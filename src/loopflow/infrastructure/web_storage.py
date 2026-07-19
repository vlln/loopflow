"""Filesystem and process primitives for Web application services."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from loopflow.infrastructure.web_events import EventProjection, project_events


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise


class ProcessProbe(Protocol):
    def identity(self, pid: int) -> str | None: ...

    def terminate(self, pid: int) -> bool: ...


class SystemProcessProbe:
    def identity(self, pid: int) -> str | None:
        if pid <= 0:
            return None
        proc_stat = Path(f"/proc/{pid}/stat")
        try:
            fields = proc_stat.read_text(encoding="utf-8").split()
            return f"linux:{fields[21]}" if len(fields) > 21 else None
        except OSError:
            pass
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "lstart="],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        value = result.stdout.strip()
        return f"ps:{value}" if result.returncode == 0 and value else None

    def terminate(self, pid: int) -> bool:
        try:
            os.kill(pid, 15)
            return True
        except (OSError, ValueError):
            return False


def parse_error_summary(error: json.JSONDecodeError) -> str:
    return f"line {error.lineno}, column {error.colno}: {error.msg}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _duration_ms(metadata: dict[str, Any], now: str | None = None) -> int | None:
    started = metadata.get("started_at") or metadata.get("created")
    finished = metadata.get("finished_at") or (now if metadata.get("status") == "running" else None)
    if not started or not finished:
        return None
    try:
        start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        finish_dt = datetime.fromisoformat(str(finished).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((finish_dt - start_dt).total_seconds() * 1000))


def allowed_actions(status: str) -> list[str]:
    return {
        "running": ["stop"],
        "stale": ["reconcile"],
        "failed": ["resume", "rerun"],
        "stopped": ["resume", "rerun"],
        "done": ["rerun"],
    }.get(status, [])


class RunRepository:
    def __init__(self, runs_root: Path, process_probe: ProcessProbe | None = None) -> None:
        self.runs_root = runs_root
        self.process_probe = process_probe or SystemProcessProbe()

    def find(self, run_id: str) -> Path | None:
        if not self.runs_root.is_dir():
            return None
        direct = self.runs_root / run_id
        if (direct / "run.json").is_file():
            return direct
        for candidate in self.runs_root.glob(f"*/{run_id}"):
            if (candidate / "run.json").is_file():
                return candidate
        return None

    def list_dirs(self) -> list[Path]:
        if not self.runs_root.is_dir():
            return []
        direct = [path.parent for path in self.runs_root.glob("*/run.json")]
        nested = [path.parent for path in self.runs_root.glob("*/*/run.json")]
        return sorted(set(direct + nested))

    def read_summary(self, run_dir: Path) -> dict[str, Any]:
        run_path = run_dir / "run.json"
        try:
            metadata = read_json(run_path)
            if not isinstance(metadata, dict):
                raise json.JSONDecodeError("run metadata must be an object", run_path.read_text(), 0)
        except json.JSONDecodeError as error:
            return {
                "run_id": run_dir.name,
                "loop": None,
                "status": "unreadable",
                "current_phase": None,
                "created": None,
                "started_at": None,
                "finished_at": None,
                "updated_at": None,
                "duration_ms": None,
                "iteration_count": 0,
                "error_summary": None,
                "parse_error": parse_error_summary(error),
                "allowed_actions": [],
            }
        status = str(metadata.get("status", "unreadable"))
        if status == "running" and not self._identity_matches(metadata):
            status = "stale"
        projection = project_events(run_dir / "events.jsonl")
        return {
            "run_id": str(metadata.get("run_id") or run_dir.name),
            "loop": metadata.get("loop"),
            "status": status,
            "current_phase": metadata.get("current_phase") or (
                projection.occurrences[-1]["phase"] if projection.occurrences else None
            ),
            "created": metadata.get("created"),
            "started_at": metadata.get("started_at"),
            "finished_at": metadata.get("finished_at"),
            "updated_at": metadata.get("updated_at"),
            "duration_ms": _duration_ms(metadata, now_iso()),
            "iteration_count": sum(edge["count"] for edge in projection.graph["edges"] if edge["is_backedge"]),
            "error_summary": metadata.get("error_summary"),
            "parse_error": None,
            "allowed_actions": allowed_actions(status),
        }

    def read_detail(self, run_dir: Path) -> dict[str, Any]:
        summary = self.read_summary(run_dir)
        projection = project_events(run_dir / "events.jsonl")
        try:
            metadata = read_json(run_dir / "run.json")
        except json.JSONDecodeError:
            metadata = {}
        try:
            state = read_json(run_dir / "state.json") if (run_dir / "state.json").is_file() else None
        except (json.JSONDecodeError, OSError):
            state = None
        calls = [{key: value for key, value in call.items() if key != "events"} for call in projection.calls]
        return {
            **summary,
            "args": metadata.get("args") if isinstance(metadata, dict) else None,
            "state": state,
            "working_directory": str(run_dir),
            "graph": projection.graph,
            "occurrences": projection.occurrences,
            "calls": calls,
            "unattributed_count": len(projection.unattributed),
            "malformed_count": len(projection.malformed),
            "events": projection.events,
            "unattributed": projection.unattributed,
            "malformed": projection.malformed,
        }

    def write_metadata(self, run_dir: Path, metadata: dict[str, Any]) -> None:
        updated = dict(metadata)
        updated["updated_at"] = now_iso()
        atomic_write_json(run_dir / "run.json", updated)

    def reconcile(self, run_dir: Path) -> dict[str, Any]:
        metadata = read_json(run_dir / "run.json")
        if metadata.get("status") != "running":
            raise ValueError("run_not_stale")
        if self._identity_matches(metadata):
            raise RuntimeError("process_alive")
        finished = now_iso()
        metadata.update(
            {
                "status": "failed",
                "finished_at": finished,
                "updated_at": finished,
                "error_summary": "Run process is no longer available",
            }
        )
        metadata.pop("pid", None)
        metadata.pop("process_started_at", None)
        atomic_write_json(run_dir / "run.json", metadata)
        return self.read_summary(run_dir)

    def _identity_matches(self, metadata: dict[str, Any]) -> bool:
        pid = metadata.get("pid")
        expected = metadata.get("process_started_at")
        return isinstance(pid, int) and bool(expected) and self.process_probe.identity(pid) == expected
