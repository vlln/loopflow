from pathlib import Path


def test_mr_gate_allows_planned_during_incremental_develop():
    script = Path("scripts/mr-gate.sh").read_text(encoding="utf-8")

    assert "INIT|DESIGN|TEST_INFRA|DEVELOP" in script
    assert "--allow-planned" in script


def test_mr_gate_uses_strict_manifest_from_system_test_onward():
    script = Path("scripts/mr-gate.sh").read_text(encoding="utf-8")

    condition, strict_branch = script.split("else", 1)
    assert "SYSTEM_TEST" not in condition
    assert "check-ac-manifest.py\n" in strict_branch
