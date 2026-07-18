from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator


NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INTEGER = {"type": ["integer", "null"]}

RUN_SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "run_id",
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
        "allowed_actions",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "loop": NULLABLE_STRING,
        "status": {"enum": ["running", "done", "failed", "stopped", "stale", "unreadable"]},
        "current_phase": NULLABLE_STRING,
        "created": NULLABLE_STRING,
        "started_at": NULLABLE_STRING,
        "finished_at": NULLABLE_STRING,
        "updated_at": NULLABLE_STRING,
        "duration_ms": NULLABLE_INTEGER,
        "iteration_count": {"type": "integer", "minimum": 0},
        "error_summary": NULLABLE_STRING,
        "parse_error": NULLABLE_STRING,
        "allowed_actions": {
            "type": "array",
            "uniqueItems": True,
            "items": {"enum": ["stop", "resume", "rerun", "reconcile"]},
        },
    },
}

ERROR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code", "message", "details"],
            "properties": {
                "code": {"type": "string", "minLength": 1},
                "message": {"type": "string", "minLength": 1},
                "details": {"type": "object"},
            },
        }
    },
}

LOOP_SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "description", "agent_count", "triggers", "valid", "error_summary"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "agent_count": {"type": "integer", "minimum": 0},
        "triggers": {"type": "array", "items": {"type": "object"}},
        "valid": {"type": "boolean"},
        "error_summary": NULLABLE_STRING,
    },
}

QUEUE_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "task_id",
        "loop",
        "args",
        "resources",
        "priority",
        "created",
        "blocked_resources",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "loop": {"type": "string"},
        "args": {"type": "object"},
        "resources": {"type": "object", "additionalProperties": {"type": "string"}},
        "priority": {"type": "integer", "minimum": 0, "maximum": 100},
        "created": {"type": "string"},
        "blocked_resources": {"type": "array", "items": {"type": "string"}},
    },
}

BACKEND_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "name",
        "status",
        "reason",
        "cli_path",
        "version",
        "transport",
        "capabilities",
        "diagnosed_at",
    ],
    "properties": {
        "name": {"type": "string"},
        "status": {"type": "string"},
        "reason": NULLABLE_STRING,
        "cli_path": NULLABLE_STRING,
        "version": NULLABLE_STRING,
        "transport": {"type": "string"},
        "capabilities": {
            "type": "object",
            "additionalProperties": False,
            "required": ["native_goal", "structured_output", "native_skills"],
            "properties": {
                "native_goal": {"type": "boolean"},
                "structured_output": {"type": "boolean"},
                "native_skills": {"type": "boolean"},
            },
        },
        "diagnosed_at": NULLABLE_STRING,
    },
}

DIAGNOSTIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "status", "reason", "exit_code", "stdout", "stderr", "diagnosed_at"],
    "properties": {
        "name": {"type": "string"},
        "status": {"type": "string"},
        "reason": NULLABLE_STRING,
        "exit_code": NULLABLE_INTEGER,
        "stdout": {"type": "string"},
        "stderr": {"type": "string"},
        "diagnosed_at": {"type": "string"},
    },
}

V2_EVENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "event_id", "type", "ts", "run_id", "payload"],
    "properties": {
        "version": {"const": 2},
        "event_id": {"type": "integer", "minimum": 1},
        "type": {"type": "string"},
        "ts": {"type": "string"},
        "run_id": {"type": "string"},
        "phase": {"type": "string"},
        "phase_id": {"type": "string"},
        "call_id": {"type": "string"},
        "payload": {"type": "object"},
    },
}

SCHEMAS = {
    "run_summary": RUN_SUMMARY_SCHEMA,
    "error": ERROR_SCHEMA,
    "loop_summary": LOOP_SUMMARY_SCHEMA,
    "queue_item": QUEUE_ITEM_SCHEMA,
    "backend": BACKEND_SCHEMA,
    "diagnostic": DIAGNOSTIC_SCHEMA,
    "v2_event": V2_EVENT_SCHEMA,
}


def validate_contract(name: str, value: Any) -> None:
    Draft202012Validator(SCHEMAS[name]).validate(value)


def contract_examples() -> dict[str, dict[str, Any]]:
    return {
        "run_summary": {
            "run_id": "run-1",
            "loop": "hello",
            "status": "running",
            "current_phase": "Review",
            "created": "2026-07-18T22:00:00Z",
            "started_at": "2026-07-18T22:00:00Z",
            "finished_at": None,
            "updated_at": "2026-07-18T22:00:00Z",
            "duration_ms": 10,
            "iteration_count": 0,
            "error_summary": None,
            "parse_error": None,
            "allowed_actions": ["stop"],
        },
        "error": {"error": {"code": "run_not_found", "message": "not found", "details": {}}},
        "loop_summary": {
            "name": "hello",
            "description": "Fixture",
            "agent_count": 1,
            "triggers": [],
            "valid": True,
            "error_summary": None,
        },
        "queue_item": {
            "task_id": "task-1",
            "loop": "hello",
            "args": {},
            "resources": {},
            "priority": 5,
            "created": "2026-07-18T22:00:00Z",
            "blocked_resources": [],
        },
        "backend": {
            "name": "mock",
            "status": "available",
            "reason": None,
            "cli_path": "/fixture/mock",
            "version": "1.0.0",
            "transport": "cli",
            "capabilities": {
                "native_goal": True,
                "structured_output": False,
                "native_skills": True,
            },
            "diagnosed_at": None,
        },
        "diagnostic": {
            "name": "mock",
            "status": "unavailable",
            "reason": "timeout",
            "exit_code": None,
            "stdout": "",
            "stderr": "diagnostic timed out after 100ms",
            "diagnosed_at": "2026-07-18T22:00:00Z",
        },
        "v2_event": {
            "version": 2,
            "event_id": 1,
            "type": "phase",
            "ts": "2026-07-18T22:00:00Z",
            "run_id": "run-1",
            "phase": "Review",
            "phase_id": "phase-1",
            "payload": {"occurrence": 1},
        },
    }
