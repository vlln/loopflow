"""Backend manager — backend creation, subagent execution, mock mode (infrastructure layer)."""

from __future__ import annotations

import json as _json
import subprocess
import sys
from pathlib import Path
from typing import Any

from loopflow.infrastructure.context import (
    _append_cache,
    _ctx,
    _extract_exit_code,
    _extract_stderr,
    _extract_text,
    _write_event,
)


# ── mock mode ────────────────────────────────────────────────────────────────

_mock_mode: str | None = None  # None | "bash" | "auto"


def set_mock(mode: str | None = "bash") -> None:
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


def _run_mock_auto(schema: dict | None) -> tuple[str, int]:
    """Generate mock data from JSON Schema."""
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
        return "mock response"

    return _json.dumps(_generate(schema)), 0


# ── backend creation ─────────────────────────────────────────────────────────

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


# ── subagent execution ───────────────────────────────────────────────────────

def _run_subagent(prompt: str, session: str, backend: str | None = None,
                  model: str | None = None, cwd: str | None = None,
                  agent_def=None,
                  cache_path: Path | None = None,
                  resume_session_id: str | None = None) -> list[dict]:
    """Run a subagent session and return JSONL events."""
    from loopflow.presentation.events import _emit_log

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