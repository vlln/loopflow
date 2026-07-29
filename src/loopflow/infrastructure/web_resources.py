"""Loop, queue, and backend projections for the Web application layer."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import yaml

from loopflow.domain.capabilities import Capabilities
from loopflow.infrastructure import loop_state
from loopflow.infrastructure.backends.diagnostics import BACKEND_META
from loopflow.infrastructure.backends.manager import _make_backend
from loopflow.infrastructure.queue import effective_status
from loopflow.infrastructure.repository import parse_agent
from loopflow.infrastructure.web_storage import RunRepository, atomic_write_json

PREVIEW_LIMIT = 1024 * 1024
RAW_LIMIT = 50 * 1024 * 1024  # 50 MiB for binary previews (images, PDFs)
_BINARY_PREVIEW_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".pdf",
}
_SECRET = re.compile(
    r"(?i)\b(token|password|secret|api_key)(\s*(?:=|:)\s*)([^\s;,]+)"
)


class PathForbidden(ValueError):
    pass


class FileNotPreviewable(ValueError):
    pass


class DiagnosticStartFailed(RuntimeError):
    pass


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("loop.md missing frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("loop.md has incomplete frontmatter")
    try:
        value = yaml.safe_load(parts[1])
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("frontmatter must be an object")
    return value


def _extract_declared_phases(metadata: dict[str, Any]) -> list[dict[str, str]]:
    """Extract declared phases from loop.md frontmatter meta.phases.

    Returns a list of {"title": ..., "detail": ...} dicts. Invalid entries
    (missing or empty title) are silently skipped.
    """
    phases = metadata.get("phases")
    if not isinstance(phases, list):
        return []
    result: list[dict[str, str]] = []
    for entry in phases:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        result.append({"title": title.strip(), "detail": str(entry.get("detail") or "")})
    return result


def _extract_declared_args(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract declared args from loop.md frontmatter meta.args (BR-047).

    Returns a list of {"name", "default", "description", "required"} dicts.
    Entries missing a string name are silently skipped; a non-list meta.args
    is treated as no declaration.
    """
    args = metadata.get("args")
    if not isinstance(args, list):
        return []
    result: list[dict[str, Any]] = []
    for entry in args:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        result.append({
            "name": name.strip(),
            "default": entry.get("default"),
            "description": str(entry.get("description") or ""),
            "required": entry.get("required") is True,
        })
    return result


