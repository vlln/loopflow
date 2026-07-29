from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from tests.web_support.ac_manifest import parse_ac


VALID_KINDS = {"http_status", "cli_exit", "dom", "process", "unit"}
HTTP_STATUS_BY_CODE = {
    "path_forbidden": 403,
    "file_not_found": 404,
    "validation_failed": 422,
    "file_not_previewable": 422,
    "file_read_failed": 500,
}


def _targets() -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}

    def assign(ids: str, *values: str) -> None:
        for ac_id in ids.split():
            targets[ac_id] = list(values)

    assign(
        "AC-033-N-1",
        "GET /api/v1/runs/{run_id}/file",
        "GET /api/v1/runs/{run_id}/file/raw",
    )
    assign(
        "AC-033-N-2",
        "GET /api/v1/loops/{loop_name}/file",
        "GET /api/v1/loops/{loop_name}/file/raw",
        "ui:file-preview",
    )
    assign("AC-033-N-3", "GET /api/v1/runs/{run_id}/file/raw", "ui:file-preview")
    assign("AC-033-B-1", "GET /api/v1/runs/{run_id}/file/raw")
    assign("AC-033-B-2 AC-033-B-3 AC-033-B-4", "GET /api/v1/runs/{run_id}/file")
    assign(
        "AC-033-E-1",
        "GET /api/v1/runs/{run_id}/file/raw",
        "GET /api/v1/loops/{loop_name}/file/raw",
    )
    assign("AC-033-E-2", "GET /api/v1/runs/{run_id}/file/raw", "ui:file-preview")
    assign(
        "AC-033-F-1",
        "GET /api/v1/runs/{run_id}/file",
        "GET /api/v1/runs/{run_id}/file/raw",
    )
    assign(
        "AC-033-F-2",
        "GET /api/v1/runs/{run_id}/file/raw",
        "GET /api/v1/runs",
    )

    assign("AC-034-N-1", "process:cli-run", "unit:run-append-prompt")
    assign("AC-034-N-2", "POST /api/v1/runs", "ui:new-run", "unit:run-append-prompt")
    assign("AC-034-N-3", "process:cli-run", "unit:run-append-prompt")
    assign("AC-034-B-1", "unit:run-append-prompt")
    assign("AC-034-B-2", "process:cli-run", "POST /api/v1/runs")
    assign("AC-034-E-1", "process:cli-run")
    assign("AC-034-E-2", "POST /api/v1/runs/{run_id}/recover")
    assign("AC-034-E-3", "POST /api/v1/runs")
    assign("AC-034-E-4", "ui:new-run")
    assign("AC-034-F-1", "unit:call-input-digest")
    assign("AC-034-F-2", "unit:run-append-prompt")

    assign(
        "AC-035-N-1 AC-035-N-2 AC-035-B-1 AC-035-B-2 AC-035-E-1",
        "GET /api/v1/loops/{loop_name}",
        "ui:new-run",
    )
    assign("AC-035-E-2", "GET /api/v1/loops/{loop_name}", "unit:declared-args")
    assign("AC-035-F-1", "GET /api/v1/loops", "ui:new-run")
    return targets


TARGETS = _targets()

