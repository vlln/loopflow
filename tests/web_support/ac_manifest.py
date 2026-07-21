from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


AC_PATTERN = re.compile(r"^\|\s*(AC-0(?:14|15|16|17|18|19)-[NBEF]-\d+)\s*\|")
VALID_KINDS = {"http_status", "sse_event", "dom", "process"}
HTTP_STATUS_BY_CODE = {
    "path_forbidden": 403,
    "loop_not_found": 404,
    "run_not_found": 404,
    "file_not_found": 404,
    "backend_not_found": 404,
    "invalid_run_transition": 409,
    "run_not_stale": 409,
    "process_alive": 409,
    "legacy_events_not_streamable": 409,
    "process_gone": 410,
    "cursor_out_of_range": 410,
    "request_too_large": 413,
    "validation_failed": 422,
    "file_not_previewable": 422,
    "atomic_write_failed": 500,
    "internal_error": 500,
    "diagnostic_start_failed": 503,
}
VALID_SSE_EVENTS = {"run_event", "stream_end", "stream_error"}


def _targets() -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}

    def assign(ids: str, *values: str) -> None:
        for ac_id in ids.split():
            targets[ac_id] = list(values)

    assign(
        "AC-014-N-1 AC-014-N-2 AC-014-N-8 AC-014-B-1 AC-014-B-2 AC-014-E-1",
        "GET /api/v1/runs",
        "ui:runs",
    )
    assign("AC-014-N-3 AC-014-E-2", "GET /api/v1/runs/{run_id}", "ui:runs")
    assign("AC-014-N-4", "POST /api/v1/runs", "ui:runs")
    assign("AC-014-N-5", "POST /api/v1/runs/{run_id}/stop", "ui:runs")
    assign("AC-014-N-6", "POST /api/v1/runs/{run_id}/resume", "ui:runs")
    assign("AC-014-N-7", "POST /api/v1/runs/{run_id}/rerun", "ui:runs")
    assign(
        "AC-014-F-1",
        "POST /api/v1/runs/{run_id}/stop",
        "POST /api/v1/runs/{run_id}/resume",
    )
    assign("AC-014-F-2", "POST /api/v1/runs/{run_id}/reconcile")

    for ac_id in (
        "AC-015-N-1 AC-015-N-2 AC-015-N-3 AC-015-N-4 AC-015-N-5 "
        "AC-015-B-1 AC-015-B-2 AC-015-E-2 AC-015-F-1 AC-015-F-2"
    ).split():
        targets[ac_id] = ["GET /api/v1/runs/{run_id}", "ui:phase"]
    assign("AC-015-E-1", "GET /api/v1/runs/{run_id}/legacy-events", "ui:phase")

    for ac_id in (
        "AC-016-N-1 AC-016-N-2 AC-016-B-1 AC-016-B-2 AC-016-E-1 "
        "AC-016-F-1 AC-016-F-2"
    ).split():
        targets[ac_id] = ["GET /api/v1/runs/{run_id}/events"]
    assign("AC-016-E-2", "ui:event-reducer")

    assign("AC-017-N-1 AC-017-F-2", "GET /api/v1/loops", "ui:loops")
    assign("AC-017-N-2 AC-017-B-1", "GET /api/v1/loops/{loop_name}", "ui:loops")
    assign(
        "AC-017-B-2 AC-017-E-1 AC-017-E-2",
        "GET /api/v1/loops/{loop_name}/file",
        "ui:loops",
    )
    assign("AC-017-F-1", "GET /api/v1/loops/{loop_name}", "GET /api/v1/loops", "ui:loops")

    assign("AC-018-N-1 AC-018-B-1 AC-018-B-2", "GET /api/v1/backends", "ui:backends")
    assign(
        "AC-018-N-2 AC-018-E-1 AC-018-E-2 AC-018-F-1 AC-018-F-2",
        "POST /api/v1/backends/{backend_name}/diagnostics",
        "ui:backends",
    )

    assign(
        "AC-019-N-1 AC-019-N-2 AC-019-B-1 AC-019-B-2 AC-019-E-1 AC-019-E-2 AC-019-F-1 AC-019-F-2",
        "ui:layout",
    )
    assign("AC-019-N-3 AC-019-N-4 AC-019-F-3", "process:loop-web")
    return targets


TARGETS = _targets()