class LoopRepository:
    def __init__(self, loops_root: Path, runs: RunRepository | None = None) -> None:
        self.loops_root = loops_root
        self.runs = runs

    def find(self, name: str) -> Path | None:
        candidate = self.loops_root / name
        return candidate if candidate.is_dir() and candidate.parent == self.loops_root else None

    def list(self) -> list[dict[str, Any]]:
        if not self.loops_root.is_dir():
            return []
        return [self.summary(path) for path in sorted(self.loops_root.iterdir()) if path.is_dir()]

    def summary(self, loop_dir: Path) -> dict[str, Any]:
        try:
            metadata = _frontmatter(loop_dir / "loop.md")
            if not (loop_dir / "workflow.py").is_file():
                raise ValueError("workflow.py is missing")
            valid, error = True, None
        except (OSError, UnicodeError, ValueError) as exc:
            metadata, valid, error = {}, False, str(exc)
        agents = list((loop_dir / "agents").glob("*.md")) if (loop_dir / "agents").is_dir() else []
        state = loop_state.load(loop_dir.name)
        return {
            "name": loop_dir.name,
            "description": str(metadata.get("description") or ""),
            "agent_count": len([path for path in agents if not path.name.startswith("_")]),
            "triggers": metadata.get("triggers") if isinstance(metadata.get("triggers"), list) else [],
            "declared_phases": _extract_declared_phases(metadata),
            "declared_args": _extract_declared_args(metadata),
            "valid": valid,
            "error_summary": error,
            # Circuit breaker projection (ADR-0045 §1): per-loop pause state
            "consecutive_failures": state["consecutive_failures"],
            "paused": state["paused"],
            "paused_reason": state["paused_reason"],
            "_resources": metadata.get("resources") if isinstance(metadata.get("resources"), list) else [],
            "_environment": metadata.get("environment") if isinstance(metadata.get("environment"), str) else None,
        }

    def detail(self, loop_dir: Path) -> dict[str, Any]:
        summary = self.summary(loop_dir)
        files = [self.file_summary(loop_dir, path) for path in sorted(loop_dir.rglob("*")) if path.is_file() and not any(part.startswith(".") for part in path.relative_to(loop_dir).parts[:-1])]
        agents = []
        for path in sorted((loop_dir / "agents").glob("*.md")) if (loop_dir / "agents").is_dir() else []:
            if path.name.startswith("_"):
                continue
            try:
                agent = parse_agent(path)
                agents.append({"name": agent.name, "description": agent.description, "path": path.relative_to(loop_dir).as_posix()})
            except Exception:
                agents.append({"name": path.stem, "description": "", "path": path.relative_to(loop_dir).as_posix()})
        related = []
        if self.runs:
            related = [self.runs.read_summary(path) for path in self.runs.list_dirs()]
            related = [item for item in related if item["loop"] == loop_dir.name]
            related.sort(key=lambda item: item.get("created") or "", reverse=True)
        return {
            "name": loop_dir.name,
            "description": summary["description"],
            "valid": summary["valid"],
            "error_summary": summary["error_summary"],
            "triggers": summary["triggers"],
            "resources": summary.get("_resources", []),
            "environment": summary.get("_environment"),
            "declared_phases": summary.get("declared_phases", []),
            "declared_args": summary.get("declared_args", []),
            "consecutive_failures": summary["consecutive_failures"],
            "paused": summary["paused"],
            "paused_reason": summary["paused_reason"],
            "files": files,
            "agents": agents,
            "runs": related[:20],
        }

    def resolve_file(self, loop_dir: Path, relative: str) -> Path:
        pure = PurePosixPath(relative)
        if not relative or pure.is_absolute() or ".." in pure.parts or "\\" in relative:
            raise PathForbidden("path must be a relative POSIX path within the Loop")
        root = loop_dir.resolve()
        candidate = (root / Path(*pure.parts)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise PathForbidden("resolved path is outside the Loop") from error
        return candidate

    def preview(self, loop_dir: Path, relative: str) -> dict[str, Any]:
        path = self.resolve_file(loop_dir, relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        size = path.stat().st_size
        suffix = path.suffix.lower()
        # Binary previews: images and PDFs served via raw endpoint
        if suffix in _BINARY_PREVIEW_EXTS:
            if size > RAW_LIMIT:
                raise FileNotPreviewable(f"file exceeds the {RAW_LIMIT // (1024 * 1024)} MiB binary preview limit")
            return {
                "path": relative,
                "media_type": _media_type(path) or "application/octet-stream",
                "content": None,
                "encoding": "raw",
                "size": size,
                "read_only": True,
            }
        if size > PREVIEW_LIMIT:
            raise FileNotPreviewable("file exceeds the 1 MiB preview limit")
        raw = path.read_bytes()
        if b"\x00" in raw:
            raise FileNotPreviewable("binary files cannot be previewed")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise FileNotPreviewable("file is not UTF-8 text") from error
        return {"path": relative, "media_type": _media_type(path), "content": content, "size": size, "read_only": True}

    def serve_raw(self, loop_dir: Path, relative: str) -> tuple[bytes, str]:
        """Read a binary file and return (content_bytes, media_type) for streaming."""
        path = self.resolve_file(loop_dir, relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        size = path.stat().st_size
        if size > RAW_LIMIT:
            raise FileNotPreviewable(f"file exceeds the {RAW_LIMIT // (1024 * 1024)} MiB binary preview limit")
        return path.read_bytes(), _media_type(path) or "application/octet-stream"

    def file_summary(self, loop_dir: Path, path: Path) -> dict[str, Any]:
        relative = path.relative_to(loop_dir).as_posix()
        try:
            resolved = self.resolve_file(loop_dir, relative)
            size = resolved.stat().st_size
            suffix = resolved.suffix.lower()
            if suffix in _BINARY_PREVIEW_EXTS:
                previewable = resolved.is_file() and size <= RAW_LIMIT
            else:
                previewable = resolved.is_file() and size <= PREVIEW_LIMIT and b"\x00" not in resolved.read_bytes()[:8192]
        except (OSError, PathForbidden):
            size, previewable = path.lstat().st_size, False
        return {"path": relative, "media_type": _media_type(path), "size": size, "previewable": previewable}


def _media_type(path: Path) -> str | None:
    if path.name.endswith(".md"):
        return "text/markdown"
    if path.name.endswith(".py"):
        return "text/x-python"
    return mimetypes.guess_type(path.name)[0]


class QueueRepository:
    def __init__(self, root: Path, resource_available: Callable[[str], bool] | None = None) -> None:
        self.root = root
        self.resource_available = resource_available or (lambda _resource: True)

    def list(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        items = []
        for path in self.root.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    items.append(self._project(path, value))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(items, key=lambda item: (item["priority"], item["created"], item["task_id"]))

    def enqueue(self, loop: str, args: dict[str, Any], resources: dict[str, str], priority: int) -> dict[str, Any]:
        task_id = uuid.uuid4().hex
        value = {"loop": loop, "args": args, "resources": resources, "priority": priority, "created": datetime.now(timezone.utc).isoformat(), "status": "pending"}
        atomic_write_json(self.root / f"{task_id}.json", value)
        return self._project(self.root / f"{task_id}.json", value)

    def _project(self, path: Path, value: dict[str, Any]) -> dict[str, Any]:
        resources = value.get("resources") if isinstance(value.get("resources"), dict) else {}
        return {
            "task_id": path.stem,
            "loop": value.get("loop"),
            "args": value.get("args") if isinstance(value.get("args"), dict) else {},
            "resources": resources,
            "priority": value.get("priority", 5),
            "created": value.get("created", ""),
            "status": effective_status(value),
            "status_reason": value.get("status_reason") if isinstance(value.get("status_reason"), str) else None,
            "superseded_by": value.get("superseded_by") if isinstance(value.get("superseded_by"), str) else None,
            "blocked_resources": [name for name in resources if not self.resource_available(name)],
        }


def redact_secrets(value: str) -> str:
    return _SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)


class BackendRepository:
    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run) -> None:
        self.runner = runner

    def list(self) -> list[dict[str, Any]]:
        return [self.summary(name) for name in BACKEND_META]

    def summary(self, name: str) -> dict[str, Any]:
        meta = BACKEND_META[name]
        path = shutil.which(meta["binary"])
        version = None
        if path:
            try:
                result = self.runner([path, "--version"], capture_output=True, timeout=2, check=False)
                text = (result.stdout or result.stderr).decode("utf-8", errors="replace").strip()
                version = text.splitlines()[0] if result.returncode == 0 and text else None
            except (OSError, subprocess.SubprocessError):
                pass
        caps = Capabilities()
        transport = "cli"
        if path:  # BL-040: skip _make_backend for missing binaries
            try:
                backend = _make_backend(name)
                caps = backend.capabilities
                transport = "acp" if backend.__class__.__name__.lower().startswith("acp") else "cli"
                backend.close()
            except (SystemExit, Exception):
                pass
        return {
            "name": name,
            "status": "available" if path else "missing",
            "reason": None if path else "cli_not_found",
            "cli_path": path,
            "version": version,
            "transport": transport,
            "capabilities": {
                "native_goal": caps.native_goal,
                "structured_output": caps.structured_output,
                "native_skills": caps.native_skills,
                "resume_session": caps.resume_session,
                "durable_session_id": caps.durable_session_id,
            },
            "diagnosed_at": None,
        }

    def diagnose(self, name: str, timeout_ms: int) -> dict[str, Any]:
        if name not in BACKEND_META:
            raise KeyError(name)
        binary = BACKEND_META[name]["binary"]
        diagnosed_at = datetime.now(timezone.utc).isoformat()
        try:
            result = self.runner([binary, "--version"], capture_output=True, timeout=timeout_ms / 1000, check=False)
        except subprocess.TimeoutExpired:
            return {"name": name, "status": "unavailable", "reason": "timeout", "exit_code": None, "stdout": "", "stderr": f"diagnostic timed out after {timeout_ms}ms", "diagnosed_at": diagnosed_at}
        except OSError as error:
            raise DiagnosticStartFailed(str(error)) from error
        stdout = redact_secrets(result.stdout.decode("utf-8", errors="replace"))
        stderr = redact_secrets(result.stderr.decode("utf-8", errors="replace"))
        return {"name": name, "status": "available" if result.returncode == 0 else "unavailable", "reason": None if result.returncode == 0 else "command_failed", "exit_code": result.returncode, "stdout": stdout, "stderr": stderr, "diagnosed_at": diagnosed_at}