TEST_NODES = {
    "AC-033-N-1": "tests/integration/test_web_api.py::test_ac033_run_raw_preview_uses_fixed_media_types_and_headers",
    "AC-033-N-2": "web/src/App.test.tsx::AC-033-N-2: Loop PDF uses the raw viewer instead of a text pre",
    "AC-033-N-3": "web/tests/webui.spec.ts::AC-033-N-3: image preview stays in viewport without shifting file tree",
    "AC-033-B-1": "tests/unit/test_web_resources.py::test_ac033_loop_preview_accepts_exact_text_and_raw_limits",
    "AC-033-B-2": "tests/integration/test_web_api.py::test_run_file_preview_rejects_binary_and_oversized",
    "AC-033-B-3": "tests/integration/test_web_api.py::test_run_file_preview_returns_text_content",
    "AC-033-B-4": "tests/integration/test_web_api.py::test_run_file_preview_rejects_binary_and_oversized",
    "AC-033-E-1": "tests/integration/test_web_api.py::test_ac033_raw_rejects_non_whitelisted_oversized_and_escaped_paths",
    "AC-033-E-2": "web/src/App.test.tsx::AC-033-E-2: raw media failure replaces the broken preview with an error",
    "AC-033-F-1": "tests/unit/test_web_resources.py::test_ac033_loop_preview_binary_rejects_oversized",
    "AC-033-F-2": "tests/integration/test_web_api.py::test_ac033_raw_reader_failure_returns_file_error_before_success_headers",
    "AC-034-N-1": "tests/integration/test_cli.py::TestCLIRun::test_ac034_n1_cli_persists_and_appends_to_every_workflow_agent",
    "AC-034-N-2": "tests/integration/test_web_api.py::test_ac034_n2_http_value_reaches_workflow_agent_prompt",
    "AC-034-N-3": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac034_n3_single_agent_forwards_append_prompt",
    "AC-034-B-1": "tests/unit/test_runtime.py::TestAgent::test_ac034_b1_empty_append_prompt_injects_no_empty_tags",
    "AC-034-B-2": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac034_b2_e1_cli_validates_utf8_limit_before_run_creation",
    "AC-034-E-1": "tests/integration/test_cli.py::TestSingleAgentRun::test_ac034_b2_e1_cli_validates_utf8_limit_before_run_creation",
    "AC-034-E-2": "tests/unit/test_web_application.py::test_ac034_e2_recover_rejects_append_prompt_without_starting_worker",
    "AC-034-E-3": "tests/integration/test_web_api.py::test_ac034_n2_b2_e3_run_create_append_prompt_http_contract",
    "AC-034-E-4": "web/src/App.test.tsx::AC-034-E-4: oversized UTF-8 append prompt is rejected without POST",
    "AC-034-F-1": "tests/unit/test_runtime.py::TestAgent::test_ac034_f1_append_prompt_tamper_diverges_before_cache_hit",
    "AC-034-F-2": "tests/unit/test_runtime.py::TestAgent::test_ac034_n1_f2_append_prompt_is_last_user_segment_only",
    "AC-035-N-1": "web/src/App.test.tsx::AC-014-N-10: declared args prefill the editor and empty rows are skipped on submit",
    "AC-035-N-2": "web/src/App.test.tsx::AC-035-N-2: Editor and JSON modes preserve the same arguments",
    "AC-035-B-1": "web/src/App.test.tsx::AC-014-B-5: a loop without declared args starts with a blank editor",
    "AC-035-B-2": "web/src/App.test.tsx::AC-035-B-2: declared defaults preserve false zero object empty and string types",
    "AC-035-E-1": "web/src/App.test.tsx::AC-035-E-1: malformed declarations are ignored and only valid names are prefilled",
    "AC-035-E-2": "tests/unit/test_web_resources.py::test_ac035_loop_md_top_level_args_and_legacy_workflow_fallback",
    "AC-035-F-1": "web/src/App.test.tsx::AC-035-F-1: loop loading failure disables New Run and clears arguments",
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

EXPECTATIONS: dict[str, list[dict[str, Any]]] = {
    "AC-033-N-1": [{"kind": "http_status", "value": 200}],
    "AC-033-N-2": [
        {"kind": "http_status", "value": 200},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-033-N-3": [
        {"kind": "http_status", "value": 200},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-033-B-1": [{"kind": "http_status", "value": 200}],
    "AC-033-B-2": [
        {"kind": "http_status", "value": 422, "code": "file_not_previewable"}
    ],
    "AC-033-B-3": [{"kind": "http_status", "value": 200}],
    "AC-033-B-4": [
        {"kind": "http_status", "value": 422, "code": "file_not_previewable"}
    ],
    "AC-033-E-1": [{"kind": "http_status", "value": 403, "code": "path_forbidden"}],
    "AC-033-E-2": [
        {"kind": "http_status", "value": 404, "code": "file_not_found"},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-033-F-1": [
        {"kind": "http_status", "value": 422, "code": "file_not_previewable"}
    ],
    "AC-033-F-2": [
        {"kind": "http_status", "value": 500, "code": "file_read_failed"},
        {"kind": "http_status", "value": 200},
    ],
    "AC-034-N-2": [{"kind": "http_status", "value": 201}],
    "AC-034-B-2": [
        {"kind": "process", "value": "matches-ac"},
        {"kind": "http_status", "value": 201},
    ],
    "AC-034-E-1": [{"kind": "cli_exit", "value": "nonzero"}],
    "AC-034-E-2": [
        {"kind": "http_status", "value": 422, "code": "validation_failed"}
    ],
    "AC-034-E-3": [
        {"kind": "http_status", "value": 422, "code": "validation_failed"}
    ],
    "AC-034-E-4": [{"kind": "dom", "value": "matches-ac"}],
    "AC-035-N-1": [
        {"kind": "http_status", "value": 200},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-035-N-2": [
        {"kind": "http_status", "value": 200},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-035-B-1": [
        {"kind": "http_status", "value": 200},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-035-B-2": [
        {"kind": "http_status", "value": 200},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-035-E-1": [
        {"kind": "http_status", "value": 200},
        {"kind": "dom", "value": "matches-ac"},
    ],
    "AC-035-F-1": [{"kind": "dom", "value": "matches-ac"}],
}


def _default_expectations(targets: list[str]) -> list[dict[str, Any]]:
    first = targets[0]
    if first.startswith("ui:"):
        return [{"kind": "dom", "value": "matches-ac"}]
    if first.startswith("process:"):
        return [{"kind": "process", "value": "matches-ac"}]
    if first.startswith("GET ") or first.startswith("POST "):
        return [{"kind": "http_status", "value": 200}]
    return [{"kind": "unit", "value": "matches-ac"}]


def generate_manifest(ac_path: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for row in parse_ac(ac_path):
        ac_id = row["ac_id"]
        if ac_id not in TARGETS:
            raise ValueError(f"target mapping missing for {ac_id}")
        cases.append(
            {
                **row,
                "test_node": TEST_NODES.get(ac_id, f"planned::{ac_id.lower()}"),
                "targets": TARGETS[ac_id],
                "expectations": deepcopy(
                    EXPECTATIONS.get(ac_id, _default_expectations(TARGETS[ac_id]))
                ),
            }
        )
    return {
        "version": 1,
        "profile": "iteration027",
        "source": str(ac_path),
        "cases": cases,
    }


def check_manifest(
    manifest: dict[str, Any], ac_path: Path, *, allow_planned: bool = False
) -> list[str]:
    errors: list[str] = []
    source_rows = {row["ac_id"]: row for row in parse_ac(ac_path)}
    cases = manifest.get("cases")
    if (
        manifest.get("version") != 1
        or manifest.get("profile") != "iteration027"
        or not isinstance(cases, list)
    ):
        return ["iteration027 manifest must have version=1, profile=iteration027, and cases array"]

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
        for field in ("fixture", "action", "assertion"):
            if not case.get(field) or case.get(field) != source_rows[ac_id][field]:
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
        elif not node.startswith("planned::") and not _test_node_exists(node):
            errors.append(f"{ac_id}: test_node does not exist")
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
                elif (
                    expectation.get("kind") != "http_status"
                    or expectation.get("value") != expected_status
                ):
                    errors.append(f"{ac_id}: {code} must use HTTP {expected_status}")
    missing = sorted(set(source_rows) - seen)
    if missing:
        errors.append(f"missing AC ids: {', '.join(missing)}")
    return errors


def read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
