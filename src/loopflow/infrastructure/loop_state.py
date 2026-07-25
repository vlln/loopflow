"""Loop circuit-breaker state — per-loop cross-run state files (infrastructure layer).

Each loop has a state file at ~/.loopflow/loop_state/<loop>.json (ADR-0045 §1)
tracking consecutive run failures and the manual-release-only pause marker.
Missing or corrupted files are treated as the initial state
(consecutive_failures=0, paused=false) and never raise (AC-027-E-1).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from loopflow.infrastructure.web_storage import atomic_write_json, now_iso

DEFAULT_FAILURE_THRESHOLD = 5

_FIELDS = ("consecutive_failures", "paused", "paused_reason", "paused_at", "last_run_id")


def _loop_state_dir() -> Path:
    """Get the loop_state directory path (same LOOPFLOW_HOME rule as the queue)."""
    home = os.environ.get("LOOPFLOW_HOME", os.environ.get("HOME", os.path.expanduser("~")))
    if "LOOPFLOW_HOME" in os.environ:
        return Path(home) / "loop_state"
    return Path(home) / ".loopflow" / "loop_state"


def _initial() -> dict[str, Any]:
    return {
        "consecutive_failures": 0,
        "paused": False,
        "paused_reason": None,
        "paused_at": None,
        "last_run_id": None,
    }


def load(loop: str) -> dict[str, Any]:
    """Read a loop's circuit-breaker state; corrupted/missing reads as initial."""
    state = _initial()
    path = _loop_state_dir() / f"{loop}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state
    if not isinstance(raw, dict):
        return state
    if isinstance(raw.get("consecutive_failures"), int) and not isinstance(raw.get("consecutive_failures"), bool):
        state["consecutive_failures"] = max(0, raw["consecutive_failures"])
    if isinstance(raw.get("paused"), bool):
        state["paused"] = raw["paused"]
    for key in ("paused_reason", "paused_at", "last_run_id"):
        if isinstance(raw.get(key), str):
            state[key] = raw[key]
    return state


def _save(loop: str, state: dict[str, Any]) -> dict[str, Any]:
    directory = _loop_state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(directory / f"{loop}.json", {key: state[key] for key in _FIELDS})
    return state


def failure_threshold(meta: dict[str, Any]) -> int:
    """Resolve the failure threshold from loop.md frontmatter; invalid values use the default."""
    value = meta.get("failure_threshold")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    return DEFAULT_FAILURE_THRESHOLD


def record_failure(loop: str, run_id: str, *, threshold: int = DEFAULT_FAILURE_THRESHOLD) -> dict[str, Any]:
    """Count one failed run; pause the loop when the streak reaches the threshold."""
    state = load(loop)
    state["consecutive_failures"] += 1
    state["last_run_id"] = run_id
    if not state["paused"] and state["consecutive_failures"] >= threshold:
        state["paused"] = True
        state["paused_reason"] = f"failure_streak:{state['consecutive_failures']}"
        state["paused_at"] = now_iso()
    return _save(loop, state)


def record_success(loop: str) -> dict[str, Any]:
    """Reset the failure streak on a done run. Paused stays — release is manual only."""
    state = load(loop)
    state["consecutive_failures"] = 0
    return _save(loop, state)


def unpause(loop: str) -> dict[str, Any]:
    """Manual release: clear the pause marker and the failure streak (BR-051)."""
    state = load(loop)
    state["paused"] = False
    state["paused_reason"] = None
    state["paused_at"] = None
    state["consecutive_failures"] = 0
    return _save(loop, state)
