"""Interactive terminal answering for pending intervention requests (ADR-0056 §1).

This presentation module only collects answers: it lists pending requests,
prompts with numbered options / free text, and applies the request timeout as
a live countdown (stdlib select on POSIX tty). Persistence and the
authoritative validation stay in the application layer (`answer_requests`);
the local pre-validation exists solely so an invalid answer re-prompts
instead of aborting the whole batch (AC-031-F-2).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from select import select as _select
from typing import Any

from loopflow.infrastructure.intervention import (
    InterventionValidationError,
    _effective_allow_custom,
    _effective_options,
    validate_response,
)


class PromptAborted(RuntimeError):
    """Input ended (EOF); nothing is persisted and the Run keeps waiting."""


def stdin_interactive() -> bool:
    """True when stdin is a tty we may prompt on (ADR-0056 §1)."""
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def collect_responses(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prompt once per pending request; returns answer_requests()-shaped items."""
    return [_prompt_one(request) for request in requests]


def _prompt_one(request: dict[str, Any]) -> dict[str, Any]:
    options = _effective_options(request)
    allow_custom = _effective_allow_custom(request)
    print(f"\n[intervention] {request.get('key')}: {request.get('prompt')}")
    for index, option in enumerate(options, start=1):
        print(f"  {index}) {option}")
    deadline = _timeout_deadline(request)
    if deadline is not None:
        print(f"  (no answer within {request.get('timeout_seconds')}s uses the default: {request.get('default')})")
    while True:
        remaining = None
        if deadline is not None:
            remaining = deadline - datetime.now(timezone.utc).timestamp()
            if remaining <= 0:
                return _timeout_answer(request)
        raw = _read_line(remaining)
        if raw is None:
            if deadline is not None:
                return _timeout_answer(request)
            raise PromptAborted(str(request.get("key")))
        value, error = _parse_input(raw, request, options, allow_custom)
        if error is None:
            try:
                validate_response(request, value)
            except InterventionValidationError as validation:
                error = str(validation)
        if error is None:
            return {"request_id": request["request_id"], "response": value}
        print(f"Invalid answer: {error}")


def _timeout_deadline(request: dict[str, Any]) -> float | None:
    timeout = request.get("timeout_seconds")
    if timeout is None or request.get("default") is None:
        return None
    created = request.get("created_at")
    if not isinstance(created, str) or not created:
        return None
    try:
        parsed = datetime.fromisoformat(created)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp() + float(timeout)


def _timeout_answer(request: dict[str, Any]) -> dict[str, Any]:
    print(f"[intervention] timeout — using default: {request.get('default')}")
    return {
        "request_id": request["request_id"],
        "response": request.get("default"),
        "response_source": "timeout_default",
    }


def _parse_input(
    raw: str,
    request: dict[str, Any],
    options: list[str],
    allow_custom: bool,
) -> tuple[Any, str | None]:
    raw = raw.strip()
    if not raw:
        return None, "answer must not be empty"
    if options:
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1], None
        if raw in options:
            return raw, None
        if allow_custom:
            return raw, None
        return None, "answer must match one of the request options"
    schema = request.get("schema")
    if isinstance(schema, dict) and schema.get("type") not in (None, "string"):
        try:
            return json.loads(raw), None
        except json.JSONDecodeError:
            return None, f"answer must be {schema.get('type')}"
    return raw, None


def _read_line(timeout: float | None) -> str | None:
    """One input line; None on countdown expiry or EOF."""
    if timeout is None:
        try:
            return input()
        except EOFError:
            return None
    try:
        ready, _, _ = _select([sys.stdin], [], [], max(timeout, 0.0))
    except (OSError, ValueError):
        # stdin is not selectable (non-POSIX or redirected): plain blocking read
        try:
            return input()
        except EOFError:
            return None
    if not ready:
        return None
    line = sys.stdin.readline()
    if line == "":
        return None
    return line.rstrip("\r\n")
