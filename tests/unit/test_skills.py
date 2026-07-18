"""Unit tests for skill discovery and prompt injection."""

import tempfile
from pathlib import Path

import pytest

from loopflow.infrastructure.skills import build_skill_prompt, check_skills, find_skill, parse_skill, skills_dir


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

    def test_find_skill_with_loop_dir(self):
        """Finds skill in loop_dir/.skills/."""
        with tempfile.TemporaryDirectory() as tmp:
            loop_dir = Path(tmp)
            skill_dir = loop_dir / ".skills" / "my-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: my-skill\n"
                "description: A loop-level skill\n"
                "---\n"
            )
            result = find_skill("my-skill", loop_dir=loop_dir)
            assert result is not None
            assert result["name"] == "my-skill"
            assert result["description"] == "A loop-level skill"

    def test_find_skill_loop_dir_nonexistent(self):
        """Returns None when loop_dir/.skills/ doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            result = find_skill("my-skill", loop_dir=Path(tmp))
            assert result is None


class TestCheckSkills:
    def test_all_found(self):
        """Returns empty list when all skills exist."""
        with tempfile.TemporaryDirectory() as tmp:
            loop_dir = Path(tmp)
            for name in ["skill-a", "skill-b"]:
                skill_dir = loop_dir / ".skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: test\n---\n"
                )
            missing = check_skills(["skill-a", "skill-b"], loop_dir=loop_dir)
            assert missing == []

    def test_some_missing(self):
        """Returns list of missing skill names."""
        with tempfile.TemporaryDirectory() as tmp:
            loop_dir = Path(tmp)
            (loop_dir / ".skills" / "skill-a").mkdir(parents=True)
            (loop_dir / ".skills" / "skill-a" / "SKILL.md").write_text(
                "---\nname: skill-a\ndescription: test\n---\n"
            )
            missing = check_skills(["skill-a", "skill-b"], loop_dir=loop_dir)
            assert missing == ["skill-b"]

    def test_all_missing(self):
        """Returns all names when no skills exist."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = check_skills(["skill-a", "skill-b"], loop_dir=Path(tmp))
            assert missing == ["skill-a", "skill-b"]

    def test_no_loop_dir(self):
        """Returns all names when loop_dir is None."""
        missing = check_skills(["skill-a"], loop_dir=None)
        assert missing == ["skill-a"]


class TestSkillsDir:
    def test_skills_dir_exists(self):
        """Returns path string when .skills/ exists."""
        with tempfile.TemporaryDirectory() as tmp:
            loop_dir = Path(tmp)
            (loop_dir / ".skills").mkdir()
            result = skills_dir(loop_dir=loop_dir)
            assert result == str(loop_dir / ".skills")

    def test_skills_dir_nonexistent(self):
        """Returns None when .skills/ doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            result = skills_dir(loop_dir=Path(tmp))
            assert result is None

    def test_skills_dir_none(self):
        """Returns None when loop_dir is None."""
        assert skills_dir(loop_dir=None) is None


class TestBuildSkillPromptLoopDir:
    def test_finds_loop_level_skills(self):
        """Prompt includes loop-level skills when loop_dir is provided."""
        with tempfile.TemporaryDirectory() as tmp:
            loop_dir = Path(tmp)
            skill_dir = loop_dir / ".skills" / "my-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: my-skill\n"
                "description: A loop-level skill\n"
                "---\n"
            )
            result = build_skill_prompt(["my-skill"], loop_dir=loop_dir)
            assert "my-skill" in result
            assert "A loop-level skill" in result
            assert "[not found]" not in result