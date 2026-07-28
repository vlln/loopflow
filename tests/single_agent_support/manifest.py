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

    assign(
        "AC-032-N-1 AC-032-N-2 AC-032-B-1 AC-032-B-2 "
        "AC-032-E-1 AC-032-E-2 AC-032-E-3 AC-032-F-1",
        "process:cli-run",
    )
    assign("AC-032-N-3", "process:cli-recover")
    return targets


TARGETS = _targets()

TEST_NODES: dict[str, str] = {
    "AC-032-N-1": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_n1_single_agent_run_done_and_workflow_digest_none",
    "AC-032-N-2": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_n2_output_schema_json_stdout",
    "AC-032-N-3": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_n3_recover_retry_reruns_call",
    "AC-032-B-1": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_b1_param_rendering_and_missing_param",
    "AC-032-B-2": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_b2_waiting_input",
    "AC-032-E-1": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_e1_unknown_agent_def",
    "AC-032-E-2": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_e2_args_rejected",
    "AC-032-E-3": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_e3_prompt_mutex",
    "AC-032-F-1": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac032_f1_backend_failure_recoverable",
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
    return {"version": 1, "profile": "singleagent", "source": str(ac_path), "cases": cases}


def check_manifest(
    manifest: dict[str, Any], ac_path: Path, *, allow_planned: bool = False
) -> list[str]:
    errors: list[str] = []
    source_rows = {row["ac_id"]: row for row in parse_ac(ac_path)}
    cases = manifest.get("cases")
    if manifest.get("version") != 1 or manifest.get("profile") != "singleagent" or not isinstance(cases, list):
        return ["singleagent manifest must have version=1, profile=singleagent, and cases array"]
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
