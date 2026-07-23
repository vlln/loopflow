from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.web_support.ac_manifest import parse_ac


VALID_KINDS = {"http_status", "cli_exit", "dom", "process", "unit"}
HTTP_STATUS_BY_CODE = {
    "run_not_found": 404,
    "intervention_not_found": 404,
    "invalid_run_transition": 409,
    "replay_diverged": 409,
    "continue_not_supported": 409,
    "intervention_already_answered": 409,
    "validation_failed": 422,
    "atomic_write_failed": 500,
}


def _targets() -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}

    def assign(ids: str, *values: str) -> None:
        for ac_id in ids.split():
            targets[ac_id] = list(values)

    assign("AC-020-N-1 AC-020-N-2", "POST /api/v1/runs/{run_id}/recover")
    assign("AC-020-N-3", "unit:call-cache")
    assign("AC-020-N-4", "ui:runs")
    assign("AC-020-B-1", "unit:parallel-call-id")
    assign("AC-020-B-2", "unit:legacy-cache")
    assign("AC-020-B-3", "process:cli-recover")
    assign("AC-020-E-1 AC-020-E-2", "POST /api/v1/runs/{run_id}/recover")
    assign("AC-020-E-3", "unit:replay-digest")
    assign("AC-020-F-1", "unit:call-cache")
    assign("AC-020-F-2", "POST /api/v1/runs/{run_id}/recover")
    assign("AC-020-F-3", "unit:replay-target")

    assign("AC-021-N-1", "POST /api/v1/runs/{run_id}/stop", "process:group")
    assign("AC-021-N-2", "POST /api/v1/runs/{run_id}/stop")
    assign("AC-021-N-3", "POST /api/v1/runs/{run_id}/recover")
    assign("AC-021-B-1", "process:group")
    assign("AC-021-B-2", "GET /api/v1/runs/{run_id}")
    assign("AC-021-B-3 AC-021-B-4", "POST /api/v1/runs/{run_id}/recover")
    assign("AC-021-E-1", "unit:execution-epoch")
    assign(
        "AC-021-E-2",
        "POST /api/v1/runs/{run_id}/recover",
        "POST /api/v1/runs/{run_id}/interventions/{request_id}/response",
    )
    assign("AC-021-F-1", "POST /api/v1/runs/{run_id}/stop")
    assign("AC-021-F-2", "process:identity")

    assign("AC-022-N-1", "unit:intervention")
    assign("AC-022-N-2", "POST /api/v1/runs/{run_id}/interventions/{request_id}/response")
    assign("AC-022-N-3", "unit:session-intervention")
    assign("AC-022-N-4", "ui:intervention")
    assign("AC-022-N-5", "POST /api/v1/runs/{run_id}/interventions/{request_id}/response")
    assign("AC-022-B-1 AC-022-B-2", "unit:intervention")
    assign("AC-022-B-3", "GET /api/v1/runs/{run_id}", "GET /api/v1/runs/{run_id}/interventions")
    assign(
        "AC-022-E-1 AC-022-E-2",
        "POST /api/v1/runs/{run_id}/interventions/{request_id}/response",
    )
    assign("AC-022-E-3", "unit:session-intervention")
    assign("AC-022-F-1", "unit:intervention-replay")
    assign("AC-022-F-2", "unit:agent-control-output")
    return targets


TARGETS = _targets()

