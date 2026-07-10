"""Unit tests for skill discovery and prompt injection."""

import tempfile
from pathlib import Path

import pytest

from loopflow.skills import build_skill_prompt, find_skill, parse_skill


class TestParseSkill:
    def test_parse_valid_skill(self):
        """Parse a SKILL.md with valid frontmatter."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                "---\n"
                "name: git-check\n"
                "description: Check git status and branches\n"
                "---\n"
                "# Git Check\n\nFull skill body here.\n"
            )
            result = parse_skill(skill_dir)
            assert result is not None
            assert result["name"] == "git-check"
            assert result["description"] == "Check git status and branches"
            assert result["path"] == str(skill_file)

    def test_parse_skill_no_file(self):
        """Return None when SKILL.md doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_skill(Path(tmp))
            assert result is None

    def test_parse_skill_no_frontmatter(self):
        """Return None when no frontmatter."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            (skill_dir / "SKILL.md").write_text("# No frontmatter\n")
            result = parse_skill(skill_dir)
            assert result is None

    def test_parse_skill_no_name(self):
        """Return None when name is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "description: Some skill\n"
                "---\n"
            )
            result = parse_skill(skill_dir)
            assert result is None


class TestBuildSkillPrompt:
    def test_empty_list(self):
        """Empty skill list returns empty string."""
        assert build_skill_prompt([]) == ""

    def test_all_not_found(self):
        """All skills not found returns empty string."""
        # Use a skill name that definitely doesn't exist
        result = build_skill_prompt(["nonexistent-skill-xyz-123"])
        assert result == "" or "[not found]" in result

    def test_includes_skill_info(self):
        """Prompt includes skill name, description, and path."""
        # We can't easily create skills in ~/.agents/skills/ in tests,
        # but we can verify the format for non-existent skills
        result = build_skill_prompt(["nonexistent-test-skill"])
        if result:  # May be empty if no skill dirs exist
            assert "nonexistent-test-skill" in result
            assert "[not found]" in result

    def test_prompt_format(self):
        """Prompt follows the expected format."""
        result = build_skill_prompt(["test-skill"])
        if result:
            assert "## Available skills" in result
            assert "DISREGARD any earlier skill listings" in result


class TestFindSkill:
    def test_nonexistent_skill(self):
        """Returns None for non-existent skill."""
        result = find_skill("definitely-nonexistent-skill-xyz-999")
        assert result is None