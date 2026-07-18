"""Queue — file-based task queue for loop dispatch (infrastructure layer).

Queue entries are JSON files in ~/.loopflow/queue/. Each file represents
one pending task. Dispatch reads, sorts, and removes entries.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _queue_dir() -> Path:
    """Get the queue directory path."""
    home = os.environ.get("LOOPFLOW_HOME", os.environ.get("HOME", os.path.expanduser("~")))
    if "LOOPFLOW_HOME" in os.environ:
        return Path(home) / "queue"
    return Path(home) / ".loopflow" / "queue"


def enqueue(loop: str, args: dict | None = None,
            resources: dict | None = None,
            priority: int = 5) -> Path:
    """Add a task to the queue. Returns the queue file path."""
    qdir = _queue_dir()
    qdir.mkdir(parents=True, exist_ok=True)

    entry = {
        "loop": loop,
        "args": args or {},
        "resources": resources or {},
        "priority": priority,
        "created": datetime.now(timezone.utc).isoformat(),
    }

    path = qdir / f"{uuid.uuid4().hex}.json"
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

    Returns list of dicts with keys: path, loop, args, resources, priority, created.
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