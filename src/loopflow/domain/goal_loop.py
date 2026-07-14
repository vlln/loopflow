"""Goal loop domain service — iterate until complete or blocked."""

from __future__ import annotations

import json as json_mod
from typing import Any, Callable

from loopflow.domain.agent_def import GoalBlocked
from loopflow.domain.marshalling import add_goal_to_schema, build_goal_steering

# Callable type: (prompt, session, resume_session_id) -> (result, backend_session_id)
CallFn = Callable[[str, str, str | None], tuple[dict | str, str | None]]


def run_goal_loop(
    resolved_prompt: str,
    schema: dict | None,
    goal: str,
    goal_max_iterations: int,
    call_fn: CallFn,
    emit_log: Callable[[str], None] | None = None,
) -> Any:
    """Run goal loop: iterate until complete or blocked.

    call_fn(prompt, session, resume_session_id) -> (result, backend_sid)
    """
    goal_schema = add_goal_to_schema(schema)

    session = "goal_1"
    resume_session_id: str | None = None
    blocked_reason: str | None = None
    blocked_count = 0

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
            f"{json_mod.dumps(goal_schema, indent=2)}\n\n"
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
            _log(f"Goal iter {iteration}: JSON parse error, retrying...")
            continue

        # Extract goal state
        goal_state: dict = result.pop("__goal", {}) if isinstance(result, dict) else {}
        status = goal_state.get("status", "active")

        if status == "complete":
            return result

        if status == "blocked":
            reason = goal_state.get("reason") or "unknown"
            if reason == blocked_reason:
                blocked_count += 1
            else:
                blocked_reason = reason
                blocked_count = 1
            _log(f"Goal blocked ({blocked_count}/3): {reason}")
            if blocked_count >= 3:
                raise GoalBlocked(
                    f"Goal blocked after {iteration} iterations: "
                    f"{reason} (3 consecutive identical reasons)"
                )

        # Setup for next iteration
        resume_session_id = backend_sid
        session = f"goal_{iteration + 1}"

    raise GoalBlocked(
        f"Goal not completed after {goal_max_iterations} iterations"
    )