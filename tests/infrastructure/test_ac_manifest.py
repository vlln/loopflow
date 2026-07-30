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
    "AC-015-N-1": "tests/integration/test_web_api.py::test_ac015_n1_sequential_graph_structure",
    "AC-015-N-2": "web/src/App.test.tsx::AC-015-N-2: selecting a graph node filters Events and file changes to that call",
    "AC-015-N-3": "tests/integration/test_web_api.py::test_ac015_n3_fork_join_graph",
    "AC-015-N-4": "tests/integration/test_web_api.py::test_ac015_n4_back_to_back_fork_join",
    "AC-015-N-5": "web/src/App.test.tsx::AC-015-N-5: Inspector shows run state; Call detail shows structured events not state diff",
    "AC-015-N-6": "tests/integration/test_web_api.py::test_ac015_n6_empty_agent_graph_no_declared_phases",
    "AC-015-N-7": "tests/integration/test_web_api.py::test_ac015_n7_live_agent_start_marks_running_current",
    "AC-015-N-8": "tests/integration/test_web_api.py::test_ac015_n8_same_label_distinct_nodes_not_merged",
    "AC-015-N-9": "web/src/App.test.tsx::AC-015-N-9: call-list shows call_id as primary, session_id in tooltip",
    "AC-015-B-1": "tests/integration/test_web_api.py::test_ac015_b1_run_without_agent_events_empty_graph",
    "AC-015-B-2": "tests/integration/test_web_api.py::test_ac015_b2_hundred_sequential_calls_ordered",
    "AC-015-B-3": "tests/integration/test_web_api.py::test_ac015_b3_no_declared_phases_in_loop_or_run",
    "AC-015-B-4": "tests/integration/test_web_api.py::test_ac015_b4_single_done_node_no_edges",
    "AC-015-B-5": "web/src/App.test.tsx::AC-015-B-5: call without session_id shows call_id and no empty row",
    "AC-015-E-1": "web/src/App.test.tsx::AC-015-F-4: legacy events without call_id stay unattributed, no phantom calls",
    "AC-015-E-2": "tests/integration/test_web_api.py::test_ac015_e2_missing_call_id_goes_to_malformed",
    "AC-015-E-3": "tests/integration/test_web_api.py::test_ac015_e3_empty_label_falls_back_to_call_id",
    "AC-015-E-4": "web/src/App.test.tsx::AC-015-E-4: graph node count, selected call, and event count shown accurately without occurrence terms",
    "AC-015-F-1": "tests/integration/test_web_api.py::test_ac015_f1_missing_events_jsonl_returns_empty",
    "AC-015-F-2": "tests/unit/test_web_events.py::test_incomplete_final_line_is_hidden_until_completed",
    "AC-015-F-3": "tests/integration/test_web_api.py::test_workflow_syntax_error_run_start_fails_without_placeholders",
    "AC-015-F-4": "web/src/App.test.tsx::AC-015-F-4: legacy events without call_id stay unattributed, no phantom calls",
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
    "AC-019-N-1": "web/tests/webui.spec.ts::operates Runs without overflow and renders a nonblank agent graph",
    "AC-019-N-2": "web/src/App.test.tsx::AC-019-N-2: keyboard selection shows focus and fires a single recover retry",
    "AC-019-N-3": "tests/integration/test_web_api.py::test_ac019_n3_default_binds_loopback_only",
    "AC-019-N-4": "tests/unit/test_web_cli.py::test_web_remote_opt_in_warns_and_serves",
    "AC-019-N-5": "web/src/App.test.tsx::AC-019-N-5: theme toggle switches data-theme and persists across renders",
    "AC-019-B-1": "web/tests/webui.spec.ts::operates Runs without overflow and renders a nonblank agent graph",
    "AC-019-B-2": "web/tests/webui.spec.ts::operates Runs without overflow and renders a nonblank agent graph",
    "AC-019-B-3": "web/tests/webui.spec.ts::light theme keeps panels and status badges legible",
    "AC-019-B-4": "web/src/App.test.tsx::AC-019-B-4: long error_summary is clamped, traceback stays expandable",
    "AC-019-E-1": "web/tests/webui.spec.ts::operates Runs without overflow and renders a nonblank agent graph",
    "AC-019-E-2": "web/src/App.test.tsx::AC-019-E-2: SSE disconnect shows stream error and keeps last data",
    "AC-019-F-1": "web/tests/webui.spec.ts::all icon-only controls expose names and tooltips",
    "AC-019-F-2": "web/src/App.test.tsx::AC-019-F-2: statuses remain text/icon distinguishable without color",
    "AC-019-F-3": "tests/unit/test_web_cli.py::test_web_remote_bind_requires_explicit_opt_in",
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
        {"kind": "http_status", "value": 200}
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
    assert len(planned) == 0
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

    # With zero planned scenarios, simulate "unmapped node" by pointing two
    # cases at node strings that have no TEST_NODES registration.
    planned = mapped_cases[2]
    planned_id = planned["ac_id"]
    planned["test_node"] = "tests/unit/test_web_application.py::test_missing"
    another_planned = mapped_cases[3]
    another_id = another_planned["ac_id"]
    another_planned["test_node"] = "tests/unit/test_web_application.py::test_other_missing"

    import tests.web_support.ac_manifest as manifest_module
    saved_first, saved_second = TEST_NODES.pop(planned_id), TEST_NODES.pop(another_id)
    try:
        errors = check_manifest(manifest, AC_PATH, allow_planned=True)
    finally:
        TEST_NODES[planned_id], TEST_NODES[another_id] = saved_first, saved_second
        manifest_module.TEST_NODES.update({planned_id: saved_first, another_id: saved_second})

    assert f"{mapped['ac_id']}: test_node does not match implemented mapping" in errors
    assert f"{downgraded['ac_id']}: test_node does not match implemented mapping" in errors
    assert f"{planned_id}: no implemented test_node mapping" in errors
    assert f"{another_id}: no implemented test_node mapping" in errors


def test_manifest_checker_rejects_missing_implemented_node(monkeypatch):
    manifest = generate_manifest(AC_PATH)
    mapped = next(case for case in manifest["cases"] if case["ac_id"] in TEST_NODES)
    missing = "tests/unit/test_web_application.py::test_missing"
    monkeypatch.setitem(TEST_NODES, mapped["ac_id"], missing)
    mapped["test_node"] = missing

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"{mapped['ac_id']}: test_node does not exist" in errors
