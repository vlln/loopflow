"""BL-019/BL-026: 技能前置 preflight 测试。

技能存在但 requires.bins/requires.env 不满足时，build_skill_prompt 应标记
[unavailable: 缺少 ...] 而非静默注入（此前 agent 用到才发现缺失——BL-019 根因）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loopflow.infrastructure.skills import (
    build_skill_prompt,
    find_skill,
    missing_prereqs,
    parse_skill,
)


def _make_skill(tmp_path: Path, name: str, requires: str = "") -> Path:
    """创建带 frontmatter 的技能目录（放 loop/.skills/ 下，_skill_dirs 优先查）。"""
    skill_dir = tmp_path / "loop" / ".skills" / name
    skill_dir.mkdir(parents=True)
    fm = f"---\nname: {name}\ndescription: test skill\n{requires}---\n# {name}\n"
    (skill_dir / "SKILL.md").write_text(fm, encoding="utf-8")
    return tmp_path / "loop" / ".skills"


def _loop_dir(tmp_path: Path) -> Path:
    """loop 目录指向含技能的家目录（.skills 查找）。"""
    loop = tmp_path / "loop"
    loop.mkdir(exist_ok=True)
    return loop


# ── parse_skill：requires 解析 ─────────────────────────────────────────
def test_parse_skill_includes_requires(tmp_path):
    skills_root = _make_skill(tmp_path, "foo", "requires:\n  env:\n    - FOO_URL\n")
    skill = parse_skill(skills_root / "foo")
    assert skill is not None
    assert skill["requires"] == {"env": ["FOO_URL"]}
    assert skill["name"] == "foo"


def test_parse_skill_no_requires(tmp_path):
    skills_root = _make_skill(tmp_path, "bar")
    skill = parse_skill(skills_root / "bar")
    assert skill is not None
    assert skill["requires"] is None


# ── missing_prereqs：bins/env 前置检测 ─────────────────────────────────
def test_missing_prereqs_env(tmp_path, monkeypatch):
    skills_root = _make_skill(tmp_path, "mineru", "requires:\n  env:\n    - MINERU_API_URL\n")
    skill = parse_skill(skills_root / "mineru")
    assert skill is not None
    # env 未设置 → 缺失
    monkeypatch.delenv("MINERU_API_URL", raising=False)
    assert missing_prereqs(skill) == ["env:MINERU_API_URL"]
    # env 设置 → 满足
    monkeypatch.setenv("MINERU_API_URL", "http://x:8001/")
    assert missing_prereqs(skill) == []


def test_missing_prereqs_bin(tmp_path, monkeypatch):
    skills_root = _make_skill(tmp_path, "tool", "requires:\n  bins:\n    - nonexistent-cli-xyz\n")
    skill = parse_skill(skills_root / "tool")
    assert skill is not None
    # 该 bin 不存在于 PATH → 缺失
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    assert missing_prereqs(skill) == ["bin:nonexistent-cli-xyz"]


def test_missing_prereqs_bin_present(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "realtool").write_text("#!/bin/sh\necho ok\n")
    (bin_dir / "realtool").chmod(0o755)
    skills_root = _make_skill(tmp_path, "tool2", "requires:\n  bins:\n    - realtool\n")
    skill = parse_skill(skills_root / "tool2")
    monkeypatch.setenv("PATH", str(bin_dir))
    assert missing_prereqs(skill) == []


def test_missing_prereqs_no_requires(tmp_path):
    skills_root = _make_skill(tmp_path, "plain")
    skill = parse_skill(skills_root / "plain")
    assert missing_prereqs(skill) == []


# ── build_skill_prompt：前置不满足标记 [unavailable] ───────────────────
def test_build_skill_prompt_marks_unavailable(tmp_path, monkeypatch):
    skills_root = _make_skill(
        tmp_path, "mineru",
        "requires:\n  env:\n    - MINERU_API_URL\n",
    )
    monkeypatch.delenv("MINERU_API_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    prompt = build_skill_prompt(["mineru"], loop_dir=_loop_dir(tmp_path))
    assert "mineru" in prompt
    assert "[unavailable: 缺少 env:MINERU_API_URL]" in prompt
    assert "Path:" not in prompt  # 前置不满足不注入路径（agent 不应去读）


def test_build_skill_prompt_ok_when_prereqs_satisfied(tmp_path, monkeypatch):
    skills_root = _make_skill(
        tmp_path, "mineru",
        "requires:\n  env:\n    - MINERU_API_URL\n",
    )
    monkeypatch.setenv("MINERU_API_URL", "http://x:8001/")
    monkeypatch.chdir(tmp_path)
    prompt = build_skill_prompt(["mineru"], loop_dir=_loop_dir(tmp_path))
    assert "[unavailable" not in prompt
    assert "Path:" in prompt


def test_build_skill_prompt_all_not_found_empty(tmp_path, monkeypatch):
    """全部技能不存在 → 不注入（build_skill_prompt 返回空串设计）。"""
    monkeypatch.chdir(tmp_path)
    prompt = build_skill_prompt(["ghost"], loop_dir=_loop_dir(tmp_path))
    assert prompt == ""


def test_build_skill_prompt_mixed(tmp_path, monkeypatch):
    skills_root = _make_skill(
        tmp_path, "mineru",
        "requires:\n  env:\n    - MINERU_API_URL\n",
    )
    _make_skill(tmp_path, "plain")
    monkeypatch.delenv("MINERU_API_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    prompt = build_skill_prompt(["mineru", "plain", "ghost"], loop_dir=_loop_dir(tmp_path))
    assert "[unavailable: 缺少 env:MINERU_API_URL]" in prompt
    assert "Path:" in prompt          # plain 满足，有路径
    assert "[not found]" in prompt    # ghost 不存在
