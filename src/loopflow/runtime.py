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


# ── infra retry ──────────────────────────────────────────────────────────

INFRA_BACKOFF = [3, 9, 27]
_TRANSIENT_PATTERNS: list[tuple[str, str]] = [
    ("connection_error", "connection_error"),
    ("terminated", "terminated"),
    ("timeout", "timeout"),
    ("rate_limit", "rate_limit"),
    ("rate limited", "rate_limit"),
    ("timed out", "timeout"),
]


def _is_transient_error(stderr: str) -> bool:
    """Check if stderr contains a known transient error pattern."""
    stderr_lower = stderr.lower()
    return any(pattern in stderr_lower for pattern, _ in _TRANSIENT_PATTERNS)


def _transient_reason(stderr: str) -> str:
    """Extract the transient error reason from stderr."""
    stderr_lower = stderr.lower()
    for pattern, reason in _TRANSIENT_PATTERNS:
        if pattern in stderr_lower:
            return reason
    return "unknown"


# ── helpers ──────────────────────────────────────────────────────────────

def _make_backend(backend: str | None = None, transport: str | None = None,
                  text_handler=None, thought_handler=None, cwd: str | None = None):
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

    if backend is None:
        from loopflow.backends.diagnostics import list_available_backends
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


def _backend_supports_native_goal(backend: str | None = None) -> bool:
    """Check if the backend supports native /goal in -p mode."""
    from loopflow.backends.claude import ClaudeBackend
    from loopflow.backends.codex import CodexBackend
    from loopflow.backends.gemini import GeminiBackend
    from loopflow.backends.kimi import KimiBackend
    from loopflow.backends.kiro import KiroBackend
    from loopflow.backends.opencode import OpencodeBackend
    from loopflow.backends.pi import PiBackend
    from loopflow.backends.qwen import QwenBackend

    BACKEND_MAP: dict[str, type] = {
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
        from loopflow.backends.diagnostics import list_available_backends
        available = list_available_backends()
        if not available:
            return False
        backend = available[0]

    cls = BACKEND_MAP.get(backend)
    if cls is None:
        return False
    return bool(getattr(cls, '_supports_native_goal', False))


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


# ── goal mode helpers ────────────────────────────────────────────────────

def _add_goal_to_schema(schema: dict | None) -> dict:
    """Wrap business schema with __goal framework schema.

    Returns a new schema dict; does not modify the input.
    """
    goal_prop = {
        "__goal": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "complete", "blocked"],
                },
                "reason": {"type": "string"},
            },
            "required": ["status"],
        }
    }

    if schema is None:
        return {
            "type": "object",
            "properties": {**goal_prop},
            "required": ["__goal"],
        }

    # Warn if business schema already uses __goal
    if "__goal" in (schema.get("properties") or {}):
        import warnings
        warnings.warn(
            "Business schema contains '__goal' field which is reserved "
            "for goal mode. Framework will override it."
        )

    return {
        **schema,
        "properties": {
            **(schema.get("properties") or {}),
            **goal_prop,
        },
        "required": (schema.get("required") or []) + ["__goal"],
    }


def _build_goal_steering(goal: str, iteration: int, max_iterations: int) -> str:
    """Generate steering prompt for goal mode.

    First iteration: full rules (completion audit, blocked audit).
    Subsequent iterations: lightweight continuation notice.
    """
    if iteration == 1:
        return (
            f"<goal-steering>\n"
            f"You are working toward a goal. Continue working until the goal "
            f"is fully accomplished.\n\n"
            f"## Goal\n"
            f"{goal}\n\n"
            f"## Completion Audit\n"
            f"Before declaring complete, verify:\n"
            f"1. Each requirement in the goal is met\n"
            f"2. Verification is based on evidence (files, command output, "
            f"test results)\n"
            f"3. \"I made a plan\" or \"I wrote a summary\" is NOT completion\n\n"
            f"## Blocked Audit\n"
            f"Before declaring blocked:\n"
            f"1. The same blocking condition must persist for 3 consecutive "
            f"attempts\n"
            f"2. \"Difficult\", \"slow\", or \"not fully done\" is NOT a blocker\n"
            f"3. Only truly insurmountable obstacles qualify (missing "
            f"credentials, external service down, etc.)\n\n"
            f"Signal your status in the __goal field of your response.\n"
            f"</goal-steering>"
        )
    else:
        return (
            f"<goal-steering>\n"
            f"Continue working toward the goal. "
            f"Iteration {iteration}/{max_iterations}.\n\n"
            f"## Goal\n"
            f"{goal}\n\n"
            f"Same completion and blocked audit rules apply. "
            f"Continue from where you left off.\n"
            f"</goal-steering>"
        )


