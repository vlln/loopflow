from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.scheduling_support.manifest import (
    TEST_NODES,
    check_manifest,
    generate_manifest,
    read_manifest,
)


AC_PATH = Path("docs/ac/0004-scheduling.md")
MANIFEST_PATH = Path("tests/system/scheduling_cases.json")


def test_scheduling_manifest_covers_every_frozen_scenario():
    manifest = generate_manifest(AC_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []
    assert len(manifest["cases"]) == len({case["ac_id"] for case in manifest["cases"]})


def test_scheduling_manifest_committed_file_matches_frozen_mapping():
    manifest = read_manifest(MANIFEST_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []


def test_scheduling_manifest_rejects_missing_and_duplicate_scenarios():
    manifest = generate_manifest(AC_PATH)
    missing = manifest["cases"].pop()
    manifest["cases"].append(deepcopy(manifest["cases"][0]))

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"missing AC ids: {missing['ac_id']}" in errors
    assert any(error.startswith("duplicate AC id:") for error in errors)


def test_scheduling_manifest_pins_implemented_nodes_and_rejects_planned_in_strict():
    manifest = generate_manifest(AC_PATH)
    implemented = [case for case in manifest["cases"] if case["ac_id"] in TEST_NODES]
    planned = [case for case in manifest["cases"] if case["ac_id"] not in TEST_NODES]
    assert len(implemented) == len(TEST_NODES) == 21
    assert len(planned) == 11

    implemented[0]["test_node"] = "tests/unit/test_queue.py::bogus"

    errors = check_manifest(manifest, AC_PATH)

    assert any("test_node does not match implemented mapping" in error for error in errors)
    assert sum("planned test node is not allowed" in error for error in errors) == len(planned)


def test_scheduling_manifest_rejects_invalid_expectation_kind():
    manifest = generate_manifest(AC_PATH)
    case = next(item for item in manifest["cases"] if item["ac_id"] == "AC-012-N-3")
    case["expectations"] = [{"kind": "http_status", "value": 200}]

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert "AC-012-N-3: invalid expectation kind" in errors
