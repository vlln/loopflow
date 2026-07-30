from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, ValidationError


NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INTEGER = {"type": ["integer", "null"]}

RUN_SUMMARY_SCHEMA = {
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
        "status": {"enum": ["running", "waiting_input", "cancelling", "cancelled", "done", "failed", "stopped", "stale", "unreadable"]},
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
            "items": {"enum": ["stop", "recover_retry", "recover_continue", "respond", "rerun", "reconcile"]},
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
        "declared_phases": {"type": "array", "items": {"type": "object"}},
        "declared_args": {
            "type": "array",
            "items": {"$ref": "#/$defs/declared_arg"},
        },
    },
    "$defs": {
        "declared_arg": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "pattern": ".*\\S.*"},
                "default": {},
                "description": {"type": "string"},
                "required": {"type": "boolean"},
            },
        }
    },
}

DECLARED_ARG_SCHEMA = LOOP_SUMMARY_SCHEMA["$defs"]["declared_arg"]

FILE_PREVIEW_SCHEMA = {
    "oneOf": [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["path", "media_type", "content", "size", "read_only"],
            "properties": {
                "path": {"type": "string"},
                "media_type": NULLABLE_STRING,
                "content": {"type": "string"},
                "size": {"type": "integer", "minimum": 0, "maximum": 1048576},
                "read_only": {"const": True},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "path",
                "media_type",
                "content",
                "size",
                "read_only",
                "encoding",
                "raw_url",
            ],
            "properties": {
                "path": {"type": "string"},
                "media_type": {
                    "enum": [
                        "image/png",
                        "image/jpeg",
                        "image/gif",
                        "image/svg+xml",
                        "image/webp",
                        "image/bmp",
                        "image/x-icon",
                        "application/pdf",
                    ]
                },
                "content": {"type": "null"},
                "size": {"type": "integer", "minimum": 0, "maximum": 52428800},
                "read_only": {"const": True},
                "encoding": {"const": "raw"},
                "raw_url": {"type": "string", "minLength": 1},
            },
        },
    ]
}

RUN_CREATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["loop"],
    "properties": {
        "loop": {"type": "string", "minLength": 1},
        "args": {"type": "object"},
        "backend": NULLABLE_STRING,
        "model": NULLABLE_STRING,
        "mock": {"enum": ["bash", "auto", None]},
        "from_phase": NULLABLE_STRING,
        "only_phase": NULLABLE_STRING,
        "working_directory": NULLABLE_STRING,
        "transport": {"enum": ["cli", "acp"]},
        "append_prompt": {"type": "string"},
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
        "status",
        "status_reason",
        "superseded_by",
        "blocked_resources",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "loop": {"type": "string"},
        "args": {"type": "object"},
        "resources": {"type": "object", "additionalProperties": {"type": "string"}},
        "priority": {"type": "integer", "minimum": 0, "maximum": 100},
        "created": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "deferred", "superseded"]},
        "status_reason": NULLABLE_STRING,
        "superseded_by": NULLABLE_STRING,
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
            "required": ["native_goal", "structured_output", "native_skills", "resume_session", "durable_session_id"],
            "properties": {
                "native_goal": {"type": "boolean"},
                "structured_output": {"type": "boolean"},
                "native_skills": {"type": "boolean"},
                "resume_session": {"type": "boolean"},
                "durable_session_id": {"type": "boolean"},
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

INTERVENTION_V18_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "request_id",
        "source",
        "key",
        "prompt",
        "schema",
        "options",
        "allow_custom",
        "status",
        "request_group_id",
        "request_index",
        "call_id",
        "session_id",
        "resume_mode",
        "can_continue_session",
        "created_at",
        "responded_at",
        "timeout_seconds",
    ],
    "properties": {
        "request_id": {"type": "string"},
        "source": {"enum": ["workflow", "agent"]},
        "key": {"type": "string", "minLength": 1},
        "prompt": {"type": "string", "minLength": 1},
        "schema": {"type": ["object", "null"]},
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "uniqueItems": True,
        },
        "allow_custom": {"type": "boolean"},
        "status": {"enum": ["pending", "answered", "closed"]},
        "request_group_id": NULLABLE_STRING,
        "request_index": {"type": "integer", "minimum": 0},
        "call_id": NULLABLE_STRING,
        "session_id": NULLABLE_STRING,
        "resume_mode": {"enum": ["replay", "continue"]},
        "can_continue_session": {"type": "boolean"},
        "response": {},
        "created_at": {"type": "string"},
        "responded_at": NULLABLE_STRING,
        "timeout_seconds": {"type": ["number", "null"], "exclusiveMinimum": 0},
        "response_source": {"enum": ["human", "default", "timeout_default"]},
    },
    "allOf": [
        {
            "if": {"properties": {"status": {"const": "answered"}}},
            "then": {"required": ["response", "response_source"]},
            "else": {
                "allOf": [
                    {"not": {"required": ["response"]}},
                    {"not": {"required": ["response_source"]}},
                ]
            },
        },
        {
            "if": {"properties": {"source": {"const": "workflow"}}},
            "then": {
                "properties": {
                    "request_group_id": {"type": "null"},
                    "request_index": {"const": 0},
                    "call_id": {"type": "null"},
                    "session_id": {"type": "null"},
                    "resume_mode": {"const": "replay"},
                }
            },
        },
        {
            "if": {"properties": {"source": {"const": "agent"}}},
            "then": {
                "properties": {
                    "request_group_id": {"type": "string", "minLength": 1},
                    "call_id": {"type": "string", "minLength": 1},
                    "session_id": {"type": "string", "minLength": 1},
                    "resume_mode": {"const": "continue"},
                    "can_continue_session": {"const": True},
                    "timeout_seconds": {"type": "null"},
                }
            },
        },
    ],
}

