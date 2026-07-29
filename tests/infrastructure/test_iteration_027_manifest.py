from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.iteration_027_support.manifest import (
    check_manifest,
    generate_manifest,
    read_manifest,
)


AC_PATH = Path("docs/ac/0015-iteration-0.27.0.md")
MANIFEST_PATH = Path("tests/system/iteration_027_cases.json")


def test_iteration_027_manifest_covers_every_frozen_scenario():
    manifest = generate_manifest(AC_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []
    assert len(manifest["cases"]) == len({case["ac_id"] for case in manifest["cases"]})


def test_iteration_027_committed_manifest_matches_frozen_mapping():
    assert check_manifest(read_manifest(MANIFEST_PATH), AC_PATH, allow_planned=True) == []


def test_iteration_027_manifest_rejects_missing_and_duplicate_scenarios():
    manifest = generate_manifest(AC_PATH)
    missing = manifest["cases"].pop()
    manifest["cases"].append(deepcopy(manifest["cases"][0]))

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"missing AC ids: {missing['ac_id']}" in errors
    assert any(error.startswith("duplicate AC id:") for error in errors)


def test_iteration_027_manifest_rejects_wrong_error_status_and_planned_nodes():
    manifest = generate_manifest(AC_PATH)
    case = next(item for item in manifest["cases"] if item["ac_id"] == "AC-033-F-2")
    case["expectations"][0]["value"] = 200

    errors = check_manifest(manifest, AC_PATH)

    assert "AC-033-F-2: file_read_failed must use HTTP 500" in errors
    assert sum("planned test node is not allowed" in error for error in errors) == len(
        manifest["cases"]
    )
