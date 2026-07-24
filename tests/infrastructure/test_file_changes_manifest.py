from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.file_changes_support.manifest import check_manifest, generate_manifest


AC_PATH = Path("docs/ac/0012-file-changes.md")


def test_generated_manifest_covers_every_frozen_scenario():
    manifest = generate_manifest(AC_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []
    assert len(manifest["cases"]) == 20


def test_manifest_checker_rejects_missing_scenario():
    manifest = generate_manifest(AC_PATH)
    missing = manifest["cases"].pop()

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert errors == [f"missing AC ids: {missing['ac_id']}"]


def test_manifest_checker_rejects_interface_drift_and_empty_assertion():
    manifest = deepcopy(generate_manifest(AC_PATH))
    case = next(item for item in manifest["cases"] if item["ac_id"] == "AC-024-N-7")
    case["expectations"][0]["value"] = "run_event"
    case["assertion"] = ""

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert "AC-024-N-7: assertion does not match AC source" in errors


def test_strict_manifest_has_no_planned_nodes():
    """All planned:: nodes have been replaced with real test references."""
    manifest = generate_manifest(AC_PATH)

    errors = check_manifest(manifest, AC_PATH)

    # No planned nodes should remain — strict mode should pass with zero errors
    assert errors == [], f"Unexpected manifest errors: {errors}"
    # Verify no test_node starts with planned::
    assert all(not case["test_node"].startswith("planned::") for case in manifest["cases"])