# Kept for pre-v18 implementation tests until DEVELOP migrates the API read model.
INTERVENTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "request_id",
        "source",
        "key",
        "prompt",
        "options",
        "allow_custom",
        "status",
        "call_id",
        "resume_mode",
        "can_continue_session",
        "created_at",
        "responded_at",
    ],
    "properties": {
        "request_id": {"type": "string"},
        "source": {"enum": ["workflow", "agent"]},
        "key": {"type": "string", "minLength": 1},
        "prompt": {"type": "string", "minLength": 1},
        "options": {"type": "array", "items": {"type": "string"}},
        "allow_custom": {"type": "boolean"},
        "status": {"enum": ["pending", "answered", "closed"]},
        "call_id": NULLABLE_STRING,
        "resume_mode": {"enum": ["replay", "continue"]},
        "can_continue_session": {"type": "boolean"},
        "response": {},
        "created_at": {"type": "string"},
        "responded_at": NULLABLE_STRING,
        "default": {},
        "timeout_seconds": {"type": ["number", "null"]},
        "response_source": {"enum": ["human", "default", "timeout_default"]},
    },
    "allOf": [
        {
            "if": {"properties": {"status": {"const": "answered"}}},
            "then": {"required": ["response"]},
            "else": {"not": {"required": ["response"]}},
        }
    ],
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
    "declared_arg": DECLARED_ARG_SCHEMA,
    "file_preview": FILE_PREVIEW_SCHEMA,
    "run_create": RUN_CREATE_SCHEMA,
    "queue_item": QUEUE_ITEM_SCHEMA,
    "backend": BACKEND_SCHEMA,
    "diagnostic": DIAGNOSTIC_SCHEMA,
    "intervention": INTERVENTION_SCHEMA,
    "intervention_v18": INTERVENTION_V18_SCHEMA,
    "v2_event": V2_EVENT_SCHEMA,
}


def validate_contract(name: str, value: Any) -> None:
    Draft202012Validator(SCHEMAS[name]).validate(value)
    if name == "run_create" and len(value.get("append_prompt", "").encode("utf-8")) > 65536:
        raise ValidationError("append_prompt exceeds 65536 UTF-8 bytes")


def contract_examples() -> dict[str, dict[str, Any]]:
    return {
        "run_summary": {
            "run_id": "run-1",
            "working_directory": "/fixture/project",
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
            "execution_epoch": 1,
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
            "declared_phases": [],
            "declared_args": [
                {
                    "name": "topic",
                    "default": "rna",
                    "description": "Research topic",
                    "required": True,
                }
            ],
        },
        "declared_arg": {
            "name": "count",
            "default": 0,
            "description": "Maximum results",
            "required": False,
        },
        "file_preview": {
            "path": "figure.png",
            "media_type": "image/png",
            "content": None,
            "size": 1024,
            "read_only": True,
            "encoding": "raw",
            "raw_url": "/api/v1/runs/run-1/file/raw?path=figure.png",
        },
        "run_create": {
            "loop": "hello",
            "args": {},
            "append_prompt": "Read only",
        },
        "queue_item": {
            "task_id": "task-1",
            "loop": "hello",
            "args": {},
            "resources": {},
            "priority": 5,
            "created": "2026-07-18T22:00:00Z",
            "status": "pending",
            "status_reason": None,
            "superseded_by": None,
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
                "resume_session": True,
                "durable_session_id": True,
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
        "intervention": {
            "request_id": "approve-legacy",
            "source": "workflow",
            "key": "approve",
            "prompt": "Approve?",
            "options": ["true", "false"],
            "allow_custom": False,
            "status": "pending",
            "call_id": None,
            "resume_mode": "replay",
            "can_continue_session": False,
            "created_at": "2026-07-18T22:00:00Z",
            "responded_at": None,
        },
        "intervention_v18": {
            "request_id": "approve-1",
            "source": "workflow",
            "key": "approve",
            "prompt": "Approve?",
            "schema": {"type": "boolean"},
            "options": ["true", "false"],
            "allow_custom": False,
            "status": "pending",
            "request_group_id": None,
            "request_index": 0,
            "call_id": None,
            "session_id": None,
            "resume_mode": "replay",
            "can_continue_session": False,
            "created_at": "2026-07-18T22:00:00Z",
            "responded_at": None,
            "timeout_seconds": None,
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
