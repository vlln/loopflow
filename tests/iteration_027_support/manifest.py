from __future__ import annotations

import json
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
                "test_node": f"planned::{ac_id.lower()}",
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
