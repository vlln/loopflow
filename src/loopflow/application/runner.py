"""AgentRunner — Agent execution instance (application layer).

AgentRunner = AgentDef + Backend + RunContext.  Owns the full execution
lifecycle: marshal → execute → parse → return.  Normal path and goal
loop share _execute_once() as the unified execution path.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from loopflow.domain import (
    AgentDef,
    AgentError,
    Capabilities,
    AgentResult,
    add_goal_to_schema,
    build_goal_steering,
    extract_json,
    marshal,
    run_goal_loop,
)
from loopflow.infrastructure.intervention import (
    InterventionIdentity,
    answered_for_call,
    request_or_answer,
)


# ── infra retry patterns ────────────────────────────────────────────────────

INFRA_BACKOFF = [3, 9, 27]
_TRANSIENT_PATTERNS: list[tuple[str, str]] = [
    ("connection_error", "connection_error"),
    ("terminated", "terminated"),
    ("timeout", "timeout"),
    ("rate_limit", "rate_limit"),
    ("rate limited", "rate_limit"),
    ("timed out", "timeout"),
]

# Native goal exit codes (kimi/claude headless mode)
_GOAL_EXIT_CODES: dict[int, str] = {
    3: "blocked",
    6: "paused",
}


def _is_transient_error(stderr: str) -> bool:
    stderr_lower = stderr.lower()
    return any(pattern in stderr_lower for pattern, _ in _TRANSIENT_PATTERNS)


def _transient_reason(stderr: str) -> str:
    stderr_lower = stderr.lower()
    for pattern, reason in _TRANSIENT_PATTERNS:
        if pattern in stderr_lower:
            return reason
    return "unknown"


def _extract_exit_code(events: list[dict]) -> int:
    for evt in events:
        if evt.get("type") == "agent_done":
            return evt.get("exit_code", 0)
    return 1


def _extract_text(events: list[dict]) -> str:
    parts: list[str] = []
    for evt in events:
        t = evt.get("type")
        if t in ("agent_message", "agent_message_chunk", "agent_text"):
            parts.append(evt["content"])
    return "\n".join(parts)


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


# ── AgentRunner ─────────────────────────────────────────────────────────────

class AgentRunner:
    """Agent execution instance.

    Holds an AgentDef, a Backend instance, and a RunContext.
    Owns the full execution lifecycle: marshal → execute → parse → return.

    User-facing entry point is runtime.agent(); AgentRunner is the
    framework-level implementation.
    """

    def __init__(
        self,
        ad: AgentDef | None,
        backend: Any,
        ctx: Any,
        invoke_fn: Callable[..., list[dict]],
        log_fn: Callable[[str], None] | None = None,
        write_event_fn: Callable[[dict], None] | None = None,
        write_cache_fn: Callable[..., None] | None = None,
        persist_state_fn: Callable[[], None] | None = None,
        create_worktree_fn: Callable[[str, int], str | None] | None = None,
        mock_mode: str | None = None,
        mock_fn: Callable[[str], tuple[str, int]] | None = None,
        mock_auto_fn: Callable[[dict | None], tuple[str, int]] | None = None,
        backend_name: str | None = None,
    ):
        self.ad = ad
        self.backend = backend
        self.ctx = ctx
        self._invoke = invoke_fn
        self._log = log_fn or (lambda _: None)
        self._write_event = write_event_fn or (lambda _: None)
        self._write_cache = write_cache_fn or (lambda *a, **kw: None)
        self._persist_state = persist_state_fn or (lambda: None)
        self._create_worktree = create_worktree_fn
        self._mock_mode = mock_mode
        self._mock_fn = mock_fn
        self._mock_auto_fn = mock_auto_fn
        self.backend_name = backend_name

    # ── public API ──────────────────────────────────────────────────────

    def run(
        self,
        prompt: str,
        *,
        goal: str | None = None,
        model: str | None = None,
        schema: dict | None = None,
        isolation: str | None = None,
        max_retries: int = 3,
        goal_max_iterations: int = 10,
        **params: str,
    ) -> Any:
        """Run an agent call with full lifecycle.

        Args:
            prompt: The user task prompt.
            goal: Optional goal for feedback loop.
            model: Model override (agent def > explicit param).
            schema: Output schema override (agent def > explicit param).
            isolation: Worktree isolation mode.
            max_retries: Max JSON parse retries.
            goal_max_iterations: Max goal loop iterations.
            **params: Template parameters.

        Returns:
            Parsed dict (if schema) or raw text.
        """
        # 1. Marshal capabilities
        caps = self.backend.capabilities if self.backend else Capabilities()
        resolved, detected_schema, native_goal = marshal(
            self.ad, prompt,
            goal=goal,
            caps=caps,
            **params,
        )

        # 2. Schema: agent output > explicit parameter
        if schema is None and detected_schema is not None:
            schema = detected_schema

        # 3. Model: agent definition > explicit parameter
        if model is None and self.ad is not None and self.ad.model is not None:
            model = self.ad.model

        # 4. Skills check and injection
        if self.ad is not None and self.ad.skills:
            from loopflow.infrastructure.skills import build_skill_prompt, check_skills
            missing = check_skills(self.ad.skills, self.ctx.loop_dir)
            if missing:
                skills_dir_hint = (
                    f"{self.ctx.loop_dir}/.skills/"
                    if self.ctx.loop_dir
                    else "~/.loopflow/skills/ or ~/.agents/skills/"
                )
                raise RuntimeError(
                    f"Skills not found: {', '.join(missing)}. "
                    f"Install them to {skills_dir_hint}"
                )
            skill_section = build_skill_prompt(self.ad.skills, self.ctx.loop_dir)
            if skill_section:
                resolved = f"{skill_section}\n\n{resolved}"

        # 5. Schema hint injection (unless native goal handles it)
        if schema and not native_goal:
            schema_hint = (
                f"\n\n---\n"
                f"Output format — you MUST respond with a single JSON object "
                f"matching this schema:\n{json.dumps(schema, indent=2)}\n\n"
                f"Do NOT wrap the JSON in markdown code blocks. "
                f"Return ONLY the JSON object."
            )
            resolved = resolved + schema_hint

        # 6. Goal mode: loopflow goal loop
        if goal and not native_goal:
            goal_schema = add_goal_to_schema(schema)

            def _goal_call(p: str, s: str, rid: str | None) -> tuple[Any, str | None]:
                return self._execute_once(
                    p, goal_schema, model, isolation, 0,  # max_retries=0: goal loop owns retry
                    resume_session_id=rid,
                )

            return run_goal_loop(
                resolved, schema, goal, goal_max_iterations,
                _goal_call, self._log,
                schema_max_retries=max_retries,
            )

        # 7. Native goal: single call, wrap in AgentResult
        if native_goal:
            result, backend_sid = self._execute_once(
                resolved, schema, model, isolation, max_retries,
            )
            if isinstance(result, str) and result.startswith("Goal ["):
                return AgentResult(status="blocked", reason=result)
            return AgentResult(status="complete", value=result)

        # 8. Normal single call
        result = self._execute_once(
            resolved, schema, model, isolation, max_retries,
        )[0]
        return AgentResult(status="complete", value=result)

    # ── internal ─────────────────────────────────────────────────────────

    def _execute_once(
        self,
        prompt: str,
        schema: dict | None,
        model: str | None,
        isolation: str | None,
        max_retries: int,
        resume_session_id: str | None = None,
    ) -> tuple[dict | str, str | None]:
        """Unified single-call execution.

        Handles: resume, mock, worktree, infra retry, JSON parsing, caching.
        Used by both normal path and goal loop.

        Returns (result, backend_session_id).
        """
        session = self.ctx.next_session()
        call_id = self.ctx.current_call_id
        cache_path = self.ctx.call_cache_path(call_id)
        from loopflow.infrastructure.recovery import (
            ReplayDiverged,
            append_cache_event,
            call_input_digest,
            select_for_replay,
        )

        input_digest = call_input_digest(
            loop_dir=self.ctx.loop_dir,
            prompt=prompt,
            schema=schema,
            backend=self.backend_name,
            model=model,
            agent_definition=getattr(self.ad, "body", None),
            execution_options=self.ctx.execution_options,
        )

        # Resume: skip if already completed
        if self.ctx.resume and not resume_session_id:
            selection = select_for_replay(
                cache_path, call_id=call_id, input_digest=input_digest
            )
            target = self.ctx.recovery_target_call_id
            target_continue = (
                self.ctx.recovery_mode == "continue"
                and target is not None
                and target == call_id
                and not self.ctx.recovery_target_reached
            )
            if selection.outcome in {"hit", "legacy_hit"} and not target_continue:
                self.ctx.legacy_recovery = selection.outcome == "legacy_hit"
                cached = selection.segment.text
                if schema:
                    try:
                        return json.loads(cached), None
                    except json.JSONDecodeError:
                        pass
                else:
                    return cached, None
            is_target = not self.ctx.recovery_target_reached
            if is_target and target is not None and target != call_id:
                raise ReplayDiverged(
                    f"Recovery expected target {target}, reached uncommitted {call_id}"
                )
            if is_target:
                self.ctx.recovery_target_reached = True
            if is_target and self.ctx.recovery_mode == "continue":
                segment = selection.segment
                caps = self.backend.capabilities if self.backend else Capabilities()
                if (
                    segment is None
                    or not segment.session_id
                    or not getattr(caps, "resume_session", False)
                    or not getattr(caps, "durable_session_id", False)
                    or segment.legacy
                ):
                    raise RuntimeError("continue_not_supported")
                resume_session_id = segment.session_id
            if is_target:
                self.ctx.mark_recovery_ready()

        backend_prompt = prompt
        if resume_session_id:
            answered = answered_for_call(self.ctx.run_dir, call_id)
            if answered is not None:
                backend_prompt = json.dumps(answered.get("response"), ensure_ascii=False)

        start_type = "agent_resume" if resume_session_id else "agent_start"
        append_cache_event(
            cache_path,
            {
                "type": start_type,
                "call_id": call_id,
                "input_digest": input_digest,
                "session": session,
            },
        )

        retry_hint = ""

        for attempt in range(max_retries + 1):
            if attempt > 0:
                self._log(f"JSON parse failed, retrying ({attempt}/{max_retries})...")
                retry_hint = (
                    f"\n\n---\n"
                    f"Your previous response was not valid JSON. "
                    f"Please respond with ONLY a JSON object matching the "
                    f"schema above."
                )

            # Worktree
            cwd = None
            if isolation == "worktree" and attempt == 0 and self._create_worktree:
                cwd = self._create_worktree(self.ctx.run_id, self.ctx._counter)
                if cwd:
                    self._log(f"Worktree: {cwd}")

            if self._mock_mode:
                # Mock mode — no real backend call
                self._write_event({
                    "type": "agent_start",
                    "session": session,
                    "phase": getattr(self.ctx, '_current_phase', None),
                })
                if self._mock_mode == "auto":
                    text, exit_code = self._mock_auto_fn(schema)
                else:
                    text, exit_code = self._mock_fn(prompt + retry_hint)
                    if exit_code != 0:
                        text = ""
                backend_sid = None
            else:
                # Real backend call with infra retry
                text, exit_code, backend_sid = self._call_backend(
                    backend_prompt, retry_hint, session, model, cwd, cache_path,
                    resume_session_id, attempt, call_id, input_digest,
                )

                # Native goal: return goal summary text directly
                if exit_code in _GOAL_EXIT_CODES:
                    self._write_cache(cache_path, session, exit_code, text, call_id=call_id, input_digest=input_digest, session_id=backend_sid)
                    return text, backend_sid

            # Schema compliance check
            if schema:
                try:
                    result = json.loads(text)
                    self._write_cache(cache_path, session, exit_code, text, call_id=call_id, input_digest=input_digest, session_id=backend_sid)
                    self._handle_control_result(result, backend_sid, call_id)
                    self._persist_state()
                    return result, backend_sid
                except json.JSONDecodeError:
                    extracted = extract_json(text, schema)
                    if extracted is not None:
                        self._write_cache(cache_path, session, exit_code, text, call_id=call_id, input_digest=input_digest, session_id=backend_sid)
                        self._handle_control_result(extracted, backend_sid, call_id)
                        self._persist_state()
                        return extracted, backend_sid
                    if attempt >= max_retries:
                        err = AgentError(
                            f"Agent failed to return valid JSON after "
                            f"{max_retries} retries"
                        )
                        err.backend_sid = backend_sid
                        self._write_cache(cache_path, session, exit_code, text, call_id=call_id, input_digest=input_digest, status="failed", session_id=backend_sid)
                        raise err
                    continue

            # No schema → return text
            self._write_cache(cache_path, session, exit_code, text, call_id=call_id, input_digest=input_digest, session_id=backend_sid)
            self._handle_control_result(_maybe_json(text), backend_sid, call_id)
            self._persist_state()
            return text, backend_sid

        raise AgentError(f"Agent failed after {max_retries} retries")

    def _handle_control_result(
        self,
        result: Any,
        backend_sid: str | None,
        call_id: str,
    ) -> None:
        if not isinstance(result, dict):
            return
        control = result.get("__loopflow")
        if not isinstance(control, dict) or control.get("status") != "waiting_input":
            return
        key = control.get("key")
        prompt = control.get("prompt")
        schema = control.get("schema")
        if not isinstance(key, str) or not key or not isinstance(prompt, str) or not prompt:
            raise RuntimeError("validation_failed")
        if schema is not None and not isinstance(schema, dict):
            raise RuntimeError("validation_failed")
        caps = self.backend.capabilities if self.backend else Capabilities()
        if not (
            backend_sid
            and getattr(caps, "resume_session", False)
            and getattr(caps, "durable_session_id", False)
        ):
            raise RuntimeError("continue_not_supported")
        request_or_answer(
            self.ctx.run_dir,
            self.ctx.run_id,
            InterventionIdentity(
                key=key,
                prompt=prompt,
                schema=schema,
                resume_mode="continue",
                call_id=call_id,
                session_id=backend_sid,
            ),
        )

    def _call_backend(
        self,
        prompt: str,
        retry_hint: str,
        session: str,
        model: str | None,
        cwd: str | None,
        cache_path: Any,
        resume_session_id: str | None,
        attempt: int,
        call_id: str,
        input_digest: str,
    ) -> tuple[str, int, str | None]:
        """Real backend call with infra retry loop.

        Returns (text, exit_code, backend_session_id).
        Raises AgentError on non-transient failure.
        """
        for infra_attempt in range(len(INFRA_BACKOFF) + 1):
            if attempt > 0 or infra_attempt > 0:
                session = f"wf_{self.ctx.run_id}_{call_id}_retry_{attempt}_{infra_attempt}"

            if attempt > 0 or infra_attempt > 0:
                from loopflow.infrastructure.recovery import append_cache_event
                append_cache_event(
                    cache_path,
                    {
                        "type": "agent_resume" if resume_session_id else "agent_start",
                        "call_id": call_id,
                        "input_digest": input_digest,
                        "session": session,
                    },
                )

            self._write_event({
                "type": "agent_start",
                "session": session,
                "phase": getattr(self.ctx, '_current_phase', None),
            })

            events = self._invoke(
                prompt + retry_hint,
                session,
                model=model,
                cwd=cwd,
                agent_def=self.ad,
                cache_path=cache_path,
                resume_session_id=resume_session_id,
                call_id=call_id,
            )
            exit_code = _extract_exit_code(events)
            text = _extract_text(events) if exit_code == 0 else ""
            backend_sid = _extract_session_id(events)

            if exit_code == 0:
                return text, exit_code, backend_sid

            # Native goal: blocked(3) / paused(6) are expected outcomes
            if exit_code in _GOAL_EXIT_CODES:
                text = _extract_text(events)
                return text, exit_code, backend_sid

            stderr = _extract_stderr(events)
            if infra_attempt < len(INFRA_BACKOFF) and _is_transient_error(stderr):
                delay = INFRA_BACKOFF[infra_attempt]
                reason = _transient_reason(stderr)
                self._write_event({
                    "type": "agent_retry",
                    "session": session,
                    "attempt": infra_attempt + 1,
                    "reason": reason,
                    "delay": delay,
                })
                self._log(
                    f"Agent infra error ({reason}), "
                    f"retrying in {delay}s "
                    f"({infra_attempt + 1}/{len(INFRA_BACKOFF)})..."
                )
                time.sleep(delay)
                continue

            msg = f"Agent call failed with exit code {exit_code}"
            if stderr:
                msg += f"\nStderr: {stderr}"
            if infra_attempt >= len(INFRA_BACKOFF):
                msg = (
                    f"Agent call failed after {len(INFRA_BACKOFF)} "
                    f"infra retries: {msg}"
                )
            self._write_cache(
                cache_path,
                session,
                exit_code,
                "",
                call_id=call_id,
                input_digest=input_digest,
                status="failed",
                session_id=backend_sid,
            )
            self.ctx.failed_session_id = backend_sid
            caps = self.backend.capabilities if self.backend else Capabilities()
            self.ctx.failed_can_continue = bool(
                backend_sid
                and getattr(caps, "resume_session", False)
                and getattr(caps, "durable_session_id", False)
            )
            error = AgentError(msg)
            error.backend_sid = backend_sid
            raise error

        raise AgentError(
            f"Agent call failed after {len(INFRA_BACKOFF)} infra retries"
        )


def _maybe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
