from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.web_support.ac_manifest import check_manifest, generate_manifest


AC_PATH = Path("docs/ac/0010-webui.md")


def test_generated_manifest_covers_every_frozen_scenario():
    manifest = generate_manifest(AC_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []
    assert len(manifest["cases"]) == 60


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

    assert len(errors) == len(manifest["cases"])
    assert all("planned test node is not allowed" in error for error in errors)
