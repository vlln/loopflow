"""Backend manager — backend creation, subagent execution, mock mode (infrastructure layer)."""

from __future__ import annotations

import json as _json
import subprocess
import sys
from pathlib import Path
from typing import Any

from loopflow.domain import ERROR_CATEGORIES
from loopflow.infrastructure.context import (
    _append_cache,
    _ctx,
    _emit_log,
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
                  text_handler=None, thought_handler=None, session_handler=None,
                  cwd: str | None = None):
    """Create a backend instance. Detects available backend if not specified.

    When transport="acp", routes to AcpSdkBackend (ADR-0049).
    CLI-only backends (claude, codex) have no ACP transport — raise error.
    """
    from loopflow.infrastructure.backends.base import BaseBackend
    from loopflow.infrastructure.backends.claude import ClaudeBackend
    from loopflow.infrastructure.backends.codex import CodexBackend
    from loopflow.infrastructure.backends.gemini import GeminiBackend
    from loopflow.infrastructure.backends.grok import GrokBackend
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
        "grok": GrokBackend,
    }

    # ADR-0049: transport="acp" routes to AcpSdkBackend
    if transport == "acp":
        if backend is None:
            backend = "pi"  # default ACP backend
        from loopflow.infrastructure.backends.acp_sdk_backend import (
            ACP_COMMANDS,
            ACP_NOT_INSTALLED_ERROR,
            _CLI_ONLY_BACKENDS,
        )

        # CLI-only backends have no ACP transport
        if backend in _CLI_ONLY_BACKENDS:
            print(
                f"Error: backend '{backend}' has no ACP transport",
                file=sys.stderr,
            )
            sys.exit(1)

        # Look up ACP command for this backend
        command = ACP_COMMANDS.get(backend)
        if command is None:
            print(
                f"Error: backend '{backend}' has no ACP transport",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            from loopflow.infrastructure.backends.acp_sdk_backend import AcpSdkBackend
        except ImportError:
            print(f"Error: {ACP_NOT_INSTALLED_ERROR}", file=sys.stderr)
            sys.exit(1)

        kwargs: dict = {"command": command}
        if text_handler:
            kwargs["text_handler"] = text_handler
        if thought_handler:
            kwargs["thought_handler"] = thought_handler
        if session_handler:
            kwargs["session_handler"] = session_handler
        return AcpSdkBackend(**kwargs)

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
    if session_handler:
        kwargs["session_handler"] = session_handler
    kwargs["transport"] = transport
    instance = cls(**kwargs)
    instance.backend_name = backend  # BL-036: carry resolved name for event display
    if cwd and hasattr(instance, '_transport'):
        instance._transport.cwd = cwd
    return instance


# ── subagent execution ───────────────────────────────────────────────────────

def _run_subagent(prompt: str, session: str, backend: str | None = None,
                  model: str | None = None, cwd: str | None = None,
                  agent_def=None,
                  cache_path: Path | None = None,
                  resume_session_id: str | None = None,
                  call_id: str | None = None) -> list[dict]:
    """Run a subagent session and return JSONL events."""
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

    def session_handler(session_id: str) -> None:
        event = {"type": "agent_session", "call_id": call_id, "session_id": session_id}
        _append_cache(cache_path, event)
        _write_event(event)

    instance = _make_backend(
        backend,
        text_handler=text_handler,
        thought_handler=thought_handler,
        session_handler=session_handler,
        cwd=cwd,
        transport=getattr(_ctx, "execution_options", {}) and _ctx.execution_options.get("transport"),
    )
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
        done = {
            "type": "agent_done",
            "exit_code": exit_code,
            "stderr": stderr_text,
            "session_id": sid,
        }
        # ADR-0044 §3: 后端结构化上报失败分类（尽力而为通道）
        reported = getattr(instance, "error_category", None)
        if reported in ERROR_CATEGORIES:
            done["error_category"] = reported
        return [
            {"type": "agent_message", "content": text},
            done,
        ]
    except Exception as e:
        _emit_log(f"Agent backend error: {e}")
        stderr_text = ""
        if hasattr(instance, '_transport') and hasattr(instance._transport, 'stderr_text'):
            stderr_text = instance._transport.stderr_text
        # ADR-0044 §3: 异常不再纯吞——连接/超时类映射 transient，其余 unknown
        category = (
            "transient" if isinstance(e, (ConnectionError, TimeoutError)) else "unknown"
        )
        return [
            {"type": "agent_message", "content": ""},
            {
                "type": "agent_done",
                "exit_code": 1,
                "stderr": stderr_text,
                "error_category": category,
            },
        ]
    finally:
        instance.close()
