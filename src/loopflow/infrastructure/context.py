"""Run context — session tracking, caching, state persistence (infrastructure layer)."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any


class State:
    """Mutable state object with attribute access, backed by a dict.

    Persisted to state.json after each successful agent() call.
    """

    def __init__(self, defaults: dict | None = None) -> None:
        defaults = defaults or {}
        object.__setattr__(self, "_data", dict(defaults))
        for key, value in defaults.items():
            object.__setattr__(self, key, value)

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "_data":
            object.__setattr__(self, key, value)
        else:
            self._data[key] = value
            object.__setattr__(self, key, value)

    def to_dict(self) -> dict:
        return dict(self._data)

    @classmethod
    def from_dict(cls, data: dict, defaults: dict | None = None) -> "State":
        state = cls(defaults)
        for key, value in data.items():
            state._data[key] = value
            object.__setattr__(state, key, value)
        return state


class RunContext:
    """Tracks run state: session naming, resume, nested workflow()."""

    def __init__(self, run_id: str | None = None, run_dir: Path | None = None,
                 resume: bool = False, graph=None, live=None,
                 loop_dir: Path | None = None,
                 state: State | None = None,
                 counter: int = 0) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.run_dir = run_dir or Path(tempfile.gettempdir()) / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.resume = resume
        self._counter = counter
        self._prev_phase: str | None = None
        self._current_phase: str | None = None
        self.from_phase: str | None = None  # --from-phase: skip phases before this
        self._reached_from_phase: bool = False
        self.graph = graph
        self.live = live
        self.loop_dir = loop_dir
        self.state = state

    def next_session(self) -> str:
        self._counter += 1
        return f"wf_{self.run_id}_{self._counter}"

    def session_output_path(self, session: str) -> Path:
        return self.run_dir / f"{self._counter:04d}.jsonl"

    def try_resume(self) -> str | None:
        """If resuming and current seq already completed, return cached text."""
        if not self.resume:
            return None
        seq = self._counter
        cache_path = self.run_dir / f"{seq:04d}.jsonl"
        if not cache_path.is_file():
            return None
        try:
            events = []
            for line in cache_path.read_text().strip().split("\n"):
                if line:
                    events.append(json.loads(line))
            if _extract_exit_code(events) == 0:
                return _extract_text(events)
        except (json.JSONDecodeError, OSError):
            pass
        return None


# Module-level singleton context
_ctx = RunContext()


def set_context(ctx: RunContext) -> RunContext:
    global _ctx
    _ctx = ctx
    return _ctx


# ── event helpers ─────────────────────────────────────────────────────────

def _extract_text(events: list[dict]) -> str:
    parts: list[str] = []
    for evt in events:
        t = evt.get("type")
        if t in ("agent_message", "agent_message_chunk", "agent_text"):
            parts.append(evt["content"])
    return "\n".join(parts)


def _extract_exit_code(events: list[dict]) -> int:
    for evt in events:
        if evt.get("type") == "agent_done":
            return evt.get("exit_code", 0)
    return 1


def _extract_stderr(events: list[dict]) -> str:
    for evt in events:
        if evt.get("type") == "agent_done":
            return evt.get("stderr", "")
    return ""


def _extract_session_id(events: list[dict]) -> str | None:
    for evt in events:
        if evt.get("type") == "agent_done":
            return evt.get("session_id")
    return None


# ── log output ───────────────────────────────────────────────────────────

def _emit_log(message: str) -> None:
    """Emit a log message to stderr and events.jsonl."""
    import sys
    if _ctx.live is not None:
        _ctx.live.console.log(f"[loopflow] {message}")
    else:
        print(f"[loopflow] {message}", file=sys.stderr, flush=True)
    _write_event({"type": "log", "message": message, "ts": __import__("time").time()})


# ── cache / persist ──────────────────────────────────────────────────────

def _write_event(event: dict) -> None:
    """Append a structured event to events.jsonl in the run directory."""
    try:
        events_path = _ctx.run_dir / "events.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        pass


def _append_cache(cache_path: Path | None, event: dict) -> None:
    """Append an event to the cache file (used for real-time progress)."""
    if cache_path is None:
        return
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        pass


def _write_cache(cache_path: Path, session: str, exit_code: int, text: str) -> None:
    """Write agent_done to cache file and events.jsonl."""
    try:
        done_event = {"type": "agent_done", "exit_code": exit_code}
        _append_cache(cache_path, done_event)
        _write_event({"type": "agent_message", "content": text})
        _write_event(done_event)
    except OSError:
        pass


def _persist_state() -> None:
    """Persist workflow state to state.json after successful agent call."""
    if _ctx.state is None:
        return
    try:
        state_path = _ctx.run_dir / "state.json"
        state_path.write_text(
            json.dumps(_ctx.state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass