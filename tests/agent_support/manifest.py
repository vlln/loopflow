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
        "AC-001-N-1 AC-001-N-2 AC-001-N-3 AC-001-B-1 AC-001-B-2 AC-001-F-1 "
        "AC-001-N-4 AC-001-B-3 AC-001-B-4 "
        "AC-002-N-1 AC-002-N-2 AC-002-N-3 AC-002-N-4 "
        "AC-003-N-1 AC-003-N-2 "
        "AC-004-N-1 AC-004-N-2 AC-004-N-3",
        "unit:agent",
    )
    assign("AC-001-E-1", "unit:agent", "process:cli-run")
    assign("AC-001-F-2", "process:cli-run")
    assign("AC-030-N-1 AC-030-N-2 AC-030-B-1 AC-030-B-2 AC-030-E-1", "process:cli-run")
    assign("AC-030-F-1", "process:cli-recover")
    return targets


TARGETS = _targets()

TEST_NODES: dict[str, str] = {
    # AC-001: Agent 类基本功能
    "AC-001-N-1": "tests/unit/test_runtime.py::TestAgent::test_agent_returns_text",
    "AC-001-N-2": "tests/unit/test_runtime.py::TestAgentDef::test_agent_def_default",
    "AC-001-N-3": "tests/unit/test_runtime.py::TestAgentDef::test_agent_def_skill_found_no_error",
    "AC-001-B-1": "tests/unit/test_runtime.py::TestAgentDef::test_agent_def_no_skills_no_warning",
    "AC-001-B-2": "tests/unit/test_runtime.py::TestOutputSchema::test_no_schema_injection_without_output",
    "AC-001-F-1": "tests/unit/test_runtime.py::TestAgentDef::test_agent_def_missing_skills_blocks",
    # AC-002: 能力 Marshalling
    "AC-002-N-1": "tests/unit/test_runtime.py::TestGoalMode::test_goal_completes_in_one_iteration",
    "AC-002-N-2": "tests/unit/test_runtime.py::TestGoalMode::test_goal_completes_after_multiple_iterations",
    "AC-002-N-3": "tests/unit/test_runtime.py::TestOutputSchema::test_auto_schema_from_agent_def",
    "AC-002-N-4": "tests/unit/test_runtime.py::TestOutputSchema::test_schema_injected_into_prompt",
    # AC-003: runtime.py 简化
    "AC-003-N-1": "tests/unit/test_runtime.py::TestAgent::test_agent_returns_text",
    "AC-003-N-2": "tests/unit/test_runtime.py::TestAgentDef::test_agent_def_default",
    # AC-004: 向后兼容
    "AC-004-N-1": "tests/unit/test_smoke.py::test_import",
    "AC-004-N-2": "tests/unit/test_runtime.py::TestGoalMode::test_goal_does_not_affect_existing_agent_call",
    "AC-004-N-3": "tests/unit/test_runtime.py::TestAgentDef::test_agent_def_skill_found_no_error",
    # AC-001 BL-018 追加场景：parse_agent 剥离 frontmatter
    "AC-001-N-4": "tests/unit/test_agent.py::TestParseAgentFrontmatter::test_ac001_n4_body_excludes_frontmatter",
    "AC-001-B-3": "tests/unit/test_agent.py::TestParseAgentFrontmatter::test_ac001_b3_missing_frontmatter_raises",
    "AC-001-B-4": "tests/unit/test_agent.py::TestParseAgentFrontmatter::test_ac001_b4_invalid_yaml_raises",
    "AC-001-E-1": "tests/unit/test_agent.py::TestParseAgentFrontmatter::test_ac001_e1_body_horizontal_rule_preserved",
    "AC-001-F-2": "tests/integration/test_cli.py::TestPiBackendArgv::test_ac001_f2_frontmatter_stripped_prompt_not_an_unknown_option",
    # AC-030: ACP 后端 loop 端到端
    "AC-030-N-1": "tests/integration/test_acp_sdk_backend.py::test_ac_030_n_1_acp_backend_loop_end_to_end",
    "AC-030-N-2": "tests/integration/test_acp_sdk_backend.py::test_ac_030_n_2_notification_full_mapping",
    "AC-030-B-1": "tests/integration/test_acp_sdk_backend.py::test_ac_030_b_1_permission_auto_approve",
    "AC-030-B-2": "tests/integration/test_acp_sdk_backend.py::test_ac_030_b_2_missing_acp_extra_error",
    "AC-030-E-1": "tests/integration/test_acp_sdk_backend.py::test_ac_030_e_1_backend_startup_failure",
    "AC-030-F-1": "tests/integration/test_acp_sdk_backend.py::test_ac_030_f_1_continue_with_session_load",
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
    return {"version": 1, "profile": "agent", "source": str(ac_path), "cases": cases}


def check_manifest(
    manifest: dict[str, Any], ac_path: Path, *, allow_planned: bool = False
) -> list[str]:
    errors: list[str] = []
    source_rows = {row["ac_id"]: row for row in parse_ac(ac_path)}
    cases = manifest.get("cases")
    if manifest.get("version") != 1 or manifest.get("profile") != "agent" or not isinstance(cases, list):
        return ["agent manifest must have version=1, profile=agent, and cases array"]
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
