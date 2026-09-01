"""Goal loop domain service — iterate until complete or blocked."""

from __future__ import annotations

import json as json_mod
from dataclasses import dataclass, field
from typing import Any, Callable

from loopflow.domain.marshalling import (
    add_control_to_schema,
    add_goal_to_schema,
    build_goal_steering,
)

# Callable type: (prompt, session, resume_session_id) -> (result, backend_session_id)
CallFn = Callable[[str, str, str | None], tuple[dict | str, str | None]]


@dataclass(frozen=True)
class AgentResult:
    """Outcome of a single agent() call.

    Unified across all modes: normal, goal, loopflow goal loop, native goal.
    """

    status: str                # "complete" | "blocked" | "exhausted" | "paused"
    reason: str = ""           # failure reason (empty if complete)
    value: Any = None          # business result (None if not complete)
    turns: int = 1             # number of agent calls
    tokens: int | None = None  # total tokens consumed
    session_id: str | None = None  # backend session id（ADR-0058 rerun_loop
                                   # 回退恢复用；mock/无 backend 下为 None）


def run_goal_loop(
    resolved_prompt: str,
    schema: dict | None,
    goal: str,
    goal_max_iterations: int,
    call_fn: CallFn,
    emit_log: Callable[[str], None] | None = None,
    schema_max_retries: int = 3,
    control_schema: dict | None = None,
    initial_resume_session_id: str | None = None,
) -> AgentResult:
    """Run goal loop: iterate until complete or blocked.

    call_fn(prompt, session, resume_session_id) -> (result, backend_sid)

    Schema retry is managed at the goal loop level, not inside _execute_once.
    Each call_fn invocation uses max_retries=0 — the goal loop owns the retry
    budget globally across iterations.

    ``initial_resume_session_id``：首轮迭代恢复的外部会话 id（ADR-0058：
    rerun_loop 回退重跑 goal 模式阶段时复用上次会话）。返回的 AgentResult
    ``session_id`` 为**最近已知**的 backend sid（末次迭代若返回 None 则保留
    更早的非 None 会话——"最近可用会话"语义）。
    """

    goal_schema = add_goal_to_schema(schema)
    output_schema = add_control_to_schema(goal_schema) if control_schema else goal_schema

    session = "goal_1"
    resume_session_id: str | None = initial_resume_session_id
    blocked_reason: str | None = None
    blocked_count = 0
    schema_failures = 0
    last_sid: str | None = None

    def _log(msg: str) -> None:
        if emit_log:
            emit_log(msg)

    for iteration in range(1, goal_max_iterations + 1):
        steering = build_goal_steering(goal, iteration,
                                        goal_max_iterations)
        full_prompt = f"{steering}\n\n{resolved_prompt}"

        # Inject goal schema
        schema_hint = (
            f"\n\n---\nOutput format — you MUST respond with a single "
            f"JSON object matching this schema:\n"
            f"{json_mod.dumps(output_schema, indent=2)}\n\n"
            f"Do NOT wrap the JSON in markdown code blocks. "
            f"Return ONLY the JSON object."
        )

        try:
            result, backend_sid = call_fn(
                full_prompt + schema_hint, session, resume_session_id,
            )
        except Exception as e:
            msg = str(e)
            if "valid JSON" not in msg:
                raise
            schema_failures += 1
            _log(f"Goal iter {iteration}: JSON parse error "
                 f"({schema_failures}/{schema_max_retries}), retrying...")
            if schema_failures > schema_max_retries:
                raise
            # Propagate session so next iteration resumes the same session
            backend_sid = getattr(e, 'backend_sid', None)
            if backend_sid:
                resume_session_id = backend_sid
            continue

        # Valid JSON: extract goal state
        goal_state: dict = result.pop("__goal", {}) if isinstance(result, dict) else {}
        status = goal_state.get("status", "active")
        if backend_sid:
            last_sid = backend_sid

        if status == "complete":
            return AgentResult(status="complete", value=result, turns=iteration,
                               session_id=last_sid)

        if status == "blocked":
            reason = goal_state.get("reason") or "unknown"
            if reason == blocked_reason:
                blocked_count += 1
            else:
                blocked_reason = reason
                blocked_count = 1
            _log(f"Goal blocked ({blocked_count}/3): {reason}")
            if blocked_count >= 3:
                return AgentResult(
                    status="blocked",
                    reason=f"{reason} (3 consecutive identical reasons)",
                    turns=iteration,
                    session_id=last_sid,
                )

        # Setup for next iteration
        resume_session_id = backend_sid
        session = f"goal_{iteration + 1}"

    return AgentResult(
        status="exhausted",
        reason=f"Goal not completed after {goal_max_iterations} iterations",
        turns=goal_max_iterations,
        session_id=last_sid,
    )
