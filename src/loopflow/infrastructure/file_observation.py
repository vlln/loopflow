"""File change observation — snapshot diff at phase boundaries.

Scans the working directory (pwd) at each phase() call, diffs against the
previous snapshot, and appends records to file_changes.jsonl. Controlled by
loop frontmatter meta.file_observation.

ADR-0039: file_changes.jsonl is independent from events.jsonl and has its
own `seq` cursor for SSE file_changes topic.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loopflow.infrastructure.web_events import utc_now
from loopflow.infrastructure.web_storage import atomic_write_json


@dataclass
class FileSnapshot:
    """A snapshot of file paths and their sizes in a directory tree."""
    files: dict[str, int] = field(default_factory=dict)  # relative_path -> size


@dataclass
class FileChange:
    path: str
    action: str  # "created" | "modified" | "deleted"
    size: int | None = None
    prev_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"path": self.path, "action": self.action}
        if self.size is not None:
            result["size"] = self.size
        if self.prev_size is not None:
            result["prev_size"] = self.prev_size
        return result


@dataclass
class FileObservationConfig:
    enabled: bool = True
    exclude: list[str] = field(default_factory=list)
    # Default excludes: VCS dirs, __pycache__, .DS_Store, run metadata
    _default_exclude: list[str] = field(default_factory=lambda: [
        ".git",
        ".git/**",
        "__pycache__",
        "__pycache__/**",
        "*.pyc",
        ".DS_Store",
        "node_modules",
        "node_modules/**",
        ".venv",
        ".venv/**",
    ])

    @classmethod
    def from_meta(cls, metadata: dict[str, Any]) -> "FileObservationConfig":
        obs = metadata.get("file_observation")
        if not isinstance(obs, dict):
            return cls()
        enabled = obs.get("enabled", True)
        if not isinstance(enabled, bool):
            enabled = True
        exclude = obs.get("exclude")
        if not isinstance(exclude, list):
            exclude = []
        exclude = [str(p) for p in exclude if isinstance(p, str)]
        return cls(enabled=enabled, exclude=exclude)

    def is_excluded(self, relative_path: str) -> bool:
        """Check if a relative path matches any exclude pattern."""
        parts = relative_path.split("/")
        for pattern in self._default_exclude + self.exclude:
            # Match against full path and each parent directory
            if fnmatch.fnmatch(relative_path, pattern):
                return True
            # Also match individual path components (e.g. ".git" matches any path under .git/)
            for part in parts:
                if fnmatch.fnmatch(part, pattern.rstrip("/**")):
                    return True
        return False


class FileChangeObserver:
    """Observes file changes in a working directory across phase boundaries.

    On each observe() call, scans the directory, diffs against the previous
    snapshot, and appends a record to file_changes.jsonl if there are changes.
    """

    def __init__(self, run_dir: Path, working_dir: Path, config: FileObservationConfig) -> None:
        self.run_dir = run_dir
        self.working_dir = working_dir
        self.config = config
        self._previous: FileSnapshot | None = None
        self._seq: int = 0
        self._file_changes_path = run_dir / "file_changes.jsonl"

    def observe(self, phase: str, phase_id: str) -> dict[str, Any] | None:
        """Take a snapshot and diff against previous. Returns the record if there are changes, None otherwise."""
        if not self.config.enabled:
            return None
        current = self._scan()
        if self._previous is None:
            # First snapshot: all files are "created"
            changes = [
                FileChange(path=path, action="created", size=size)
                for path, size in sorted(current.files.items())
            ]
        else:
            changes = self._diff(self._previous, current)
        self._previous = current
        if not changes:
            return None
        self._seq += 1
        record = {
            "seq": self._seq,
            "phase": phase,
            "phase_id": phase_id,
            "ts": utc_now(),
            "changes": [c.to_dict() for c in changes],
        }
        self._append(record)
        return record

    def _scan(self) -> FileSnapshot:
        """Recursively scan the working directory and return a snapshot."""
        snapshot = FileSnapshot()
        if not self.working_dir.is_dir():
            return snapshot
        for root, dirs, files in os.walk(self.working_dir):
            # Filter excluded directories in-place (prunes walk)
            dirs[:] = [
                d for d in dirs
                if not self.config.is_excluded(
                    str(Path(root, d).relative_to(self.working_dir))
                )
            ]
            for filename in files:
                full = Path(root, filename)
                try:
                    relative = str(full.relative_to(self.working_dir))
                except ValueError:
                    continue
                if self.config.is_excluded(relative):
                    continue
                try:
                    size = full.stat().st_size
                except OSError:
                    continue
                snapshot.files[relative] = size
        return snapshot

    @staticmethod
    def _diff(prev: FileSnapshot, curr: FileSnapshot) -> list[FileChange]:
        """Compute the diff between two snapshots."""
        changes: list[FileChange] = []
        prev_files = prev.files
        curr_files = curr.files
        all_paths = sorted(set(prev_files) | set(curr_files))
        for path in all_paths:
            if path not in prev_files:
                changes.append(FileChange(path=path, action="created", size=curr_files[path]))
            elif path not in curr_files:
                changes.append(FileChange(path=path, action="deleted", prev_size=prev_files[path]))
            elif prev_files[path] != curr_files[path]:
                changes.append(FileChange(
                    path=path,
                    action="modified",
                    size=curr_files[path],
                    prev_size=prev_files[path],
                ))
        return changes

    def _append(self, record: dict[str, Any]) -> None:
        """Append a record to file_changes.jsonl."""
        import json
        with self._file_changes_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
