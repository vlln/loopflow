from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


AC_PATTERN = re.compile(r"^\|\s*(AC-\d{3}-[NBEF]-\d+)\s*\|")
VALID_KINDS = {"http_status", "sse_event", "dom", "process"}
SUPERSEDED_AC_IDS = {"AC-014-N-3", "AC-014-N-5", "AC-014-N-6", "AC-014-F-1"}
HTTP_STATUS_BY_CODE = {
    "path_forbidden": 403,
    "loop_not_found": 404,
    "run_not_found": 404,
    "file_not_found": 404,
    "backend_not_found": 404,
    "invalid_run_transition": 409,
    "run_not_stale": 409,
    "run_in_grace": 409,
    "process_alive": 409,
    "legacy_events_not_streamable": 409,
    "process_gone": 410,
    "cursor_out_of_range": 410,
    "request_too_large": 413,
    "validation_failed": 422,
    "file_not_previewable": 422,
    "file_read_failed": 500,
    "atomic_write_failed": 500,
    "internal_error": 500,
    "diagnostic_start_failed": 503,
}
VALID_SSE_EVENTS = {"run_event", "stream_end", "stream_error", "file_changes"}


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
    assign("AC-014-N-9 AC-014-B-3 AC-014-B-4", "POST /api/v1/runs", "ui:runs")
    assign(
        "AC-014-N-10 AC-014-B-5",
        "GET /api/v1/loops/{loop_name}",
        "POST /api/v1/runs",
        "ui:runs",
    )
    assign("AC-014-N-11", "GET /api/v1/system/meta", "ui:layout")
    assign("AC-014-B-6", "GET /api/v1/runs", "ui:runs")
    assign("AC-014-B-7", "POST /api/v1/runs/{run_id}/reconcile", "ui:runs")
    assign(
        "AC-014-F-1",
        "POST /api/v1/runs/{run_id}/stop",
        "POST /api/v1/runs/{run_id}/resume",
    )
    assign("AC-014-F-2", "POST /api/v1/runs/{run_id}/reconcile")

    for ac_id in (
        "AC-015-N-1 AC-015-N-2 AC-015-N-3 AC-015-N-4 AC-015-N-5 "
        "AC-015-N-6 AC-015-N-7 AC-015-N-8 AC-015-N-9 "
        "AC-015-B-1 AC-015-B-2 AC-015-B-3 AC-015-B-4 AC-015-B-5 "
        "AC-015-E-2 AC-015-E-3 AC-015-E-4 AC-015-F-1 AC-015-F-2 AC-015-F-3 AC-015-F-4"
    ).split():
        targets[ac_id] = ["GET /api/v1/runs/{run_id}", "ui:agent-graph"]
    assign(
        "AC-015-N-2",
        "GET /api/v1/runs/{run_id}",
        "GET /api/v1/runs/{run_id}/file-changes",
        "ui:agent-graph",
    )
    assign(
        "AC-015-E-1",
        "GET /api/v1/runs/{run_id}",
        "GET /api/v1/runs/{run_id}/legacy-events",
        "ui:agent-graph",
    )
    assign(
        "AC-015-B-3",
        "GET /api/v1/loops/{loop_name}",
        "GET /api/v1/runs/{run_id}",
        "ui:agent-graph",
    )
    assign(
        "AC-015-F-3",
        "POST /api/v1/runs",
        "GET /api/v1/loops",
        "ui:agent-graph",
    )

    for ac_id in (
        "AC-016-N-1 AC-016-N-2 AC-016-N-3 AC-016-N-4 "
        "AC-016-B-1 AC-016-B-2 AC-016-B-3 "
        "AC-016-E-1 AC-016-E-3 "
        "AC-016-F-1 AC-016-F-2 AC-016-F-3"
    ).split():
        targets[ac_id] = ["GET /api/v1/runs/{run_id}/events"]
    assign("AC-016-E-2", "ui:event-reducer")

    assign("AC-017-N-1 AC-017-F-2", "GET /api/v1/loops", "ui:loops")
    assign("AC-017-B-1", "GET /api/v1/loops/{loop_name}", "ui:loops")
    assign(
        "AC-017-N-2",
        "GET /api/v1/loops/{loop_name}",
        "GET /api/v1/loops/{loop_name}/file",
        "GET /api/v1/loops/{loop_name}/file/raw",
        "ui:loops",
    )
    assign(
        "AC-017-N-3",
        "GET /api/v1/runs/{run_id}/file-changes",
        "GET /api/v1/runs/{run_id}/file",
        "GET /api/v1/runs/{run_id}/file/raw",
        "ui:runs",
    )
    assign(
        "AC-017-B-2",
        "GET /api/v1/loops/{loop_name}/file",
        "GET /api/v1/loops/{loop_name}/file/raw",
        "ui:loops",
    )
    assign(
        "AC-017-E-1 AC-017-E-2",
        "GET /api/v1/loops/{loop_name}/file",
        "ui:loops",
    )
    assign("AC-017-F-1", "GET /api/v1/loops/{loop_name}", "GET /api/v1/loops", "ui:loops")
    assign(
        "AC-017-F-3",
        "GET /api/v1/runs/{run_id}/file/raw",
        "GET /api/v1/loops/{loop_name}/file/raw",
        "ui:runs",
        "ui:loops",
    )

    assign("AC-018-N-1 AC-018-B-1 AC-018-B-2", "GET /api/v1/backends", "ui:backends")
    assign(
        "AC-018-N-2 AC-018-E-1 AC-018-E-2 AC-018-F-1 AC-018-F-2",
        "POST /api/v1/backends/{backend_name}/diagnostics",
        "ui:backends",
    )

    assign(
        "AC-019-N-1 AC-019-N-2 AC-019-N-5 AC-019-B-1 AC-019-B-2 AC-019-B-3 AC-019-B-4 AC-019-E-1 AC-019-E-2 AC-019-F-1 AC-019-F-2",
        "ui:layout",
    )
    assign("AC-019-N-3 AC-019-N-4 AC-019-F-3", "process:loop-web")
    return targets


