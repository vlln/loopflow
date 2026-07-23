from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator


NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INTEGER = {"type": ["integer", "null"]}

RUN_SUMMARY_V13_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "run_id",
        "working_directory",
        "loop",
        "status",
        "current_phase",
        "created",
        "started_at",
        "finished_at",
        "updated_at",
        "duration_ms",
        "iteration_count",
        "error_summary",
        "parse_error",
        "execution_epoch",
        "allowed_actions",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "working_directory": {"type": "string"},
        "loop": NULLABLE_STRING,
        "status": {
            "enum": [
                "running",
                "waiting_input",
                "cancelling",
                "cancelled",
                "done",
                "failed",
                "stopped",
                "stale",
                "unreadable",
            ]
        },
        "current_phase": NULLABLE_STRING,
        "created": NULLABLE_STRING,
        "started_at": NULLABLE_STRING,
        "finished_at": NULLABLE_STRING,
        "updated_at": NULLABLE_STRING,
        "duration_ms": NULLABLE_INTEGER,
        "iteration_count": {"type": "integer", "minimum": 0},
        "error_summary": NULLABLE_STRING,
        "parse_error": NULLABLE_STRING,
        "execution_epoch": NULLABLE_INTEGER,
        "allowed_actions": {
            "type": "array",
            "uniqueItems": True,
            "items": {
                "enum": [
                    "stop",
                    "recover_retry",
                    "recover_continue",
                    "respond",
                    "rerun",
                    "reconcile",
                ]
            },
        },
    },
}

AGENT_CALL_V13_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "call_id",
        "phase_id",
        "session",
        "status",
        "started_at",
        "finished_at",
        "exit_code",
        "backend",
        "model",
        "input_digest",
    ],
    "properties": {
        "call_id": {"type": "string"},
        "phase_id": {"type": "string"},
        "session": NULLABLE_STRING,
        "status": {
            "enum": [
                "pending",
                "running",
                "succeeded",
                "failed",
                "retrying",
                "waiting_input",
                "blocked",
            ]
        },
        "started_at": NULLABLE_STRING,
        "finished_at": NULLABLE_STRING,
        "exit_code": NULLABLE_INTEGER,
        "backend": NULLABLE_STRING,
        "model": NULLABLE_STRING,
        "input_digest": NULLABLE_STRING,
    },
}

INTERVENTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "request_id",
        "key",
        "prompt",
        "schema",
        "status",
        "call_id",
        "resume_mode",
        "can_continue_session",
        "created_at",
        "answered_at",
    ],
    "properties": {
        "request_id": {"type": "string"},
        "key": {"type": "string", "minLength": 1},
        "prompt": {"type": "string", "minLength": 1},
        "schema": {"type": ["object", "null"]},
        "status": {"enum": ["pending", "answered", "closed"]},
        "call_id": NULLABLE_STRING,
        "resume_mode": {"enum": ["replay", "continue"]},
        "can_continue_session": {"type": "boolean"},
        "response": {},
        "created_at": {"type": "string"},
        "answered_at": NULLABLE_STRING,
    },
    "allOf": [
        {
            "if": {"properties": {"status": {"const": "answered"}}},
            "then": {"required": ["response"]},
            "else": {"not": {"required": ["response"]}},
        }
    ],
}

BACKEND_CAPABILITIES_V13_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "native_goal",
        "structured_output",
        "native_skills",
        "resume_session",
        "durable_session_id",
    ],
    "properties": {
        "native_goal": {"type": "boolean"},
        "structured_output": {"type": "boolean"},
        "native_skills": {"type": "boolean"},
        "resume_session": {"type": "boolean"},
        "durable_session_id": {"type": "boolean"},
    },
}

SCHEMAS = {
    "run_summary_v13": RUN_SUMMARY_V13_SCHEMA,
    "agent_call_v13": AGENT_CALL_V13_SCHEMA,
    "intervention": INTERVENTION_SCHEMA,
    "backend_capabilities_v13": BACKEND_CAPABILITIES_V13_SCHEMA,
}


def validate_contract(name: str, value: Any) -> None:
    Draft202012Validator(SCHEMAS[name]).validate(value)


def contract_examples() -> dict[str, dict[str, Any]]:
    return {
        "run_summary_v13": {
            "run_id": "run-1",
            "working_directory": "/fixture/project",
            "loop": "hello",
            "status": "waiting_input",
            "current_phase": "Review",
            "created": "2026-07-22T08:00:00Z",
            "started_at": "2026-07-22T08:00:00Z",
            "finished_at": None,
            "updated_at": "2026-07-22T08:00:00Z",
            "duration_ms": 10,
            "iteration_count": 0,
            "error_summary": None,
            "parse_error": None,
            "execution_epoch": 2,
            "allowed_actions": ["respond", "stop"],
        },
        "agent_call_v13": {
            "call_id": "0003.0000.0001",
            "phase_id": "phase-1",
            "session": "session-1",
            "status": "waiting_input",
            "started_at": "2026-07-22T08:00:00Z",
            "finished_at": None,
            "exit_code": None,
            "backend": "mock",
            "model": None,
            "input_digest": "sha256:abc",
        },
        "intervention": {
            "request_id": "request-1",
            "key": "approve",
            "prompt": "Approve?",
            "schema": {"type": "boolean"},
            "status": "pending",
            "call_id": None,
            "resume_mode": "replay",
            "can_continue_session": False,
            "created_at": "2026-07-22T08:00:00Z",
            "answered_at": None,
        },
        "backend_capabilities_v13": {
            "native_goal": False,
            "structured_output": False,
            "native_skills": False,
            "resume_session": True,
            "durable_session_id": True,
        },
    }
