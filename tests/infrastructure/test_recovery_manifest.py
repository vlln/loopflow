from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.recovery_support.manifest import check_manifest, generate_manifest


AC_PATH = Path("docs/ac/0011-recovery-intervention.md")


def test_recovery_manifest_covers_every_frozen_scenario():
    manifest = generate_manifest(AC_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []
    assert len(manifest["cases"]) == len({case["ac_id"] for case in manifest["cases"]})


def test_recovery_manifest_rejects_missing_and_duplicate_scenarios():
    manifest = generate_manifest(AC_PATH)
    missing = manifest["cases"].pop()
    manifest["cases"].append(deepcopy(manifest["cases"][0]))

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"missing AC ids: {missing['ac_id']}" in errors
    assert any(error.startswith("duplicate AC id:") for error in errors)


def test_recovery_manifest_rejects_deprecated_web_resume_endpoint():
    manifest = generate_manifest(AC_PATH)
    case = next(item for item in manifest["cases"] if item["ac_id"] == "AC-020-N-1")
    case["targets"] = ["POST /api/v1/runs/{run_id}/resume"]

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert "AC-020-N-1: targets do not match frozen mapping" in errors
    assert "AC-020-N-1: deprecated Web /resume endpoint is forbidden" in errors


def test_recovery_manifest_rejects_wrong_error_status_and_planned_nodes():
    manifest = generate_manifest(AC_PATH)
    case = next(item for item in manifest["cases"] if item["ac_id"] == "AC-020-E-2")
    case["expectations"][0]["value"] = 200

    errors = check_manifest(manifest, AC_PATH)

    assert "AC-020-E-2: continue_not_supported must use HTTP 409" in errors
    planned = sum(case["test_node"].startswith("planned::") for case in manifest["cases"])
    assert sum("planned test node is not allowed" in error for error in errors) == planned
