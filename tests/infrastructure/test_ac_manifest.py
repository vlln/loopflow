from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.web_support.ac_manifest import (
    SUPERSEDED_AC_IDS,
    TEST_NODES,
    check_manifest,
    generate_manifest,
    read_manifest,
)


AC_PATH = Path("docs/ac/0010-webui.md")
MANIFEST_PATH = Path("tests/system/cases.json")


def test_generated_manifest_covers_every_frozen_scenario():
    manifest = generate_manifest(AC_PATH)

    assert check_manifest(manifest, AC_PATH, allow_planned=True) == []
    assert len(manifest["cases"]) == 86


def test_committed_manifest_matches_generator():
    assert read_manifest(MANIFEST_PATH) == generate_manifest(AC_PATH)


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

    planned = [
        case for case in manifest["cases"]
        if case["ac_id"] not in SUPERSEDED_AC_IDS
        and case["test_node"].startswith("planned::")
    ]
    assert len(errors) == len(planned)
    assert all("planned test node is not allowed" in error for error in errors)


def test_manifest_checker_rejects_mapping_drift_and_unmapped_nodes():
    manifest = generate_manifest(AC_PATH)
    mapped_cases = [case for case in manifest["cases"] if case["ac_id"] in TEST_NODES]
    mapped = mapped_cases[0]
    mapped["test_node"] = "tests/unit/test_web_application.py::test_missing"
    downgraded = mapped_cases[1]
    downgraded["test_node"] = f"planned::{downgraded['ac_id'].lower()}"

    planned = next(
        case for case in manifest["cases"]
        if case["ac_id"] not in SUPERSEDED_AC_IDS
        and case["ac_id"] not in TEST_NODES
    )
    planned["test_node"] = "tests/unit/test_web_application.py::test_missing"

    another_planned = next(
        case for case in manifest["cases"]
        if case["ac_id"] not in SUPERSEDED_AC_IDS
        and case["ac_id"] not in TEST_NODES
        and case is not planned
    )
    another_planned["test_node"] = next(iter(TEST_NODES.values()))

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"{mapped['ac_id']}: test_node does not match implemented mapping" in errors
    assert f"{downgraded['ac_id']}: test_node does not match implemented mapping" in errors
    assert f"{planned['ac_id']}: no implemented test_node mapping" in errors
    assert f"{another_planned['ac_id']}: no implemented test_node mapping" in errors


def test_manifest_checker_rejects_missing_implemented_node(monkeypatch):
    manifest = generate_manifest(AC_PATH)
    mapped = next(case for case in manifest["cases"] if case["ac_id"] in TEST_NODES)
    missing = "tests/unit/test_web_application.py::test_missing"
    monkeypatch.setitem(TEST_NODES, mapped["ac_id"], missing)
    mapped["test_node"] = missing

    errors = check_manifest(manifest, AC_PATH, allow_planned=True)

    assert f"{mapped['ac_id']}: test_node does not exist" in errors
