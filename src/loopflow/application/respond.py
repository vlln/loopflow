"""Shared intervention respond + recover path (ADR-0056 §1/§2).

The Web handlers and the CLI (`loopflow respond`, foreground inline answering)
both funnel through `respond_and_recover` so response validation, persistence
(`answer_requests`) and recovery semantics never drift between channels.
"""

from __future__ import annotations

import threading
from typing import Any

from loopflow.infrastructure.intervention import (
    InterventionAlreadyAnswered,
    InterventionNotFound,
    InterventionPersistenceError,
    InterventionValidationError,
    answer_requests,
    emit_answer_events,
    _normalize_group_fields,
    list_requests,
    read_request,
    restore_requests,
)
from loopflow.infrastructure.web_storage import (
    RunRepository,
    atomic_write_json,
    read_json,
)


_LOCKS_GUARD = threading.Lock()
_RESPOND_LOCKS: dict[str, threading.Lock] = {}


def _respond_lock(run_dir: Any) -> threading.Lock:
    key = str(run_dir.resolve())
    with _LOCKS_GUARD:
        return _RESPOND_LOCKS.setdefault(key, threading.Lock())


def respond_and_recover(
    runs: RunRepository,
    executor: Any,
    run_id: str,
    responses: list[dict[str, Any]],
) -> dict[str, Any]:
    from loopflow.application.web import ApplicationError

    run_dir = runs.find(run_id)
    if run_dir is None:
        raise ApplicationError("run_not_found", f"Run '{run_id}' was not found")
    with _respond_lock(run_dir):
        return _respond_and_recover_locked(runs, executor, run_id, responses)


def _respond_and_recover_locked(
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
        pending_ids = {
            str(item["request_id"])
            for item in list_requests(run_dir)
            if item.get("status") == "pending"
        }
        if seen != pending_ids:
            raise InterventionValidationError(
                "responses must exactly cover all current pending requests"
            )
        status = runs.read_summary(run_dir)["status"]
        if status not in {"waiting_input", "cancelled"}:
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' is not waiting for input")
        normalized_existing = _normalize_group_fields(existing)
        mode = "continue" if any(
            item.get("resume_mode") == "continue" for item in normalized_existing
        ) else "retry"
        targets: list[dict[str, Any]] = []
        if mode == "continue":
            groups: dict[str, dict[str, Any]] = {}
            for request in normalized_existing:
                if request.get("resume_mode") != "continue":
                    continue
                group_id = str(request.get("request_group_id") or "")
                target = {
                    "request_group_id": group_id,
                    "call_id": request.get("call_id"),
                    "session_id": request.get("session_id"),
                }
                previous = groups.setdefault(group_id, target)
                if previous != target or not all(target.values()):
                    raise InterventionValidationError(
                        "invalid intervention request group"
                    )
            targets = sorted(groups.values(), key=lambda item: str(item["call_id"]))
        if executor is None:
            raise ApplicationError(
                "invalid_run_transition", "Run execution is unavailable"
            )
        original_metadata = read_json(run_dir / "run.json")
        original_requests = {
            str(item["request_id"]): item for item in existing
        }
        answered_items = answer_requests(
            run_dir, run_id, responses, emit_events=False
        )
    except InterventionNotFound as error:
        raise ApplicationError("intervention_not_found", f"Intervention '{error}' was not found") from error
    except InterventionAlreadyAnswered as error:
        raise ApplicationError("intervention_already_answered", f"Intervention '{error}' was already answered") from error
    except InterventionValidationError as error:
        raise ApplicationError("validation_failed", str(error)) from error
    except OSError as error:
        raise ApplicationError("atomic_write_failed", str(error)) from error
    metadata = dict(original_metadata)
    metadata_written = False
    try:
        if mode == "continue":
            metadata["continue_targets"] = targets
            metadata["failed_call_id"] = targets[0]["call_id"]
            metadata["failed_session_id"] = targets[0]["session_id"]
            metadata["can_recover_continue"] = True
            runs.write_metadata(run_dir, metadata)
            metadata_written = True
        returned = executor.start(
            metadata["loop"],
            metadata.get("args", {}),
            {"recover": True, "recovery_mode": mode},
            run_id=run_id,
        )
    except BaseException as error:
        rollback_errors: list[str] = []
        try:
            restore_requests(run_dir, original_requests)
        except InterventionPersistenceError as rollback_error:
            rollback_errors.append(str(rollback_error))
        if metadata_written:
            try:
                atomic_write_json(run_dir / "run.json", original_metadata)
            except OSError as rollback_error:
                rollback_errors.append(f"run metadata rollback failed: {rollback_error}")
        if rollback_errors:
            raise ApplicationError(
                "atomic_write_failed", "; ".join(rollback_errors)
            ) from error
        if isinstance(error, OSError):
            raise ApplicationError("atomic_write_failed", str(error)) from error
        if not isinstance(error, RuntimeError):
            raise
        if str(error) == "replay_diverged":
            raise ApplicationError("replay_diverged", f"Run '{run_id}' replay diverged") from error
        if str(error) == "continue_not_supported":
            raise ApplicationError("continue_not_supported", f"Run '{run_id}' cannot continue its session") from error
        if str(error) == "invalid_run_transition":
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' already has a worker") from error
        raise
    if returned != run_id:
        raise ApplicationError("internal_error", "Executor changed run_id during intervention response")
    emit_answer_events(run_dir, run_id, answered_items)
    return runs.read_summary(run_dir)
