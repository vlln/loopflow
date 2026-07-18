from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest


SCRIPT = Path("scripts/submission-gate.py")


def load_gate_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("submission_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gate_fixture(tmp_path):
    plan = tmp_path / "plan.md"
    report = tmp_path / "report.md"
    readme = tmp_path / "README.md"
    coverage = tmp_path / "coverage.json"
    result = tmp_path / "junit.xml"
    manifest = tmp_path / "cases.json"
    plan.write_text(
        "---\ntype: plan\nstatus: done\n---\n# Acceptance\n- AC-014-N-1\n",
        encoding="utf-8",
    )
    report.write_text(
        "---\ntype: report\nstatus: complete\n---\n# Results\n"
        "| AC-014-N-1 | [PASS] | abc1234 |\n",
        encoding="utf-8",
    )
    readme.write_text("| 01 | Plan | Report | done |\n", encoding="utf-8")
    coverage.write_text(json.dumps({"totals": {"percent_covered": 85}}), encoding="utf-8")
    result.write_text('<testsuite tests="1" failures="0" errors="0"/>', encoding="utf-8")
    manifest.write_text(json.dumps({"cases": [{"ac_id": "AC-014-N-1"}]}), encoding="utf-8")
    return argparse.Namespace(
        plan=plan,
        report=report,
        container_readme=readme,
        manifest=manifest,
        coverage=[f"{coverage}:80"],
        result=[result],
    )


def test_submission_gate_accepts_consistent_evidence(gate_fixture):
    gate = load_gate_module()

    assert gate.run(gate_fixture) == []


@pytest.mark.parametrize("defect", ["report", "ac", "coverage", "result"])
def test_submission_gate_rejects_invalid_evidence(gate_fixture, defect):
    if defect == "report":
        gate_fixture.report.write_text(
            "---\ntype: report\nstatus: draft\n---\nAC-014-N-1 [TODO]\n",
            encoding="utf-8",
        )
    elif defect == "ac":
        gate_fixture.plan.write_text(
            "---\ntype: plan\nstatus: done\n---\n# Acceptance\n- AC-999-N-1\n",
            encoding="utf-8",
        )
    elif defect == "coverage":
        coverage_path = Path(gate_fixture.coverage[0].rpartition(":")[0])
        coverage_path.write_text(
            json.dumps({"totals": {"percent_covered": 79.99}}),
            encoding="utf-8",
        )
    else:
        gate_fixture.result[0].write_text(
            '<testsuite tests="1" failures="1" errors="0"/>',
            encoding="utf-8",
        )

    gate = load_gate_module()

    assert gate.run(gate_fixture)
