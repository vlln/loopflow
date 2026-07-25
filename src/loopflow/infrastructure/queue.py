"""Queue — file-based task queue for loop dispatch (infrastructure layer).

Queue entries are JSON files in ~/.loopflow/queue/. Each entry carries an
explicit status (ADR-0047): pending / deferred / superseded. Entries with a
missing or unknown status are treated as pending (backward compatible).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

VALID_STATUSES = {"pending", "deferred", "superseded"}


def _queue_dir() -> Path:
    """Get the queue directory path."""
    home = os.environ.get("LOOPFLOW_HOME", os.environ.get("HOME", os.path.expanduser("~")))
    if "LOOPFLOW_HOME" in os.environ:
        return Path(home) / "queue"
    return Path(home) / ".loopflow" / "queue"


def effective_status(entry: dict) -> str:
    """Return the entry's status; missing or unknown values count as pending."""
    status = entry.get("status")
    return status if status in VALID_STATUSES else "pending"


def mark_status(path: Path, status: str, *, reason: str | None = None,
                superseded_by: str | None = None) -> None:
    """Update a queue entry's status in place, preserving other fields."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = status
    if reason is not None:
        data["status_reason"] = reason
    if superseded_by is not None:
        data["superseded_by"] = superseded_by
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def enqueue(loop: str, args: dict | None = None,
            resources: dict | None = None,
            priority: int = 5,
            supersede: bool = False) -> Path:
    """Add a task to the queue. Returns the queue file path.

    With supersede=True, existing pending/deferred tasks of the same loop are
    marked superseded with superseded_by pointing at the new task id.
    """
    qdir = _queue_dir()
    qdir.mkdir(parents=True, exist_ok=True)

    task_id = uuid.uuid4().hex

    if supersede:
        for entry in list_queue():
            if entry.get("loop") != loop:
                continue
            if effective_status(entry) in ("pending", "deferred"):
                mark_status(Path(entry["path"]), "superseded",
                            reason=f"superseded by task {task_id}",
                            superseded_by=task_id)

    entry = {
        "loop": loop,
        "args": args or {},
        "resources": resources or {},
        "priority": priority,
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }

    path = qdir / f"{task_id}.json"
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def dequeue(path: Path) -> None:
    """Remove a task from the queue after processing."""
    try:
        path.unlink()
    except OSError:
        pass


def list_queue() -> list[dict]:
    """List all pending tasks, sorted by priority then created time.

    Returns list of dicts with keys: path, loop, args, resources, priority,
    created, plus the status fields (status/status_reason/superseded_by) when
    present. Use effective_status() for the backward-compatible default.
    """
    qdir = _queue_dir()
    if not qdir.is_dir():
        return []

    entries = []
    for path in sorted(qdir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["path"] = str(path)
            entries.append(data)
        except (json.JSONDecodeError, OSError):
            continue

    entries.sort(key=lambda e: (e.get("priority", 5), e.get("created", "")))
    return entries


def queue_size() -> int:
    """Return the number of pending tasks."""
    qdir = _queue_dir()
    if not qdir.is_dir():
        return 0
    return len(list(qdir.glob("*.json")))