def _call_agent_once(
    resolved_prompt: str,
    session: str,
    schema: dict | None,
    backend: str | None,
    model: str | None,
    isolation: str | None,
    ad,
    cache_path: Path,
    retry_hint: str,
    max_retries: int,
    resume_session_id: str | None = None,
) -> tuple[dict | str, str | None]:
    """Run a single agent call (create or resume) and return (result, backend_session_id).

    Returns parsed dict if schema is set, raw text otherwise.
    Raises AgentError on failure.
    """
    t0 = time.time()
    backend_sid: str | None = None

    if _mock_mode == "auto":
        _write_event({"type": "agent_start", "session": session, "phase": _ctx._current_phase})
        text, exit_code = _run_mock_auto(schema)
    elif _mock_mode == "bash":
        _write_event({"type": "agent_start", "session": session, "phase": _ctx._current_phase})
        text, exit_code = _run_mock(resolved_prompt + retry_hint)
        if exit_code != 0:
            text = ""
    else:
        cwd = None
        if isolation == "worktree":
            cwd = _create_worktree(_ctx.run_id, _ctx._counter)
            if cwd:
                _emit_log(f"Worktree: {cwd}")

        events = _run_subagent(
            resolved_prompt + retry_hint,
            session,
            backend=backend,
            model=model,
            cwd=cwd,
            agent_def=ad if ad else None,
            cache_path=cache_path,
            resume_session_id=resume_session_id,
        )
        exit_code = _extract_exit_code(events)
        text = _extract_text(events) if exit_code == 0 else ""
        backend_sid = _extract_session_id(events)

        if exit_code != 0:
            stderr = _extract_stderr(events)
            from loopflow.agent import AgentError
            msg = f"Agent call failed with exit code {exit_code}"
            if stderr:
                msg += f"\nStderr: {stderr}"
            raise AgentError(msg)

    if schema:
        try:
            return json.loads(text), backend_sid
        except json.JSONDecodeError:
            from loopflow.agent import extract_json
            extracted = extract_json(text, schema)
            if extracted is not None:
                return extracted, backend_sid
            from loopflow.agent import AgentError
            raise AgentError(
                f"Agent failed to return valid JSON after "
                f"{max_retries} retries"
            )

    return text, backend_sid