TARGETS = _targets()

# Only scenarios whose current tests cover the complete active AC semantics belong
# here. Partial candidates remain planned so strict mode exposes the coverage gap.
TEST_NODES = {
    "AC-014-N-1": "tests/integration/test_web_api.py::test_ac014_n1_runs_list_all_statuses_default_latest",
    "AC-014-N-2": "tests/integration/test_web_api.py::test_ac014_n2_failed_filter_in_place_switch",
    "AC-014-N-4": "tests/integration/test_web_api.py::test_ac014_n4_start_run_returns_201_location_and_running",
    "AC-014-N-7": "tests/integration/test_web_api.py::test_ac014_n7_rerun_creates_new_run_preserves_source",
    "AC-014-N-8": "tests/integration/test_web_api.py::test_ac014_n8_loop_filter_and_text_search",
    "AC-014-N-9": "web/src/App.test.tsx::AC-014-N-9: arguments editor builds a typed args object",
    "AC-014-N-10": "web/src/App.test.tsx::AC-014-N-10: declared args prefill the editor and empty rows are skipped on submit",
    "AC-014-N-11": "tests/integration/test_web_api.py::test_ac014_n11_system_meta_returns_running_version",
    "AC-014-B-1": "web/tests/webui.spec.ts::keeps a thousand Runs reachable without resizing the workspace",
    "AC-014-B-2": "tests/integration/test_web_api.py::test_ac014_b2_empty_runs_shows_empty_state",
    "AC-014-B-3": "web/src/App.test.tsx::AC-014-B-3: blank-key rows are ignored and an empty editor submits {}",
    "AC-014-B-4": "web/src/App.test.tsx::AC-014-B-4: invalid JSON in JSON mode shows an error and sends nothing",
    "AC-014-B-5": "web/src/App.test.tsx::AC-014-B-5: a loop without declared args starts with a blank editor",
    "AC-014-B-6": "tests/integration/test_web_api.py::test_ac014_b6_working_directory_basename_in_summary",
    "AC-014-B-7": "tests/integration/test_web_api.py::test_ac014_b7_reconcile_stale_since_cleans_failed",
    "AC-014-E-1": "tests/integration/test_web_api.py::test_ac014_e1_unreadable_run_returned_as_summary",
    "AC-014-E-2": "tests/integration/test_web_api.py::test_ac014_e2_stale_detection_records_stale_since_once",
    "AC-014-F-2": "tests/integration/test_web_api.py::test_ac014_f2_reconcile_expired_stale_atomic_failed",
    "AC-015-F-2": "tests/unit/test_web_events.py::test_incomplete_final_line_is_hidden_until_completed",
    "AC-016-N-3": "tests/integration/test_web_api.py::test_sse_multi_topic_pushes_run_event_and_file_changes",
    "AC-016-N-2": "tests/integration/test_web_api.py::test_sse_replay_end_cursor_and_legacy",
    "AC-016-N-1": "tests/integration/test_web_api.py::test_ac016_n1_sse_replay_then_live_push",
    "AC-016-N-4": "tests/integration/test_web_api.py::test_sse_multi_topic_per_topic_cursor_reconnect",
    "AC-016-B-1": "tests/integration/test_web_api.py::test_ac016_b1_sse_end_cursor_streams_end_without_replay",
    "AC-016-B-2": "tests/integration/test_web_api.py::test_ac016_b2_sse_replay_latency_under_500ms",
    "AC-016-E-1": "tests/integration/test_web_api.py::test_ac016_e1_sse_cursor_out_of_range_returns_410",
    "AC-016-E-2": "web/src/eventReducer.test.ts::AC-016-E-2: applying the same event_id twice changes state only once",
    "AC-016-F-1": "tests/integration/test_web_api.py::test_ac016_f1_sse_unknown_run_returns_404",
    "AC-016-B-3": "tests/integration/test_web_api.py::test_sse_stream_end_waits_for_file_changes_terminal",
    "AC-016-E-3": "tests/integration/test_web_api.py::test_sse_file_changes_cursor_out_of_range_does_not_affect_run_event",
    "AC-016-F-2": "tests/integration/test_web_api.py::test_sse_reader_failure_after_headers_emits_stream_error",
    "AC-016-F-3": "tests/integration/test_web_api.py::test_sse_file_changes_read_failure_emits_stream_error_and_closes",
    "AC-017-E-1": "tests/integration/test_web_api.py::test_loop_preview_security_backend_and_static",
    "AC-017-E-2": "tests/integration/test_web_api.py::test_loop_preview_security_backend_and_static",
    "AC-017-N-1": "web/src/App.test.tsx::AC-017-N-1: selecting a Loop keeps both items and swaps detail in place",
    "AC-017-N-2": "tests/integration/test_web_api.py::test_ac017_n2_loop_file_previews_text_and_binary",
    "AC-017-N-3": "tests/integration/test_web_api.py::test_ac017_n3_run_file_changes_binary_preview",
    "AC-017-B-1": "web/src/App.test.tsx::AC-017-B-1: loop with no agents shows 0 Agents empty state without error",
    "AC-017-B-2": "tests/integration/test_web_api.py::test_ac017_b2_loop_preview_rejects_binary_oversized",
    "AC-017-F-1": "tests/integration/test_web_api.py::test_ac017_f1_loop_deleted_returns_404",
    "AC-017-F-2": "tests/integration/test_web_api.py::test_ac017_f2_invalid_yaml_marks_loop_invalid",
    "AC-017-F-3": "tests/integration/test_web_api.py::test_ac017_f3_loop_raw_read_failure_no_partial_headers",
    "AC-018-N-1": "tests/integration/test_web_api.py::test_ac018_n1_backends_list_real_fields",
    "AC-018-N-2": "tests/integration/test_web_api.py::test_ac018_n2_stderr_token_redacted",
    "AC-018-B-1": "tests/integration/test_web_api.py::test_ac018_b1_no_backends_empty_state",
    "AC-018-B-2": "tests/integration/test_web_api.py::test_ac018_b2_unknown_version_renders_null",
    "AC-018-E-1": "tests/integration/test_web_api.py::test_ac018_e1_diagnostic_timeout",
    "AC-018-E-2": "tests/integration/test_web_api.py::test_ac018_e2_invalid_encoding_uses_replacement",
    "AC-018-F-1": "tests/integration/test_web_api.py::test_ac018_f1_unknown_backend_404",
    "AC-018-F-2": "tests/integration/test_web_api.py::test_ac018_f2_diagnostic_start_failed_503",
}


