"""Dispatch — scan queue, sort by priority, lock resources, execute loop (infrastructure layer)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from loopflow.infrastructure.queue import list_queue, dequeue, queue_size
from loopflow.infrastructure.lock import acquire_resources, release_resources


def dispatch(run_func: Callable[[str, dict], None] | None = None) -> dict:
    """Scan queue, execute pending tasks with resource locking.

    Args:
        run_func: Optional callable(loop_name, args) to execute a loop.
                  Defaults to _run_loop_subprocess. Injected for testing.

    Returns a summary dict with keys: processed, skipped, errors.
    Each call is idempotent — safe to call repeatedly via cron/launchd.
    """
    if run_func is None:
        run_func = _run_loop_subprocess

    summary = {"processed": 0, "skipped": 0, "errors": 0}

    if queue_size() == 0:
        return summary

    entries = list_queue()
    for entry in entries:
        path = Path(entry["path"])
        loop_name = entry["loop"]
        resources = entry.get("resources", {})
        task_args = entry.get("args", {})

        # Try to acquire all resource locks
        locks = []
        try:
            if resources:
                locks = acquire_resources(resources)
        except RuntimeError:
            summary["skipped"] += 1
            continue

        # Remove from queue and execute
        dequeue(path)

        try:
            run_func(loop_name, task_args)
            summary["processed"] += 1
        except Exception:
            summary["errors"] += 1
        finally:
            if locks:
                release_resources(locks)

    return summary


def _run_loop_subprocess(loop_name: str, args: dict) -> None:
    """Execute a loop via the CLI. Raises subprocess.CalledProcessError on failure."""
    import json

    cmd = ["loop", "run", loop_name]
    if args:
        cmd.extend(["--args", json.dumps(args, ensure_ascii=False)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[loopflow] dispatch: {loop_name} failed (exit {result.returncode})",
              file=sys.stderr)
        if result.stderr:
            print(f"[loopflow] {result.stderr.strip()}", file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)