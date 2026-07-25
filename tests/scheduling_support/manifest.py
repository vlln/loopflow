from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.web_support.ac_manifest import parse_ac


VALID_KINDS = {"cli_exit", "process", "unit"}


def _targets() -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}

    def assign(ids: str, *values: str) -> None:
        for ac_id in ids.split():
            targets[ac_id] = list(values)

    assign("AC-010-N-1 AC-010-N-2 AC-010-E-2", "process:cli-list")
    assign("AC-010-E-1", "unit:discovery")

    assign("AC-011-N-1 AC-011-E-1", "process:cli-enqueue")
    assign("AC-011-N-2", "process:cli-list")

    assign(
        "AC-012-N-1 AC-012-N-2 AC-012-N-3 AC-012-B-1 AC-012-F-1",
        "process:cli-dispatch",
    )

    assign("AC-013-N-1 AC-013-N-2", "unit:resource-lock")
    assign("AC-013-B-1 AC-013-F-1", "process:cli-dispatch")

    assign(
        "AC-027-N-1 AC-027-N-2 AC-027-N-3 AC-027-B-1 AC-027-B-2 AC-027-F-1",
        "unit:loop-state",
    )
    assign("AC-027-N-4 AC-027-E-1", "process:cli-dispatch")
    assign("AC-027-B-3", "process:cli-run")

    assign("AC-028-N-1 AC-028-N-3 AC-028-B-1", "process:cli-enqueue")
    assign("AC-028-N-2 AC-028-N-4 AC-028-E-1 AC-028-F-1", "process:cli-dispatch")
    return targets


TARGETS = _targets()

TEST_NODES = {
    "AC-010-N-1": "tests/integration/test_cli.py::TestCLIRun::test_list_loops_and_runs",
    "AC-010-E-1": "tests/unit/test_discovery.py::TestLoopMd::test_loop_md_missing_name",
    "AC-011-N-1": "tests/unit/test_queue.py::TestEnqueue::test_creates_queue_file",
    "AC-011-N-2": "tests/unit/test_queue.py::TestEnqueue::test_multiple_entries_sorted_by_priority",
    "AC-011-E-1": "tests/e2e/test_scheduling_e2e.py::TestSchedulingE2E::test_enqueue_nonexistent_loop",
    "AC-012-N-1": "tests/e2e/test_scheduling_e2e.py::TestSchedulingE2E::test_enqueue_then_dispatch",
    "AC-012-N-2": "tests/unit/test_dispatch.py::TestDispatchScan::test_priority_ordering",
    "AC-012-N-3": "tests/e2e/test_scheduling_e2e.py::TestSchedulingE2E::test_dispatch_empty_queue",
    "AC-012-B-1": "tests/e2e/test_scheduling_e2e.py::TestSchedulingE2E::test_dispatch_resource_conflict",
    "AC-012-F-1": "tests/e2e/test_scheduling_e2e.py::TestSchedulingE2E::test_dispatch_failed_task_removed",
    "AC-013-N-1": "tests/unit/test_resource_lock.py::TestResourceLock::test_acquire_creates_lock_file",
    "AC-013-N-2": "tests/unit/test_resource_lock.py::TestResourceLock::test_release_deletes_lock_file",
    "AC-013-B-1": "tests/unit/test_resource_lock.py::TestResourceLock::test_stale_lock_cleanup",
    "AC-013-F-1": "tests/unit/test_resource_lock.py::TestResourceLock::test_conflict_detection",
    "AC-028-N-1": "tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_enqueue_writes_pending_status",
    "AC-028-N-2": "tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_dispatch_defers_task_when_resource_locked",
    "AC-028-N-3": "tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_enqueue_supersede_marks_existing_task",
    "AC-028-N-4": "tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_dispatch_skips_and_cleans_superseded",
    "AC-028-B-1": "tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_enqueue_supersede_without_existing_task",
    "AC-028-E-1": "tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_dispatch_treats_unknown_or_missing_status_as_pending",
    "AC-028-F-1": "tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_dispatch_deferred_and_superseded_not_counted_as_errors",
}

EXPECTATIONS: dict[str, list[dict[str, Any]]] = {}


def generate_manifest(ac_path: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for row in parse_ac(ac_path):
        ac_id = row["ac_id"]
        if ac_id not in TARGETS:
            raise ValueError(f"target mapping missing for {ac_id}")
        expectations = EXPECTATIONS.get(ac_id)
        if expectations is None:
            target = TARGETS[ac_id][0]
            if target.startswith("process:"):
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
    return {"version": 1, "profile": "scheduling", "source": str(ac_path), "cases": cases}


def check_manifest(
    manifest: dict[str, Any], ac_path: Path, *, allow_planned: bool = False
) -> list[str]:
    errors: list[str] = []
    source_rows = {row["ac_id"]: row for row in parse_ac(ac_path)}
    cases = manifest.get("cases")
    if manifest.get("version") != 1 or manifest.get("profile") != "scheduling" or not isinstance(cases, list):
        return ["scheduling manifest must have version=1, profile=scheduling, and cases array"]
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
        if case.get("targets") != TARGETS.get(ac_id):
            errors.append(f"{ac_id}: targets do not match frozen mapping")
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
    missing = sorted(set(source_rows) - seen)
    if missing:
        errors.append(f"missing AC ids: {', '.join(missing)}")
    return errors


def read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