def _test_node_exists(node: str) -> bool:
    path_text, *selectors = node.split("::")
    path = Path(path_text)
    if not path.is_file() or not selectors:
        return False
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        for selector in selectors[:-1]:
            if not re.search(rf"^class\s+{re.escape(selector)}\b", source, re.M):
                return False
        return bool(re.search(
            rf"^(?:\s*)def\s+{re.escape(selectors[-1])}\s*\(",
            source,
            re.M,
        ))
    return selectors[-1] in source

PROTOCOL_EXPECTATIONS: dict[str, list[dict[str, Any]]] = {
    "AC-014-N-4": [{"kind": "http_status", "value": 201}],
    "AC-014-N-5": [{"kind": "http_status", "value": 200}],
    "AC-014-N-6": [{"kind": "http_status", "value": 200}],
    "AC-014-N-7": [{"kind": "http_status", "value": 201}],
    "AC-014-F-1": [
        {"kind": "http_status", "value": 409, "code": "invalid_run_transition"}
    ],
    "AC-014-F-2": [{"kind": "http_status", "value": 200}],
    "AC-014-B-7": [
        {"kind": "http_status", "value": 409, "code": "run_in_grace"}
    ],
    "AC-015-E-1": [{"kind": "http_status", "value": 200}],
    "AC-015-F-1": [{"kind": "http_status", "value": 200}],
    "AC-016-N-1": [{"kind": "sse_event", "value": "run_event"}],
    "AC-016-N-2": [{"kind": "sse_event", "value": "run_event"}],
    "AC-016-N-3": [{"kind": "sse_event", "value": "run_event"}, {"kind": "sse_event", "value": "file_changes"}],
    "AC-016-N-4": [{"kind": "sse_event", "value": "run_event"}, {"kind": "sse_event", "value": "file_changes"}],
    "AC-016-B-1": [{"kind": "sse_event", "value": "stream_end"}],
    "AC-016-B-2": [{"kind": "sse_event", "value": "run_event"}],
    "AC-016-B-3": [{"kind": "sse_event", "value": "file_changes"}],
    "AC-016-E-1": [
        {"kind": "http_status", "value": 410, "code": "cursor_out_of_range"}
    ],
    "AC-016-E-2": [{"kind": "dom", "value": "deduplicated"}],
    "AC-016-E-3": [{"kind": "sse_event", "value": "stream_error"}],
    "AC-016-F-1": [{"kind": "http_status", "value": 404, "code": "run_not_found"}],
    "AC-016-F-2": [{"kind": "sse_event", "value": "stream_error"}],
    "AC-016-F-3": [{"kind": "sse_event", "value": "stream_error"}],
    "AC-017-B-2": [
        {"kind": "http_status", "value": 422, "code": "file_not_previewable"}
    ],
    "AC-017-N-2": [{"kind": "http_status", "value": 200}],
    "AC-017-N-3": [{"kind": "http_status", "value": 200}],
    "AC-017-E-1": [{"kind": "http_status", "value": 403, "code": "path_forbidden"}],
    "AC-017-E-2": [{"kind": "http_status", "value": 403, "code": "path_forbidden"}],
    "AC-017-F-1": [{"kind": "http_status", "value": 404, "code": "loop_not_found"}],
    "AC-017-F-3": [{"kind": "http_status", "value": 500, "code": "file_read_failed"}],
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
                "test_node": TEST_NODES.get(ac_id, f"planned::{ac_id.lower()}"),
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
        if ac_id in SUPERSEDED_AC_IDS:
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
        elif ac_id in TEST_NODES:
            if node != TEST_NODES[ac_id]:
                errors.append(f"{ac_id}: test_node does not match implemented mapping")
            elif not _test_node_exists(node):
                errors.append(f"{ac_id}: test_node does not exist")
        elif node.startswith("planned::"):
            if not allow_planned:
                errors.append(f"{ac_id}: planned test node is not allowed in strict mode")
        else:
            errors.append(f"{ac_id}: no implemented test_node mapping")

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
