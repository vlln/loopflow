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
    resume_mode: str
    source: str = "workflow"
    options: tuple[str, ...] = ()
    allow_custom: bool = True
    schema: dict[str, Any] | None = None
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
    answers = [
        read_request(run_dir, str(item["request_id"]))
        for item in list_requests(run_dir)
        if item.get("call_id") == call_id and item.get("status") == "answered"
    ]
    if len(answers) == 1:
        return answers[0]
    if answers:
        return {
            "responses": [
                {
                    "key": item.get("key"),
                    "prompt": item.get("prompt"),
                    "response": item.get("response"),
                }
                for item in answers
            ]
        }
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
    request_id = _request_id_for_identity(identity)
    path = request_path(run_dir, request_id)
    prompt_digest = stable_digest(identity.prompt)
    schema_digest = stable_digest(
        {
            "schema": identity.schema,
            "options": list(identity.options),
            "allow_custom": identity.allow_custom,
            "source": identity.source,
        }
    )
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
        "source": identity.source,
        "prompt": identity.prompt,
        "prompt_digest": prompt_digest,
        "options": list(identity.options),
        "allow_custom": identity.allow_custom,
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
    return answer_requests(run_dir, run_id, [{"request_id": request_id, "response": response}])[0]


def answer_requests(run_dir: Path, run_id: str, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not responses:
        raise InterventionValidationError("responses must be a non-empty array")
    seen: set[str] = set()
    prepared: list[tuple[str, dict[str, Any], Any]] = []
    for item in responses:
        if not isinstance(item, dict):
            raise InterventionValidationError("each response must be an object")
        request_id = item.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise InterventionValidationError("request_id is required")
        if request_id in seen:
            raise InterventionValidationError("duplicate request_id")
        seen.add(request_id)
        response = item.get("response")
        request = read_request(run_dir, request_id)
        if request.get("status") == "answered" or "response" in request:
            raise InterventionAlreadyAnswered(request_id)
        if request.get("status") != "pending":
            raise InterventionNotFound(request_id)
        validate_response(request, response)
        prepared.append((request_id, request, _normalize_response(request, response)))

    answered_items: list[dict[str, Any]] = []
    answered_at = now_iso()
    for request_id, request, response in prepared:
        answered = dict(request)
        answered.update({
            "status": "answered",
            "response": response,
            "responded_at": answered_at,
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
        answered_items.append(answered)
    return answered_items


def validate_response(request_or_schema: Any, response: Any) -> None:
    if isinstance(request_or_schema, dict) and (
        "options" in request_or_schema or "allow_custom" in request_or_schema or "schema" in request_or_schema
    ):
        request = request_or_schema
        if _is_legacy_boolean_request(request):
            if isinstance(response, bool):
                return
            if isinstance(response, str) and response in {"true", "false"}:
                return
            raise InterventionValidationError("response must match one of the request options")
        if request.get("source") == "agent" or "options" in request or "allow_custom" in request:
            raw_options = request.get("options", [])
            if not isinstance(raw_options, list) or any(not isinstance(item, str) for item in raw_options):
                raise InterventionValidationError("options must be a string array")
            if not isinstance(response, str) or not response:
                raise InterventionValidationError("response must be a non-empty string")
            options = _effective_options(request)
            allow_custom = _effective_allow_custom(request)
            if not allow_custom and response not in options:
                raise InterventionValidationError("response must match one of the request options")
            return
        schema = request.get("schema")
    else:
        schema = request_or_schema
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
    can_continue_session = bool(
        request.get("resume_mode") == "continue" and request.get("session_id")
    )
    summary = {
        "request_id": request.get("request_id"),
        "source": request.get("source", "workflow" if request.get("resume_mode") == "replay" else "agent"),
        "key": request.get("key"),
        "prompt": request.get("prompt"),
        "options": _effective_options(request),
        "allow_custom": _effective_allow_custom(request),
        "status": request.get("status"),
        "resume_mode": request.get("resume_mode"),
        "call_id": request.get("call_id"),
        "can_continue_session": can_continue_session,
        "created_at": request.get("created_at"),
        "responded_at": request.get("responded_at"),
    }
    if request.get("status") == "answered" and "response" in request:
        summary["response"] = _response_to_string(request.get("response"))
    return summary


def _options_from_schema(schema: Any) -> list[str]:
    if isinstance(schema, dict) and schema.get("type") == "boolean":
        return ["true", "false"]
    return []


def _effective_options(request: dict[str, Any]) -> list[str]:
    options = request.get("options")
    if isinstance(options, list) and options:
        return options
    return _options_from_schema(request.get("schema"))


def _effective_allow_custom(request: dict[str, Any]) -> bool:
    options = request.get("options")
    if isinstance(options, list) and options:
        return bool(request.get("allow_custom", True))
    if _options_from_schema(request.get("schema")):
        return False
    return bool(request.get("allow_custom", request.get("schema") is None))


def _is_legacy_boolean_request(request: dict[str, Any]) -> bool:
    return request.get("source", "workflow") == "workflow" and isinstance(request.get("schema"), dict) and request["schema"].get("type") == "boolean" and not (isinstance(request.get("options"), list) and request.get("options"))


def _normalize_response(request: dict[str, Any], response: Any) -> Any:
    if _is_legacy_boolean_request(request) and isinstance(response, str):
        if response == "true":
            return True
        if response == "false":
            return False
    return response


def _response_to_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


def _request_id_for_identity(identity: InterventionIdentity) -> str:
    if identity.source == "agent" and identity.call_id:
        slug_key = f"{identity.call_id}-{identity.key}"
        digest_key: Any = {
            "source": identity.source,
            "call_id": identity.call_id,
            "key": identity.key,
        }
        slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", slug_key).strip("-")[:40] or "request"
        digest = stable_digest(digest_key).split(":", 1)[1][:12]
        return f"{slug}-{digest}"
    return request_id_for(identity.key)
