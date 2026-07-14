"""Workflow runtime — agent, parallel, pipeline, phase, log, workflow.

Delegates to backends for actual agent execution. Uses sequential counter
for resume support: each agent() call gets a unique seq number, output is
cached to <seq>.jsonl. On resume, completed calls return cached results.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable


# ── helpers ──────────────────────────────────────────────────────────────

def _make_backend(backend: str | None = None, transport: str | None = None,
                  text_handler=None, thought_handler=None, cwd: str | None = None):
    """Create a backend instance. Detects available backend if not specified."""
    from loopflow.infrastructure.backends.base import BaseBackend
    from loopflow.infrastructure.backends.claude import ClaudeBackend
    from loopflow.infrastructure.backends.codex import CodexBackend
    from loopflow.infrastructure.backends.gemini import GeminiBackend
    from loopflow.infrastructure.backends.kimi import KimiBackend
    from loopflow.infrastructure.backends.kiro import KiroBackend
    from loopflow.infrastructure.backends.opencode import OpencodeBackend
    from loopflow.infrastructure.backends.pi import PiBackend
    from loopflow.infrastructure.backends.qwen import QwenBackend

    BACKEND_MAP: dict[str, type[BaseBackend]] = {
        "kimi": KimiBackend,
        "claude": ClaudeBackend,
        "codex": CodexBackend,
        "pi": PiBackend,
        "kiro": KiroBackend,
        "opencode": OpencodeBackend,
        "qwen": QwenBackend,
        "gemini": GeminiBackend,
    }

    if backend is None:
        from loopflow.infrastructure.backends.diagnostics import list_available_backends
        available = list_available_backends()
        if not available:
            print("[loopflow] No agent backends found on PATH.", file=sys.stderr)
            sys.exit(1)
        backend = available[0]

    cls = BACKEND_MAP.get(backend)
    if cls is None:
        print(f"Error: unknown backend '{backend}'", file=sys.stderr)
        sys.exit(1)

    kwargs: dict = {}
    if text_handler:
        kwargs["text_handler"] = text_handler
    if thought_handler:
        kwargs["thought_handler"] = thought_handler
    kwargs["transport"] = transport
    instance = cls(**kwargs)
    if cwd and hasattr(instance, '_transport'):
        instance._transport.cwd = cwd
    return instance


def _run_subagent(prompt: str, session: str, backend: str | None = None,
                  model: str | None = None, cwd: str | None = None,
                  agent_def=None,
                  cache_path: Path | None = None,
                  resume_session_id: str | None = None) -> list[dict]:
    """Run a subagent session and return JSONL events.

    If resume_session_id is set, resumes the existing session instead of
    creating a new one.
    """
    # Collect real output from backend via text_handler
    output_parts: list[str] = []

    def text_handler(text: str) -> None:
        if text:
            output_parts.append(text)
            _write_event({"type": "agent_message", "session": session, "content": text})
            _append_cache(cache_path, {"type": "agent_message", "content": text})
            print(f"[agent] {text}", file=sys.stderr, flush=True)

    def thought_handler(text: str) -> None:
        if text:
            _append_cache(cache_path, {"type": "agent_thought", "content": text})

    instance = _make_backend(backend, text_handler=text_handler, thought_handler=thought_handler, cwd=cwd)
    try:
        _emit_log(f"Calling agent via {backend or 'auto'}...")

        # Pass loop-level skills directory to the backend
        skills_dir = None
        if _ctx.loop_dir is not None and (_ctx.loop_dir / ".skills").is_dir():
            skills_dir = str(_ctx.loop_dir / ".skills")

        if resume_session_id:
            _emit_log(f"Resuming session {resume_session_id}...")
            exit_code = instance.resume_session(
                resume_session_id, prompt, model=model,
                agent_def=agent_def, skills_dir=skills_dir,
            )
            sid = resume_session_id
        else:
            sid, exit_code = instance.create_session(prompt, model=model, agent_def=agent_def, skills_dir=skills_dir)

        text = "\n".join(output_parts) if output_parts else ""
        stderr_text = ""
        if hasattr(instance, '_transport') and hasattr(instance._transport, 'stderr_text'):
            stderr_text = instance._transport.stderr_text
        if text:
            _emit_log(f"Agent responded: {len(text)} chars")
        return [
            {"type": "agent_message", "content": text},
            {"type": "agent_done", "exit_code": exit_code, "stderr": stderr_text, "session_id": sid},
        ]
    except Exception as e:
        _emit_log(f"Agent backend error: {e}")
        stderr_text = ""
        if hasattr(instance, '_transport') and hasattr(instance._transport, 'stderr_text'):
            stderr_text = instance._transport.stderr_text
        return [
            {"type": "agent_message", "content": ""},
            {"type": "agent_done", "exit_code": 1, "stderr": stderr_text},
        ]
    finally:
        instance.close()


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
    """Extract backend session ID from agent_done event."""
    for evt in events:
        if evt.get("type") == "agent_done":
            return evt.get("session_id")
    return None


# ── context ──────────────────────────────────────────────────────────────

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
        self.graph = graph  # PhaseGraph instance (optional, for live rendering)
        self.live = live    # Rich Live instance (optional)
        self.loop_dir = loop_dir  # Path to loop definition directory
        self.state = state  # Workflow state (optional, auto-persisted)

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


_ctx = RunContext()


def set_context(ctx: RunContext) -> RunContext:
    global _ctx
    _ctx = ctx
    return _ctx


def _tempfile_getdir() -> str:
    import tempfile
    return tempfile.gettempdir()


# ── mock agent ────────────────────────────────────────────────────────────

_mock_mode: str | None = None  # None | "bash" | "auto"


def set_mock(mode: str | None = "bash") -> None:
    """Enable mock agent mode for testing without a real backend.

    Args:
        mode: "bash" (shell execution) or "auto" (schema-based generation).
    """
    global _mock_mode
    _mock_mode = mode


def _run_mock(prompt: str) -> tuple[str, int]:
    """Run prompt as shell command, return (stdout, exit_code)."""
    try:
        result = subprocess.run(
            prompt, shell=True, capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", 1
    except Exception:
        return "", 1


def _run_mock_auto(schema: dict | None) -> tuple[str, int]:
    """Generate mock data from JSON Schema.

    Rules:
    - string + enum → first enum value
    - string (no enum) → field name
    - number/integer → 0
    - boolean → false
    - array → empty list
    - object → empty object
    """
    if schema is None:
        return "mock response", 0

    def _generate(s: dict) -> Any:
        if "enum" in s and isinstance(s["enum"], list) and s["enum"]:
            return s["enum"][0]
        t = s.get("type", "string")
        if t == "object":
            result = {}
            for key, prop in s.get("properties", {}).items():
                if isinstance(prop, dict):
                    result[key] = _generate(prop)
            return result
        if t == "array":
            return []
        if t == "boolean":
            return False
        if t in ("number", "integer"):
            return 0
        return "mock response"  # string without enum

    return json.dumps(_generate(schema)), 0


# ── public API ───────────────────────────────────────────────────────────

def agent(
    prompt: str,
    *,
    schema: dict | None = None,
    max_retries: int = 3,
    isolation: str | None = None,
    label: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    agent_def: str | None = None,
    goal: str | None = None,
    goal_max_iterations: int = 10,
    **kwargs: str,
) -> Any:
    """Run an agent call. Thin facade over AgentRunner."""
    from loopflow.infrastructure.repository import parse_agent
    from loopflow.application.runner import AgentRunner

    # Load agent definition
    ad = None
    if _ctx.loop_dir is not None and agent_def is not None:
        agent_path = _ctx.loop_dir / "agents" / f"{agent_def}.md"
        if agent_path.is_file():
            try:
                ad = parse_agent(agent_path)
            except (ValueError, FileNotFoundError):
                ad = None

    # Create backend once — AgentRunner owns it
    backend_instance = None if _mock_mode else _make_backend(backend)
    try:
        # Build invoke closure that calls _run_subagent
        def _invoke(prompt_str, session_name, **kw):
            return _run_subagent(
                prompt_str, session_name, backend=backend,
                model=kw.get("model"), cwd=kw.get("cwd"),
                agent_def=kw.get("agent_def"),
                cache_path=kw.get("cache_path"),
                resume_session_id=kw.get("resume_session_id"),
            )

        runner = AgentRunner(
            ad, backend_instance, _ctx,
            invoke_fn=_invoke,
            log_fn=_emit_log,
            write_event_fn=_write_event,
            write_cache_fn=_write_cache,
            persist_state_fn=_persist_state,
            create_worktree_fn=_create_worktree,
            mock_mode=_mock_mode,
            mock_fn=_run_mock,
            mock_auto_fn=_run_mock_auto,
        )
        return runner.run(
            prompt,
            goal=goal,
            model=model,
            schema=schema,
            isolation=isolation,
            max_retries=max_retries,
            goal_max_iterations=goal_max_iterations,
            **kwargs,
        )
    finally:
        if backend_instance:
            backend_instance.close()


def parallel(thunks: list[Callable[[], Any]]) -> list[Any]:
    results: list[Any] = [None] * len(thunks)

    def _run(idx: int, fn: Callable[[], Any]) -> None:
        try:
            results[idx] = fn()
        except Exception:
            results[idx] = None

    threads: list[threading.Thread] = []
    for i, fn in enumerate(thunks):
        t = threading.Thread(target=_run, args=(i, fn), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results


def pipeline(items: list[Any], *stages: Callable) -> list[Any]:
    results: list[Any] = [None] * len(items)

    def _process(idx: int, item: Any) -> None:
        result: Any = item
        for stage in stages:
            try:
                if stage is stages[0]:
                    result = stage(item, idx)
                else:
                    result = stage(result, item, idx)
            except Exception:
                result = None
                break
            if result is None:
                break
        results[idx] = result

    threads: list[threading.Thread] = []
    for i, item in enumerate(items):
        t = threading.Thread(target=_process, args=(i, item), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results


def workflow(script_path: str, args: dict | None = None) -> Any:
    """Run another workflow script as a sub-workflow (one level deep)."""
    path = Path(script_path)
    if not path.is_file():
        return None

    spec = importlib.util.spec_from_file_location(
        f"wf_sub_{_ctx.run_id}_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None

    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None

    if not hasattr(mod, "run"):
        return None

    import inspect
    sig = inspect.signature(mod.run)
    run_kwargs = dict(
        agent=agent, parallel=parallel, pipeline=pipeline,
        phase=phase, log=log, args=args or {},
        workflow=workflow,
    )
    if "state" in sig.parameters:
        run_kwargs["state"] = _ctx.state
    return mod.run(**run_kwargs)


def phase(title: str) -> None:
    _emit_phase(title)


def log(message: str) -> None:
    _emit_log(message)


def _emit_phase(title: str) -> None:
    _ctx._current_phase = title

    if _ctx.live is not None:
        _ctx.live.console.log(f"[loopflow] Phase: {title}")
    else:
        print(f"[loopflow] Phase: {title}", file=sys.stderr, flush=True)

    _write_event({"type": "phase", "title": title, "ts": time.time()})

    # Live graph rendering
    if _ctx.graph is not None:
        _ctx.graph.record(_ctx._prev_phase, title)
        _ctx._prev_phase = title
        if _ctx.live is not None:
            from loopflow.presentation.display.graph_renderer import TerminalGraphRenderer
            renderer = TerminalGraphRenderer(_ctx.graph)
            _ctx.live.update(renderer.render())


def _emit_log(message: str) -> None:
    if _ctx.live is not None:
        _ctx.live.console.log(f"[loopflow] {message}")
    else:
        print(f"[loopflow] {message}", file=sys.stderr, flush=True)

    _write_event({"type": "log", "message": message, "ts": time.time()})


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
    """Write agent_done to cache file and events.jsonl.

    agent_text chunks are already in the cache file via _append_cache
    (real mode). For mock mode, text_handler is never called, so write
    agent_text to events.jsonl here.
    """
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
        state_path.write_text(json.dumps(_ctx.state.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _create_worktree(run_id: str, seq: int) -> str | None:
    """Create a git worktree for isolated agent execution.

    Returns the worktree path, or None if not in a git repo.
    """
    import subprocess
    worktree_name = f"lf_{run_id}_{seq}"
    worktree_path = Path.cwd() / ".agents" / "worktrees" / worktree_name
    try:
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path)],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return str(worktree_path)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None