from pathlib import Path
import re


def test_mr_gate_allows_planned_during_incremental_develop():
    """The gate branches on phase: incremental phases (INIT..DEVELOP) use --allow-planned.

    This asserts the script structure, not the repo's current phase — the gate must
    work whether the repo is mid-DEVELOP or already past it.
    """
    script = Path("scripts/mr-gate.sh").read_text(encoding="utf-8")

    assert "INIT|DESIGN|TEST_INFRA|DEVELOP" in script
    assert "--allow-planned" in script
    # the phase regex matches the incremental-phase README form
    pattern = re.search(r"grep -Eq '([^']+)' docs/README.md", script).group(1)
    develop_readme = "| **当前阶段** | `DEVELOP` (example) |"
    assert re.search(pattern, develop_readme)
    release_readme = "| **当前阶段** | `RELEASE` (example) |"
    assert not re.search(pattern, release_readme)


def test_mr_gate_uses_strict_manifest_from_system_test_onward():
    script = Path("scripts/mr-gate.sh").read_text(encoding="utf-8")

    condition, strict_branch = script.split("else", 1)
    assert "SYSTEM_TEST" not in condition
    assert "check-ac-manifest.py\n" in strict_branch