PROTOCOL_EXPECTATIONS: dict[str, list[dict[str, Any]]] = {
    "AC-014-N-4": [{"kind": "http_status", "value": 201}],
    "AC-014-N-5": [{"kind": "http_status", "value": 200}],
    "AC-014-N-6": [{"kind": "http_status", "value": 200}],
    "AC-014-N-7": [{"kind": "http_status", "value": 201}],
    "AC-014-F-1": [
        {"kind": "http_status", "value": 409, "code": "invalid_run_transition"}
    ],
    "AC-014-F-2": [{"kind": "http_status", "value": 200}],
    "AC-015-E-1": [{"kind": "http_status", "value": 200}],
    "AC-015-F-1": [{"kind": "http_status", "value": 200}],
    "AC-016-N-1": [{"kind": "sse_event", "value": "run_event"}],
    "AC-016-N-2": [{"kind": "sse_event", "value": "run_event"}],
    "AC-016-B-1": [{"kind": "sse_event", "value": "stream_end"}],
    "AC-016-B-2": [{"kind": "sse_event", "value": "run_event"}],
    "AC-016-E-1": [
        {"kind": "http_status", "value": 410, "code": "cursor_out_of_range"}
    ],
    "AC-016-E-2": [{"kind": "dom", "value": "deduplicated"}],
    "AC-016-F-1": [{"kind": "http_status", "value": 404, "code": "run_not_found"}],
    "AC-016-F-2": [{"kind": "sse_event", "value": "stream_error"}],
    "AC-017-B-2": [
        {"kind": "http_status", "value": 422, "code": "file_not_previewable"}
    ],
    "AC-017-E-1": [{"kind": "http_status", "value": 403, "code": "path_forbidden"}],
    "AC-017-E-2": [{"kind": "http_status", "value": 403, "code": "path_forbidden"}],
    "AC-017-F-1": [{"kind": "http_status", "value": 404, "code": "loop_not_found"}],
    "AC-018-N-2": [{"kind": "http_status", "value": 200}],
    "AC-018-E-1": [{"kind": "http_status", "value": 200}],
    "AC-018-E-2": [{"kind": "http_status", "value": 200}],
    "AC-018-F-1": [{"kind": "http_status", "value": 404, "code": "backend_not_found"}],
    "AC-018-F-2": [
        {"kind": "http_status", "value": 503, "code": "diagnostic_start_failed"}
    ],
    "AC-019-N-3": [{"kind": "process", "value": "loopback-only"}],
    "AC-019-N-4": [{"kind": "process", "value": "remote-opt-in"}],
    "AC-019-F-3": [{"kind": "process", "value": "exit-nonzero"}],
}


def parse_ac(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not AC_PATTERN.match(line):
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if len(columns) < 4:
            raise ValueError(f"malformed AC table row: {line}")
        cases.append(
            {
                "ac_id": columns[0],
                "fixture": columns[1],
                "action": columns[2],
                "assertion": columns[3],
            }
        )
    return cases


def generate_manifest(ac_path: Path) -> dict[str, Any]:
    cases = []
    for row in parse_ac(ac_path):
        ac_id = row["ac_id"]
        if ac_id not in TARGETS:
            raise ValueError(f"target mapping missing for {ac_id}")
        expectations = PROTOCOL_EXPECTATIONS.get(ac_id)
        if expectations is None:
            default_kind = "dom" if any(target.startswith("ui:") for target in TARGETS[ac_id]) else "http_status"
            default_value: str | int = "matches-ac" if default_kind == "dom" else 200
            expectations = [{"kind": default_kind, "value": default_value}]
        cases.append(
            {
                **row,
                "test_node": f"planned::{ac_id.lower()}",
                "targets": TARGETS[ac_id],
                "expectations": expectations,
            }
        )
    return {"version": 1, "source": str(ac_path), "cases": cases}


def check_manifest(
    manifest: dict[str, Any], ac_path: Path, *, allow_planned: bool = False
) -> list[str]:
    errors: list[str] = []
    source_rows = {row["ac_id"]: row for row in parse_ac(ac_path)}
    cases = manifest.get("cases")
    if manifest.get("version") != 1 or not isinstance(cases, list):
        return ["manifest must have version=1 and a cases array"]

    seen: set[str] = set()
    for index, case in enumerate(cases):
        label = f"case[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        ac_id = case.get("ac_id")
        if ac_id in seen:
            errors.append(f"duplicate AC id: {ac_id}")
        seen.add(ac_id)
        if ac_id not in source_rows:
            errors.append(f"unknown AC id: {ac_id}")
            continue
        source = source_rows[ac_id]
        for field in ("fixture", "action", "assertion"):
            if not case.get(field) or case.get(field) != source[field]:
                errors.append(f"{ac_id}: {field} does not match AC source")
        if case.get("targets") != TARGETS.get(ac_id):
            errors.append(f"{ac_id}: targets do not match frozen mapping")
        node = case.get("test_node")
        if not isinstance(node, str) or not node:
            errors.append(f"{ac_id}: test_node is required")
        elif node.startswith("planned::") and not allow_planned:
            errors.append(f"{ac_id}: planned test node is not allowed in strict mode")

        expectations = case.get("expectations")
        if not isinstance(expectations, list) or not expectations:
            errors.append(f"{ac_id}: at least one expectation is required")
            continue
        for expectation in expectations:
            if not isinstance(expectation, dict) or expectation.get("kind") not in VALID_KINDS:
                errors.append(f"{ac_id}: invalid expectation kind")
                continue
            if expectation.get("value") in (None, ""):
                errors.append(f"{ac_id}: expectation value is required")
            if expectation.get("kind") == "sse_event" and expectation.get("value") not in VALID_SSE_EVENTS:
                errors.append(f"{ac_id}: unknown SSE event {expectation.get('value')}")
            code = expectation.get("code")
            if code is not None:
                expected_status = HTTP_STATUS_BY_CODE.get(code)
                if expected_status is None:
                    errors.append(f"{ac_id}: unknown Interface error code {code}")
                elif expectation.get("kind") != "http_status" or expectation.get("value") != expected_status:
                    errors.append(f"{ac_id}: {code} must use HTTP {expected_status}")

    missing = sorted(set(source_rows) - seen)
    if missing:
        errors.append(f"missing AC ids: {', '.join(missing)}")
    return errors


def read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