TEST_NODES = {
    "AC-020-N-1": "tests/unit/test_runtime.py::TestAgent::test_recovery_replays_success_then_retries_failed_call",
    "AC-020-N-2": "tests/unit/test_runtime.py::TestAgent::test_recovery_continue_uses_failed_durable_session",
    "AC-020-N-3": "tests/unit/test_runtime.py::TestAgent::test_agent_writes_cache",
    "AC-020-N-4": "web/src/App.test.tsx::disables Continue when the failed backend has no durable session",
    "AC-020-B-1": "tests/unit/test_runtime.py::TestRunContext::test_parallel_namespaces_are_stable_by_input_position",
    "AC-020-B-2": "tests/unit/test_recovery.py::test_corrupt_tail_is_uncommitted_and_legacy_success_is_unverified",
    "AC-020-B-3": "tests/integration/test_cli.py::TestResume::test_resume_is_deprecated_retry_alias_for_failed_run",
    "AC-020-E-1": "tests/unit/test_web_execution.py::test_background_executor_surfaces_replay_divergence_before_return",
    "AC-020-E-2": "tests/unit/test_web_application.py::test_continue_requires_durable_session_and_concurrent_recovery_is_rejected",
    "AC-020-E-3": "tests/unit/test_recovery.py::test_call_digest_is_stable_and_tracks_workflow_and_prompt",
    "AC-020-F-1": "tests/unit/test_recovery.py::test_corrupt_tail_is_uncommitted_and_legacy_success_is_unverified",
    "AC-020-F-2": "tests/unit/test_web_execution.py::test_background_executor_rejects_second_worker_for_same_run",
    "AC-020-F-3": "tests/unit/test_web_execution.py::test_recovery_fails_when_workflow_ends_before_target",
    "AC-021-N-1": "tests/unit/test_web_application.py::test_create_stop_recover_rerun_and_invalid_transition",
    "AC-021-N-2": "tests/unit/test_web_application.py::test_stop_waiting_input_cancels_without_worker_and_preserves_pending_request",
    "AC-021-N-3": "tests/unit/test_web_application.py::test_cancelled_recover_retry_and_continue_boundaries",
    "AC-021-B-1": "tests/unit/test_web_application.py::test_stop_escalates_to_kill_result_and_legacy_stopped_has_only_rerun",
    "AC-021-B-2": "tests/unit/test_web_application.py::test_stop_escalates_to_kill_result_and_legacy_stopped_has_only_rerun",
    "AC-021-B-3": "tests/unit/test_web_application.py::test_cancelled_recover_retry_and_continue_boundaries",
    "AC-021-B-4": "tests/unit/test_web_application.py::test_cancelled_recover_retry_and_continue_boundaries",
    "AC-021-E-1": "tests/unit/test_web_execution.py::test_execute_workflow_terminal_guard_does_not_overwrite_cancelled",
    "AC-021-E-2": "tests/unit/test_web_application.py::test_cancelled_without_boundary_rejects_recover_and_respond",
    "AC-021-F-1": "tests/unit/test_web_application.py::test_stop_does_not_signal_when_cancelling_write_fails",
    "AC-021-F-2": "tests/unit/test_web_application.py::test_stop_pid_reuse_does_not_signal_and_records_process_gone",
    "AC-022-N-1": "tests/unit/test_web_execution.py::test_workflow_intervention_waits_and_replays_answer",
    "AC-022-N-2": "tests/unit/test_web_application.py::test_intervention_response_validates_persists_and_recovers_same_run",
    "AC-022-N-3": "tests/unit/test_runtime.py::TestAgent::test_agent_structured_intervention_requires_durable_session",
    "AC-022-N-4": "web/src/App.test.tsx::answers a waiting intervention with a boolean control",
    "AC-022-N-5": "tests/unit/test_web_application.py::test_cancelled_pending_intervention_can_be_answered",
    "AC-022-B-1": "tests/integration/test_web_api.py::test_intervention_endpoints_list_validate_and_respond",
    "AC-022-B-2": "tests/unit/test_web_application.py::test_intervention_null_schema_accepts_any_json_value",
    "AC-022-B-3": "tests/unit/test_web_application.py::test_cancelled_pending_intervention_remains_pending_without_response",
    "AC-022-E-1": "tests/unit/test_web_application.py::test_intervention_response_rejects_invalid_and_duplicate_without_recovery",
    "AC-022-E-2": "tests/unit/test_web_application.py::test_intervention_response_rejects_invalid_and_duplicate_without_recovery",
    "AC-022-E-3": "tests/unit/test_runtime.py::TestAgent::test_agent_intervention_without_durable_session_fails_without_request",
    "AC-022-F-1": "tests/unit/test_web_execution.py::test_workflow_intervention_replay_diverges_on_prompt_change",
    "AC-022-F-2": "tests/unit/test_runtime.py::TestAgent::test_agent_natural_language_question_is_plain_output",
}

