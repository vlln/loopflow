from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.web_support.ac_manifest import parse_ac


VALID_KINDS = {"http_status", "sse_event", "dom", "process", "unit", "file_jsonl"}


def _targets() -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}

    def assign(ids: str, *values: str) -> None:
        for ac_id in ids.split():
            targets[ac_id] = list(values)

    # Normal: file_changes.jsonl content verification
    assign(
        "AC-024-N-1 AC-024-N-2 AC-024-N-3 AC-024-N-6",
        "file_jsonl:file_changes",
    )
    # Normal: WebUI rendering
    assign("AC-024-N-4 AC-024-N-5", "GET /api/v1/runs/{run_id}", "ui:phase")
    # Normal: SSE file_changes topic
    assign("AC-024-N-7", "GET /api/v1/runs/{run_id}/events")

    # Boundary
    assign(
        "AC-024-B-1 AC-024-B-2 AC-024-B-3 AC-024-B-4 AC-024-B-5 AC-024-B-6 AC-024-B-7",
        "file_jsonl:file_changes",
    )

    # Exception
    assign("AC-024-E-1", "file_jsonl:file_changes")
    assign("AC-024-E-2", "process:cli-run")

    # Failure
    assign("AC-024-F-1", "process:cli-run")
    assign("AC-024-F-2", "GET /api/v1/runs/{run_id}/events")

    # Unit
    assign(
        "AC-024-U-1 AC-024-U-2 AC-024-U-3 AC-024-U-4 AC-024-U-5 AC-024-U-6",
        "unit:file-observation",
    )

    return targets


TARGETS = _targets()

PROTOCOL_EXPECTATIONS: dict[str, list[dict[str, Any]]] = {
    "AC-024-N-7": [{"kind": "sse_event", "value": "file_changes"}],
    "AC-024-F-2": [{"kind": "sse_event", "value": "stream_error"}],
}


def generate_manifest(ac_path: Path) -> dict[str, Any]:
    cases = []
    for row in parse_ac(ac_path):
        ac_id = row["ac_id"]
        if ac_id not in TARGETS:
            raise ValueError(f"target mapping missing for {ac_id}")
        expectations = PROTOCOL_EXPECTATIONS.get(ac_id)
        if expectations is None:
            default_kind = "file_jsonl" if any(
                t.startswith("file_jsonl:") for t in TARGETS[ac_id]
            ) else ("dom" if any(t.startswith("ui:") for t in TARGETS[ac_id]) else "unit" if any(t.startswith("unit:") for t in TARGETS[ac_id]) else "process" if any(t.startswith("process:") for t in TARGETS[ac_id]) else "http_status")
            default_value = "matches-ac" if default_kind in ("dom", "file_jsonl") else 0 if default_kind == "process" else "matches-ac"
            expectations = [{"kind": default_kind, "value": default_value}]
        cases.append(
            {
                **row,
                "test_node": _test_node_for(ac_id),
                "targets": TARGETS[ac_id],
                "expectations": expectations,
            }
        )
    return {"version": 1, "source": str(ac_path), "cases": cases}


# Maps AC IDs to real test node identifiers (replacing planned:: placeholders)
_TEST_NODES: dict[str, str] = {
    "AC-024-N-1": "test_file_changes_rest_endpoint_returns_records",
    "AC-024-N-2": "test_file_changes_rest_endpoint_returns_records",
    "AC-024-N-3": "test_file_changes_rest_endpoint_returns_records",
    "AC-024-N-4": "test_file_changes_rest_endpoint_returns_records",
    "AC-024-N-5": "test_file_changes_rest_endpoint_returns_records",
    "AC-024-N-6": "test_file_changes_rest_endpoint_empty_for_no_file",
    "AC-024-N-7": "test_sse_multi_topic_pushes_run_event_and_file_changes",
    "AC-024-B-1": "test_first_observe_marks_all_files_as_created",
    "AC-024-B-2": "test_second_observe_detects_modified_and_created",
    "AC-024-B-3": "test_deleted_file_detected",
    "AC-024-B-4": "test_no_changes_returns_none",
    "AC-024-B-5": "test_exclude_patterns_skip_files",
    "AC-024-B-6": "test_disabled_config_returns_none",
    "AC-024-B-7": "test_seq_strictly_increasing",
    "AC-024-E-1": "test_file_changes_rest_404_for_nonexistent_run",
    "AC-024-E-2": "test_sse_file_changes_cursor_out_of_range_does_not_affect_run_event",
    "AC-024-F-1": "test_file_changes_rest_404_for_nonexistent_run",
    "AC-024-F-2": "test_sse_file_changes_cursor_out_of_range_does_not_affect_run_event",
    "AC-024-U-1": "test_default_config_is_enabled",
    "AC-024-U-2": "test_disabled_via_meta",
    "AC-024-U-3": "test_exclude_patterns_from_meta",
    "AC-024-U-4": "test_default_excludes_git_and_pycache",
    "AC-024-U-5": "test_custom_exclude_pattern",
    "AC-024-U-6": "test_nested_directories_scanned",
}


def _test_node_for(ac_id: str) -> str:
    return _TEST_NODES.get(ac_id, f"planned::{ac_id.lower()}")


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

    missing = sorted(set(source_rows) - seen)
    if missing:
        errors.append(f"missing AC ids: {', '.join(missing)}")
    return errors


def read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