def _run_with_goal(
    resolved_prompt: str,
    schema: dict | None,
    goal: str,
    goal_max_iterations: int,
    max_retries: int,
    backend: str | None,
    model: str | None,
    isolation: str | None,
    ad,
    agent_def: str | None,
    cache_path: Path,
) -> Any:
    """Run agent in goal mode: iterate until complete or blocked."""
    from loopflow.agent import GoalBlocked

    goal_schema = _add_goal_to_schema(schema)

    session = _ctx.next_session()
    resume_session_id: str | None = None
    blocked_reason: str | None = None
    blocked_count = 0

    for iteration in range(1, goal_max_iterations + 1):
        steering = _build_goal_steering(goal, iteration, goal_max_iterations)
        full_prompt = f"{steering}\n\n{resolved_prompt}"

        # Inject goal schema into prompt
        import json as json_mod
        schema_hint = (
            f"\n\n---\n"
            f"Output format — you MUST respond with a single JSON object "
            f"matching this schema:\n{json_mod.dumps(goal_schema, indent=2)}\n\n"
            f"Do NOT wrap the JSON in markdown code blocks. "
            f"Return ONLY the JSON object."
        )

        # Retry loop for schema compliance
        retry_hint = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                _emit_log(f"Goal iter {iteration}: JSON parse failed, retrying ({attempt}/{max_retries})...")
                retry_hint = (
                    f"\n\n---\n"
                    f"Your previous response was not valid JSON. "
                    f"Please respond with ONLY a JSON object matching the schema above."
                )
            try:
                result, backend_sid = _call_agent_once(
                    resolved_prompt=full_prompt,
                    session=session,
                    schema=goal_schema,
                    backend=backend,
                    model=model,
                    isolation=isolation,
                    ad=ad,
                    cache_path=cache_path,
                    retry_hint=retry_hint,
                    max_retries=max_retries,
                    resume_session_id=resume_session_id,
                )
                break
            except Exception as e:
                # Only retry on JSON parse errors, not infra errors
                msg = str(e)
                if "valid JSON" not in msg:
                    raise
                if attempt >= max_retries:
                    raise
                continue

        # Extract goal state
        goal_state: dict = result.pop("__goal", {}) if isinstance(result, dict) else {}
        status = goal_state.get("status", "active")

        if status == "complete":
            _write_cache(cache_path, session, 0, json.dumps(result))
            _persist_state()
            return result

        if status == "blocked":
            reason = goal_state.get("reason") or "unknown"
            if reason == blocked_reason:
                blocked_count += 1
            else:
                blocked_reason = reason
                blocked_count = 1

            _emit_log(f"Goal blocked ({blocked_count}/3): {reason}")

            if blocked_count >= 3:
                raise GoalBlocked(
                    f"Goal blocked after {iteration} iterations: {reason} "
                    f"(3 consecutive identical reasons)"
                )

        # active or first/second blocked → set up resume for next iteration
        resume_session_id = backend_sid
        session = _ctx.next_session()

    # Max iterations reached
    raise GoalBlocked(
        f"Goal not completed after {goal_max_iterations} iterations"
    )


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
    session = _ctx.next_session()
    seq = _ctx._counter
    cache_path = _ctx.run_dir / f"{seq:04d}.jsonl"

    # Resolve agent definition: load body from agents/<agent_def>.md
    resolved_prompt = prompt
    ad = None
    if _ctx.loop_dir is not None and agent_def is not None:
        agent_path = _ctx.loop_dir / "agents" / f"{agent_def}.md"
        if agent_path.is_file():
            from loopflow.agent import parse_agent, render_template, resolve_params, _input_to_params
            try:
                ad = parse_agent(agent_path)
            except (ValueError, FileNotFoundError):
                ad = None
            if ad is not None:
                params = _input_to_params(ad.input)
                resolved_kwargs = resolve_params(params, **kwargs)
                body = render_template(ad.body, **resolved_kwargs)
                resolved_prompt = f"{body}\n\n---\n\nTask: {prompt}"

                # Auto-detect output schema from agent definition
                if schema is None and ad.output is not None:
                    schema = ad.output

                # Inject skill descriptions into system prompt
                if ad.skills:
                    from loopflow.skills import build_skill_prompt, check_skills
                    missing = check_skills(ad.skills, _ctx.loop_dir)
                    if missing:
                        skills_dir_hint = f"{_ctx.loop_dir}/.skills/" if _ctx.loop_dir else "~/.loopflow/skills/ or ~/.agents/skills/"
                        raise RuntimeError(
                            f"Skills not found: {', '.join(missing)}. "
                            f"Install them to {skills_dir_hint}"
                        )
                    skill_section = build_skill_prompt(ad.skills, _ctx.loop_dir)
                    if skill_section:
                        resolved_prompt = f"{skill_section}\n\n{resolved_prompt}"

                # Auto-detect model from agent definition
                if model is None and ad.model is not None:
                    model = ad.model

    # Inject schema into prompt so the agent knows the expected output format
    if schema:
        import json as json_mod
        schema_hint = (
            f"\n\n---\n"
            f"Output format — you MUST respond with a single JSON object "
            f"matching this schema:\n{json_mod.dumps(schema, indent=2)}\n\n"
            f"Do NOT wrap the JSON in markdown code blocks. "
            f"Return ONLY the JSON object."
        )
        resolved_prompt = resolved_prompt + schema_hint

    # Goal mode: delegate to goal loop or native goal
    if goal:
        if _backend_supports_native_goal(backend):
            # Backend handles /goal internally — prepend to prompt, single call
            resolved_prompt = f"/goal {goal}\n\n{resolved_prompt}"
            # Fall through to normal single-call flow (no __goal schema)
        else:
            return _run_with_goal(
                resolved_prompt=resolved_prompt,
                schema=schema,
                goal=goal,
                goal_max_iterations=goal_max_iterations,
                max_retries=max_retries,
                backend=backend,
                model=model,
                isolation=isolation,
                ad=ad,
                agent_def=agent_def,
                cache_path=cache_path,
            )

    # Retry loop for schema compliance
    retry_hint = ""
    for attempt in range(max_retries + 1):
        if attempt > 0:
            _emit_log(f"JSON parse failed, retrying ({attempt}/{max_retries})...")
            retry_hint = (
                f"\n\n---\n"
                f"Your previous response was not valid JSON. "
                f"Please respond with ONLY a JSON object matching the schema above."
            )

        # Resume: skip if already completed (first attempt only)
        if _ctx.resume and attempt == 0:
            cached = _ctx.try_resume()
            if cached is not None:
                if schema:
                    try:
                        return json.loads(cached)
                    except json.JSONDecodeError:
                        pass  # Cached result invalid, fall through to retry
                else:
                    return cached

        t0 = time.time()

        if _mock_mode == "auto":
            _write_event({"type": "agent_start", "session": session, "phase": _ctx._current_phase})
            text, exit_code = _run_mock_auto(schema)
        elif _mock_mode == "bash":
            _write_event({"type": "agent_start", "session": session, "phase": _ctx._current_phase})
            text, exit_code = _run_mock(resolved_prompt + retry_hint)
            # Mock bash mode: shell commands may fail on non-shell prompts.
            # Treat non-zero exit as empty output, not infra failure.
            if exit_code != 0:
                text = ""
        else:
            # Create worktree for isolation (only on first attempt)
            cwd = None
            if isolation == "worktree" and attempt == 0:
                cwd = _create_worktree(_ctx.run_id, _ctx._counter)
                if cwd:
                    _emit_log(f"Worktree: {cwd}")

            # Infra retry loop: transient errors get retried with exponential backoff
            for infra_attempt in range(len(INFRA_BACKOFF) + 1):
                if attempt > 0 or infra_attempt > 0:
                    session = _ctx.next_session()
                _write_event({"type": "agent_start", "session": session, "phase": _ctx._current_phase})
                events = _run_subagent(
                    resolved_prompt + retry_hint,
                    session,
                    backend=backend,
                    model=model,
                    cwd=cwd,
                    agent_def=ad if ad else None,
                    cache_path=cache_path,
                )
                exit_code = _extract_exit_code(events)
                text = _extract_text(events) if exit_code == 0 else ""

                if exit_code == 0:
                    break  # Success

                stderr = _extract_stderr(events)
                if infra_attempt < len(INFRA_BACKOFF) and _is_transient_error(stderr):
                    delay = INFRA_BACKOFF[infra_attempt]
                    reason = _transient_reason(stderr)
                    _write_event({
                        "type": "agent_retry",
                        "session": session,
                        "attempt": infra_attempt + 1,
                        "reason": reason,
                        "delay": delay,
                    })
                    _emit_log(
                        f"Agent infra error ({reason}), "
                        f"retrying in {delay}s ({infra_attempt + 1}/{len(INFRA_BACKOFF)})..."
                    )
                    time.sleep(delay)
                    continue

                # Non-transient or retries exhausted → raise
                from loopflow.agent import AgentError
                msg = f"Agent call failed with exit code {exit_code}"
                if stderr:
                    msg += f"\nStderr: {stderr}"
                if infra_attempt >= len(INFRA_BACKOFF):
                    msg = (
                        f"Agent call failed after {len(INFRA_BACKOFF)} infra retries: "
                        f"{msg}"
                    )
                raise AgentError(msg)

        # Schema compliance check
        if schema:
            try:
                result = json.loads(text)
                # Write cache on success
                _write_cache(cache_path, session, exit_code, text)
                _persist_state()
                return result
            except json.JSONDecodeError:
                # Best-effort extraction from text-mode responses
                from loopflow.agent import extract_json
                extracted = extract_json(text, schema)
                if extracted is not None:
                    _write_cache(cache_path, session, exit_code, text)
                    _persist_state()
                    return extracted
                if attempt >= max_retries:
                    from loopflow.agent import AgentError
                    raise AgentError(
                        f"Agent failed to return valid JSON after "
                        f"{max_retries} retries"
                    )
                continue

        # No schema → return text
        _write_cache(cache_path, session, exit_code, text)
        _persist_state()
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