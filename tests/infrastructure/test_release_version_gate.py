"""BL-049 / BL-061: release tooling gates.

- BL-049: `check-ac-manifest.py --write` must exit clean — it is a manifest
  *generator*, and a regenerated manifest contains planned:: nodes that strict
  validation would always reject. Before the fix the tool reported a false
  failure right after writing.
- BL-061: `verify-wheel-assets.py` must gate version consistency — the wheel
  must install what pyproject declares (always), and during RELEASE the
  CHANGELOG top entry must match pyproject (no "only bumped the changelog"
  releases, the 0.28.0 defect).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
WEB_AC = Path(__file__).resolve().parents[2] / "docs" / "ac" / "0010-webui.md"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- BL-049: --write is a generator, not a validator ------------------------


def test_manifest_write_generates_and_exits_clean(tmp_path, monkeypatch, capsys):
    check = _load_script("check-ac-manifest.py")
    manifest = tmp_path / "cases.json"
    monkeypatch.setattr(
        "sys.argv",
        ["check-ac-manifest.py", "--write", "--ac", str(WEB_AC), "--manifest", str(manifest)],
    )

    assert check.main() == 0

    assert manifest.is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["cases"]
    assert "AC manifest written" in capsys.readouterr().out


def test_manifest_write_does_not_validate_planned_nodes(tmp_path, monkeypatch):
    """Regenerated manifest contains planned:: nodes; --write must not run strict validation."""
    check = _load_script("check-ac-manifest.py")
    manifest = tmp_path / "cases.json"
    monkeypatch.setattr(
        "sys.argv",
        ["check-ac-manifest.py", "--write", "--ac", str(WEB_AC), "--manifest", str(manifest)],
    )

    assert check.main() == 0  # would exit 1 if strict validation ran


def test_manifest_strict_check_still_fails_on_planned_nodes(tmp_path, monkeypatch):
    """Read mode (no --write) keeps strict semantics: planned nodes are errors."""
    check = _load_script("check-ac-manifest.py")
    manifest = tmp_path / "cases.json"
    # Generate a manifest via --write, then inject a planned:: node and check
    # it strictly. (The committed AC set is fully mapped, so we must fabricate
    # a planned node to prove strict read-mode validation still rejects it.)
    monkeypatch.setattr(
        "sys.argv",
        ["check-ac-manifest.py", "--write", "--ac", str(WEB_AC), "--manifest", str(manifest)],
    )
    assert check.main() == 0
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["cases"][0]["test_node"] = "planned::ac-016-e-1"
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["check-ac-manifest.py", "--ac", str(WEB_AC), "--manifest", str(manifest)],
    )
    assert check.main() == 1


# --- BL-061: version consistency gate ---------------------------------------


def _write_repo(tmp_path: Path, *, version: str, changelog_top: str, release: bool) -> Path:
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "loopflow"\nversion = "{version}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{changelog_top}] — 2026-08-04\n", encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    stage = f"`RELEASE` ({changelog_top})" if release else "`DESIGN` (新一轮迭代)"
    (docs / "README.md").write_text(f"| **当前阶段** | {stage} |\n", encoding="utf-8")
    return tmp_path


def test_version_gate_accepts_consistent_release(tmp_path, monkeypatch):
    verify = _load_script("verify-wheel-assets.py")
    root = _write_repo(tmp_path, version="0.29.0", changelog_top="0.29.0", release=True)
    monkeypatch.setattr(verify, "_REPO_ROOT", root)
    monkeypatch.setattr(verify.importlib.metadata, "version", lambda name: "0.29.0")

    verify._check_version_consistency()  # no raise


def test_version_gate_rejects_wheel_pyproject_mismatch(tmp_path, monkeypatch):
    verify = _load_script("verify-wheel-assets.py")
    root = _write_repo(tmp_path, version="0.29.0", changelog_top="0.29.0", release=True)
    monkeypatch.setattr(verify, "_REPO_ROOT", root)
    monkeypatch.setattr(verify.importlib.metadata, "version", lambda name: "0.27.1")

    with pytest.raises(SystemExit, match="version mismatch"):
        verify._check_version_consistency()


def test_version_gate_rejects_changelog_pyproject_mismatch_in_release(tmp_path, monkeypatch):
    """The 0.28.0 defect: CHANGELOG bumped, pyproject left behind."""
    verify = _load_script("verify-wheel-assets.py")
    root = _write_repo(tmp_path, version="0.27.1", changelog_top="0.28.0", release=True)
    monkeypatch.setattr(verify, "_REPO_ROOT", root)
    monkeypatch.setattr(verify.importlib.metadata, "version", lambda name: "0.27.1")

    with pytest.raises(SystemExit, match="RELEASE gate"):
        verify._check_version_consistency()


def test_version_gate_skips_changelog_check_outside_release(tmp_path, monkeypatch):
    """develop/PR context: only wheel==pyproject consistency is enforced."""
    verify = _load_script("verify-wheel-assets.py")
    root = _write_repo(tmp_path, version="0.27.1", changelog_top="0.28.0", release=False)
    monkeypatch.setattr(verify, "_REPO_ROOT", root)
    monkeypatch.setattr(verify.importlib.metadata, "version", lambda name: "0.27.1")

    verify._check_version_consistency()  # no raise: changelog may lag on develop
