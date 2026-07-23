"""Persistent human intervention requests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loopflow.infrastructure.recovery import ReplayDiverged, stable_digest
from loopflow.infrastructure.web_events import EventWriter
from loopflow.infrastructure.web_storage import atomic_write_json, now_iso, read_json


class InterventionPending(RuntimeError):
    def __init__(self, request: dict[str, Any]) -> None:
        super().__init__("intervention_pending")
        self.request = request


class InterventionAlreadyAnswered(RuntimeError):
    pass


class InterventionNotFound(RuntimeError):
    pass


class InterventionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class InterventionIdentity:
    key: str
    prompt: str
    schema: dict[str, Any] | None
    resume_mode: str
    call_id: str | None = None
    session_id: str | None = None


def request_id_for(key: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", key).strip("-")[:40] or "request"
    digest = stable_digest({"key": key}).split(":", 1)[1][:12]
    return f"{slug}-{digest}"


def request_path(run_dir: Path, request_id: str) -> Path:
    return run_dir / "interventions" / f"{request_id}.json"


def list_requests(run_dir: Path) -> list[dict[str, Any]]:
    root = run_dir / "interventions"
    if not root.is_dir():
        return []
    items = []
    for path in sorted(root.glob("*.json")):
        try:
            value = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            items.append(_summary(value))
    return items


def answered_for_call(run_dir: Path, call_id: str) -> dict[str, Any] | None:
    for item in list_requests(run_dir):
        if item.get("call_id") == call_id and item.get("status") == "answered":
            return read_request(run_dir, str(item["request_id"]))
    return None


def read_request(run_dir: Path, request_id: str) -> dict[str, Any]:
    path = request_path(run_dir, request_id)
    if not path.is_file():
        raise InterventionNotFound(request_id)
    value = read_json(path)
    if not isinstance(value, dict):
        raise InterventionNotFound(request_id)
    return value


def request_or_answer(run_dir: Path, run_id: str, identity: InterventionIdentity) -> Any:
    request_id = request_id_for(identity.key)
    path = request_path(run_dir, request_id)
    prompt_digest = stable_digest(identity.prompt)
    schema_digest = stable_digest(identity.schema)
    if path.is_file():
        current = read_request(run_dir, request_id)
        if (
            current.get("key") != identity.key
            or current.get("prompt_digest") != prompt_digest
            or current.get("schema_digest") != schema_digest
            or current.get("resume_mode") != identity.resume_mode
        ):
            raise ReplayDiverged(f"Intervention {identity.key} changed during replay")
        if current.get("status") == "answered":
            return current.get("response")
        raise InterventionPending(current)

    created = now_iso()
    request = {
        "request_id": request_id,
        "key": identity.key,
        "prompt": identity.prompt,
        "prompt_digest": prompt_digest,
        "schema": identity.schema,
        "schema_digest": schema_digest,
        "resume_mode": identity.resume_mode,
        "call_id": identity.call_id,
        "session_id": identity.session_id,
        "status": "pending",
        "created_at": created,
        "updated_at": created,
    }
    atomic_write_json(path, request)
    EventWriter().append(
        run_dir,
        "intervention_requested",
        run_id=run_id,
        call_id=identity.call_id,
        payload=_summary(request),
    )
    raise InterventionPending(request)


def answer_request(run_dir: Path, run_id: str, request_id: str, response: Any) -> dict[str, Any]:
    request = read_request(run_dir, request_id)
    if request.get("status") == "answered" or "response" in request:
        raise InterventionAlreadyAnswered(request_id)
    if request.get("status") != "pending":
        raise InterventionNotFound(request_id)
    validate_response(request.get("schema"), response)
    answered = dict(request)
    answered.update({
        "status": "answered",
        "response": response,
        "responded_at": now_iso(),
        "updated_at": now_iso(),
    })
    atomic_write_json(request_path(run_dir, request_id), answered)
    EventWriter().append(
        run_dir,
        "intervention_responded",
        run_id=run_id,
        call_id=answered.get("call_id"),
        payload={"request_id": request_id},
    )
    return answered


def validate_response(schema: Any, response: Any) -> None:
    if schema is None:
        return
    if not isinstance(schema, dict):
        raise InterventionValidationError("schema must be object or null")
    schema_type = schema.get("type")
    checks = {
        "boolean": lambda value: isinstance(value, bool),
        "string": lambda value: isinstance(value, str),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
    }
    if schema_type not in checks:
        raise InterventionValidationError("unsupported intervention schema")
    if not checks[schema_type](response):
        raise InterventionValidationError(f"response must be {schema_type}")


def _summary(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request.get("request_id"),
        "key": request.get("key"),
        "prompt": request.get("prompt"),
        "schema": request.get("schema"),
        "status": request.get("status"),
        "resume_mode": request.get("resume_mode"),
        "call_id": request.get("call_id"),
        "created_at": request.get("created_at"),
        "responded_at": request.get("responded_at"),
    }