EXPECTATIONS: dict[str, list[dict[str, Any]]] = {
    "AC-020-N-1": [{"kind": "http_status", "value": 200}],
    "AC-020-N-2": [{"kind": "http_status", "value": 200}],
    "AC-020-E-1": [
        {"kind": "http_status", "value": 409, "code": "replay_diverged"}
    ],
    "AC-020-E-2": [
        {"kind": "http_status", "value": 409, "code": "continue_not_supported"}
    ],
    "AC-020-F-2": [
        {"kind": "http_status", "value": 409, "code": "invalid_run_transition"}
    ],
    "AC-021-N-1": [{"kind": "http_status", "value": 200}],
    "AC-021-N-2": [{"kind": "http_status", "value": 200}],
    "AC-021-N-3": [{"kind": "http_status", "value": 200}],
    "AC-021-B-3": [
        {"kind": "http_status", "value": 409, "code": "continue_not_supported"}
    ],
    "AC-021-B-4": [{"kind": "http_status", "value": 200}],
    "AC-021-E-2": [
        {"kind": "http_status", "value": 409, "code": "invalid_run_transition"}
    ],
    "AC-021-F-1": [
        {"kind": "http_status", "value": 500, "code": "atomic_write_failed"}
    ],
    "AC-022-N-2": [{"kind": "http_status", "value": 200}],
    "AC-022-N-5": [{"kind": "http_status", "value": 200}],
    "AC-022-B-3": [{"kind": "http_status", "value": 200}],
    "AC-022-E-1": [
        {"kind": "http_status", "value": 422, "code": "validation_failed"}
    ],
    "AC-022-E-2": [
        {
            "kind": "http_status",
            "value": 409,
            "code": "intervention_already_answered",
        }
    ],
}


def generate_manifest(ac_path: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for row in parse_ac(ac_path):
        ac_id = row["ac_id"]
        if ac_id not in TARGETS:
            raise ValueError(f"target mapping missing for {ac_id}")
        expectations = EXPECTATIONS.get(ac_id)
        if expectations is None:
            target = TARGETS[ac_id][0]
            if target.startswith("ui:"):
                expectations = [{"kind": "dom", "value": "matches-ac"}]
            elif target.startswith("process:"):
                expectations = [{"kind": "process", "value": "matches-ac"}]
            else:
                expectations = [{"kind": "unit", "value": "matches-ac"}]
        cases.append(
            {
                **row,
                "test_node": TEST_NODES.get(ac_id, f"planned::{ac_id.lower()}"),
                "targets": TARGETS[ac_id],
                "expectations": expectations,
            }
        )
    return {"version": 1, "profile": "recovery", "source": str(ac_path), "cases": cases}


def check_manifest(
    manifest: dict[str, Any], ac_path: Path, *, allow_planned: bool = False
) -> list[str]:
    errors: list[str] = []
    source_rows = {row["ac_id"]: row for row in parse_ac(ac_path)}
    cases = manifest.get("cases")
    if manifest.get("version") != 1 or manifest.get("profile") != "recovery" or not isinstance(cases, list):
        return ["recovery manifest must have version=1, profile=recovery, and cases array"]
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case[{index}] must be an object")
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
        targets = case.get("targets")
        if targets != TARGETS.get(ac_id):
            errors.append(f"{ac_id}: targets do not match frozen mapping")
        if isinstance(targets, list) and any("/resume" in str(target) for target in targets):
            errors.append(f"{ac_id}: deprecated Web /resume endpoint is forbidden")
        node = case.get("test_node")
        if not isinstance(node, str) or not node:
            errors.append(f"{ac_id}: test_node is required")
        elif node.startswith("planned::") and not allow_planned:
            errors.append(f"{ac_id}: planned test node is not allowed in strict mode")
        elif ac_id in TEST_NODES and node != TEST_NODES[ac_id]:
            errors.append(f"{ac_id}: test_node does not match implemented mapping")
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
