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

def _make_backend(backend_name: str | None = None, transport: str | None = None,
                  text_handler=None):
    """Create a backend instance. Detects available backend if not specified."""
    from loopflow.backends.base import BaseBackend
    from loopflow.backends.claude import ClaudeBackend
    from loopflow.backends.codex import CodexBackend
    from loopflow.backends.gemini import GeminiBackend
    from loopflow.backends.kimi import KimiBackend
    from loopflow.backends.kiro import KiroBackend
    from loopflow.backends.opencode import OpencodeBackend
    from loopflow.backends.pi import PiBackend
    from loopflow.backends.qwen import QwenBackend

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

    if backend_name is None:
        from loopflow.backends.diagnostics import list_available_backends
        available = list_available_backends()
        if not available:
            print("[loopflow] No agent backends found on PATH.", file=sys.stderr)
            sys.exit(1)
        backend_name = available[0]

    cls = BACKEND_MAP.get(backend_name)
    if cls is None:
        print(f"Error: unknown backend '{backend_name}'", file=sys.stderr)
        sys.exit(1)

    kwargs: dict = {}
    if text_handler:
        kwargs["text_handler"] = text_handler
    kwargs["transport"] = transport
    return cls(**kwargs)


def _run_subagent(prompt: str, session: str, backend_name: str | None = None,
                  model: str | None = None) -> list[dict]:
    """Run a subagent session and return JSONL events."""
    # Collect real output from backend via text_handler
    output_parts: list[str] = []

    def text_handler(text: str) -> None:
        if text:
            output_parts.append(text)

    backend = _make_backend(backend_name, text_handler=text_handler)
    try:
        existing_sid = None
        try:
            from loopflow.registry import get_session_id_from_any
            existing_sid = get_session_id_from_any(session)
        except Exception:
            pass

        _emit_log(f"Calling agent via {backend_name or 'auto'}...")

        if existing_sid:
            exit_code = backend.resume_session(existing_sid, prompt, model=model)
        else:
            sid, exit_code = backend.create_session(prompt, model=model)
            try:
                from loopflow.registry import register
                register(session, session, sid, background=False)
            except Exception:
                pass

        text = "\n".join(output_parts) if output_parts else ""
        if text:
            _emit_log(f"Agent responded: {len(text)} chars")
        return [
            {"type": "agent_text", "content": text},
            {"type": "agent_done", "exit_code": exit_code},
        ]
    except TimeoutError:
        _emit_log(f"Agent timed out: {prompt[:80]}...")
        return [
            {"type": "agent_text", "content": ""},
            {"type": "agent_done", "exit_code": 124},
        ]
    except Exception as e:
        _emit_log(f"Agent backend error: {e}")
        return [
            {"type": "agent_text", "content": ""},
            {"type": "agent_done", "exit_code": 1},
        ]
    finally:
        backend.close()


def _extract_text(events: list[dict]) -> str:
    parts: list[str] = []
    for evt in events:
        if evt.get("type") == "agent_text":
            parts.append(evt["content"])
    return "\n".join(parts)


def _extract_exit_code(events: list[dict]) -> int:
    for evt in events:
        if evt.get("type") == "agent_done":
            return evt.get("exit_code", 0)
    return 1


# ── context ──────────────────────────────────────────────────────────────

class RunContext:
    """Tracks run state: session naming, resume, nested workflow()."""

    def __init__(self, run_id: str | None = None, run_dir: Path | None = None,
                 resume: bool = False, graph=None, live=None) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.run_dir = run_dir or Path(tempfile.gettempdir()) / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.resume = resume
        self._counter = 0
        self._prev_phase: str | None = None
        self.graph = graph  # PhaseGraph instance (optional, for live rendering)
        self.live = live    # Rich Live instance (optional)

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

_mock_mode: str | None = None  # None | "shell" | "echo"


def set_mock(mode: str | None = "shell") -> None:
    """Enable mock agent mode for testing without a real backend."""
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


# ── public API ───────────────────────────────────────────────────────────

def agent(
    prompt: str,
    *,
    schema: dict | None = None,
    label: str | None = None,
    backend: str | None = None,
    model: str | None = None,
) -> Any:
    session = _ctx.next_session()
    seq = _ctx._counter
    cache_path = _ctx.run_dir / f"{seq:04d}.jsonl"

    # Resume: skip if already completed
    if _ctx.resume:
        cached = _ctx.try_resume()
        if cached is not None:
            return cached

    t0 = time.time()

    if _mock_mode:
        text, exit_code = _run_mock(prompt)
    else:
        try:
            events = _run_subagent(prompt, session, backend_name=backend, model=model)
        except Exception as e:
            print(f"[loopflow] agent failed: {e}", file=sys.stderr)
            return None
        exit_code = _extract_exit_code(events)
        text = _extract_text(events) if exit_code == 0 else ""

    # Write cache
    try:
        cache_events = [
            {"type": "agent_start", "session": session},
            {"type": "agent_text", "content": text},
            {"type": "agent_done", "exit_code": exit_code},
        ]
        cache_path.write_text("\n".join(json.dumps(e) for e in cache_events) + "\n")
        for e in cache_events:
            _write_event(e)
    except OSError:
        pass

    if exit_code != 0:
        return None

    if schema:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    return text


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

    return mod.run(
        agent=agent, parallel=parallel, pipeline=pipeline,
        phase=phase, log=log, args=args or {},
        workflow=workflow,
    )


def phase(title: str) -> None:
    _emit_phase(title)


def log(message: str) -> None:
    _emit_log(message)


def _emit_phase(title: str) -> None:
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
            from loopflow.display.graph_renderer import TerminalGraphRenderer
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
        with open(events_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass