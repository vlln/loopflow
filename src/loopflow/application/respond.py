"""Shared intervention respond + recover path (ADR-0056 §1/§2).

The Web handlers and the CLI (`loopflow respond`, foreground inline answering)
both funnel through `respond_and_recover` so response validation, persistence
(`answer_requests`) and recovery semantics never drift between channels.
"""

from __future__ import annotations

from typing import Any

from loopflow.infrastructure.intervention import (
    InterventionAlreadyAnswered,
    InterventionNotFound,
    InterventionValidationError,
    answer_requests,
    read_request,
)
from loopflow.infrastructure.web_storage import RunRepository, read_json


def respond_and_recover(
    runs: RunRepository,
    executor: Any,
    run_id: str,
    responses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist intervention responses for a waiting Run and start its recovery.

    Mirrors the semantics the Web respond endpoints have always had: batch
    validation first (nothing persists on any failure), Run must be
    waiting_input/cancelled, recovery mode is continue when any answered
    request has resume_mode=continue, retry/replay otherwise.
    """
    from loopflow.application.web import ApplicationError

    run_dir = runs.find(run_id)
    if run_dir is None:
        raise ApplicationError("run_not_found", f"Run '{run_id}' was not found")
    try:
        existing = []
        seen: set[str] = set()
        if not responses:
            raise InterventionValidationError("responses must be a non-empty array")
        for item in responses:
            if not isinstance(item, dict):
                raise InterventionValidationError("each response must be an object")
            request_id = item.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                raise InterventionValidationError("request_id is required")
            if request_id in seen:
                raise InterventionValidationError("duplicate request_id")
            seen.add(request_id)
            existing.append(read_request(run_dir, request_id))
        for item in existing:
            if item.get("status") == "answered" or "response" in item:
                raise InterventionAlreadyAnswered(str(item.get("request_id")))
        status = runs.read_summary(run_dir)["status"]
        if status not in {"waiting_input", "cancelled"}:
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' is not waiting for input")
        answered = answer_requests(run_dir, run_id, responses)
    except InterventionNotFound as error:
        raise ApplicationError("intervention_not_found", f"Intervention '{error}' was not found") from error
    except InterventionAlreadyAnswered as error:
        raise ApplicationError("intervention_already_answered", f"Intervention '{error}' was already answered") from error
    except InterventionValidationError as error:
        raise ApplicationError("validation_failed", str(error)) from error
    if executor is None:
        raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
    metadata = read_json(run_dir / "run.json")
    mode = "continue" if any(item.get("resume_mode") == "continue" for item in answered) else "retry"
    if mode == "continue":
        request = next(item for item in answered if item.get("resume_mode") == "continue")
        metadata["failed_call_id"] = request.get("call_id")
        metadata["failed_session_id"] = request.get("session_id")
        metadata["can_recover_continue"] = True
        try:
            runs.write_metadata(run_dir, metadata)
        except OSError as error:
            raise ApplicationError("atomic_write_failed", str(error)) from error
    try:
        returned = executor.start(
            metadata["loop"],
            metadata.get("args", {}),
            {"recover": True, "recovery_mode": mode},
            run_id=run_id,
        )
    except RuntimeError as error:
        if str(error) == "replay_diverged":
            raise ApplicationError("replay_diverged", f"Run '{run_id}' replay diverged") from error
        if str(error) == "continue_not_supported":
            raise ApplicationError("continue_not_supported", f"Run '{run_id}' cannot continue its session") from error
        if str(error) == "invalid_run_transition":
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' already has a worker") from error
        raise
    if returned != run_id:
        raise ApplicationError("internal_error", "Executor changed run_id during intervention response")
    return runs.read_summary(run_dir)
