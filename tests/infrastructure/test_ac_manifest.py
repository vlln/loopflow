from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.web_support.ac_manifest import (
    SUPERSEDED_AC_IDS,
    TEST_NODES,
    check_manifest,
    generate_manifest,
    read_manifest,
)


AC_PATH = Path("docs/ac/0010-webui.md")
MANIFEST_PATH = Path("tests/system/cases.json")

EXPECTED_TEST_NODES = {
    "AC-014-N-9": "web/src/App.test.tsx::AC-014-N-9: arguments editor builds a typed args object",
    "AC-014-B-1": "web/tests/webui.spec.ts::keeps a thousand Runs reachable without resizing the workspace",
    "AC-014-B-3": "web/src/App.test.tsx::AC-014-B-3: blank-key rows are ignored and an empty editor submits {}",
    "AC-014-B-4": "web/src/App.test.tsx::AC-014-B-4: invalid JSON in JSON mode shows an error and sends nothing",
    "AC-015-F-2": "tests/unit/test_web_events.py::test_incomplete_final_line_is_hidden_until_completed",
    "AC-016-N-2": "tests/integration/test_web_api.py::test_sse_replay_end_cursor_and_legacy",
    "AC-016-N-3": "tests/integration/test_web_api.py::test_sse_multi_topic_pushes_run_event_and_file_changes",
    "AC-016-N-4": "tests/integration/test_web_api.py::test_sse_multi_topic_per_topic_cursor_reconnect",
    "AC-016-B-3": "tests/integration/test_web_api.py::test_sse_stream_end_waits_for_file_changes_terminal",
    "AC-016-E-3": "tests/integration/test_web_api.py::test_sse_file_changes_cursor_out_of_range_does_not_affect_run_event",
    "AC-016-F-2": "tests/integration/test_web_api.py::test_sse_reader_failure_after_headers_emits_stream_error",
    "AC-016-F-3": "tests/integration/test_web_api.py::test_sse_file_changes_read_failure_emits_stream_error_and_closes",
    "AC-017-E-1": "tests/integration/test_web_api.py::test_loop_preview_security_backend_and_static",
    "AC-017-E-2": "tests/integration/test_web_api.py::test_loop_preview_security_backend_and_static",
}


def test_generated_manifest_covers_every_frozen_scenario():
    manifest = generate_manifest(AC_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []
    assert len(manifest["cases"]) == 89
    assert TEST_NODES == EXPECTED_TEST_NODES


def test_agentgraph_targets_and_new_scenarios_are_frozen():
    manifest = generate_manifest(AC_PATH)
    cases = {case["ac_id"]: case for case in manifest["cases"]}

    assert "ui:agent-graph" in cases["AC-015-N-1"]["targets"]
    assert all("ui:phase" not in case["targets"] for case in manifest["cases"])
    assert cases["AC-014-B-7"]["expectations"] == [
        {"kind": "http_status", "value": 409, "code": "run_in_grace"}
    ]
    assert "GET /api/v1/runs/{run_id}/file/raw" in cases["AC-017-N-3"]["targets"]
    assert cases["AC-017-F-3"]["expectations"] == [
        {"kind": "http_status", "value": 500, "code": "file_read_failed"}
    ]


def test_committed_manifest_matches_generator():
    assert read_manifest(MANIFEST_PATH) == generate_manifest(AC_PATH)


def test_manifest_checker_rejects_missing_scenario():
    manifest = generate_manifest(AC_PATH)
    missing = manifest["cases"].pop()

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert errors == [f"missing AC ids: {missing['ac_id']}"]


def test_manifest_checker_rejects_interface_drift_and_empty_assertion():
    manifest = deepcopy(generate_manifest(AC_PATH))
    case = next(item for item in manifest["cases"] if item["ac_id"] == "AC-016-E-1")
    case["expectations"][0]["value"] = 409
    case["assertion"] = ""

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert "AC-016-E-1: assertion does not match AC source" in errors
    assert "AC-016-E-1: cursor_out_of_range must use HTTP 410" in errors


def test_strict_manifest_rejects_planned_nodes():
    manifest = generate_manifest(AC_PATH)

    errors = check_manifest(manifest, AC_PATH)

    planned = [
        case for case in manifest["cases"]
        if case["ac_id"] not in SUPERSEDED_AC_IDS
        and case["test_node"].startswith("planned::")
    ]
    assert len(planned) == 71
    assert len(SUPERSEDED_AC_IDS) == 4
    assert set(TEST_NODES).isdisjoint(SUPERSEDED_AC_IDS)
    assert len(manifest["cases"]) == len(TEST_NODES) + len(planned) + len(SUPERSEDED_AC_IDS)
    assert len(errors) == len(planned)
    assert all("planned test node is not allowed" in error for error in errors)


def test_manifest_checker_rejects_mapping_drift_and_unmapped_nodes():
    manifest = generate_manifest(AC_PATH)
    mapped_cases = [case for case in manifest["cases"] if case["ac_id"] in TEST_NODES]
    mapped = mapped_cases[0]
    mapped["test_node"] = "tests/unit/test_web_application.py::test_missing"
    downgraded = mapped_cases[1]
    downgraded["test_node"] = f"planned::{downgraded['ac_id'].lower()}"

    planned = next(
        case for case in manifest["cases"]
        if case["ac_id"] not in SUPERSEDED_AC_IDS
        and case["ac_id"] not in TEST_NODES
    )
    planned["test_node"] = "tests/unit/test_web_application.py::test_missing"

    another_planned = next(
        case for case in manifest["cases"]
        if case["ac_id"] not in SUPERSEDED_AC_IDS
        and case["ac_id"] not in TEST_NODES
        and case is not planned
    )
    another_planned["test_node"] = next(iter(TEST_NODES.values()))

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"{mapped['ac_id']}: test_node does not match implemented mapping" in errors
    assert f"{downgraded['ac_id']}: test_node does not match implemented mapping" in errors
    assert f"{planned['ac_id']}: no implemented test_node mapping" in errors
    assert f"{another_planned['ac_id']}: no implemented test_node mapping" in errors


def test_manifest_checker_rejects_missing_implemented_node(monkeypatch):
    manifest = generate_manifest(AC_PATH)
    mapped = next(case for case in manifest["cases"] if case["ac_id"] in TEST_NODES)
    missing = "tests/unit/test_web_application.py::test_missing"
    monkeypatch.setitem(TEST_NODES, mapped["ac_id"], missing)
    mapped["test_node"] = missing

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"{mapped['ac_id']}: test_node does not exist" in errors
