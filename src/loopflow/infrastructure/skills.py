"""Skill discovery and prompt injection.

Skills are directories containing SKILL.md with YAML frontmatter.
Lookup order: {loop_dir}/.skills/ → ~/.loopflow/skills/ → ~/.agents/skills/
"""

from __future__ import annotations

import os
from pathlib import Path


def _skill_dirs(loop_dir: Path | None = None) -> list[Path]:
    """Return skill search directories in priority order.

    Loop-level skills take highest priority, then user-level.
    """
    dirs: list[Path] = []
    home = Path.home()

    if loop_dir is not None:
        loop_skills = loop_dir / ".skills"
        if loop_skills.is_dir():
            dirs.append(loop_skills)

    loopflow_skills = home / ".loopflow" / "skills"
    agents_skills = home / ".agents" / "skills"
    if loopflow_skills.is_dir():
        dirs.append(loopflow_skills)
    if agents_skills.is_dir():
        dirs.append(agents_skills)
    return dirs


def find_skill(name: str, loop_dir: Path | None = None) -> dict | None:
    """Find a skill by name, returning {name, description, path}.

    Searches {loop_dir}/.skills/ first, then ~/.loopflow/skills/,
    then ~/.agents/skills/.
    Returns None if the skill is not found.
    """
    for base in _skill_dirs(loop_dir):
        skill_dir = base / name
        skill_file = skill_dir / "SKILL.md"
        if skill_file.is_file():
            skill = parse_skill(skill_dir)
            if skill:
                return skill
    return None


def check_skills(names: list[str], loop_dir: Path | None = None) -> list[str]:
    """Check which skills are missing. Returns list of missing skill names."""
    return [name for name in names if find_skill(name, loop_dir) is None]


def skills_dir(loop_dir: Path | None = None) -> str | None:
    """Return the loop-level skills directory path, if it exists."""
    if loop_dir is not None:
        d = loop_dir / ".skills"
        if d.is_dir():
            return str(d)
    return None


def parse_skill(skill_dir: Path) -> dict | None:
    """Parse a skill directory's SKILL.md.

    Returns {name, description, path} or None on failure.
    """
    import yaml

    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return None

    content = skill_file.read_text(encoding="utf-8")

    # Extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        fm = yaml.safe_load(parts[1].strip())
    except yaml.YAMLError:
        return None

    if not isinstance(fm, dict):
        return None

    name = str(fm.get("name", "")).strip()
    description = str(fm.get("description", "")).strip()

    if not name:
        return None

    return {
        "name": name,
        "description": description,
        "path": str(skill_file),
    }


def build_skill_prompt(skill_names: list[str], loop_dir: Path | None = None) -> str:
    """Build a skill injection block for the system prompt.

    Format follows kimi-code convention: name + description + path.
    Only injects the directory — agent reads full skill body on demand.

    Skills that are not found are listed as [not found].
    """
    if not skill_names:
        return ""

    lines = [
        "## Available skills",
        "",
        "Skills are grouped by scope so you can tell where each came from.",
        "DISREGARD any earlier skill listings. Current available skills:",
        "",
    ]

    found_any = False
    for name in skill_names:
        skill = find_skill(name, loop_dir)
        if skill:
            lines.append(f"- {skill['name']}: {skill['description']}")
            lines.append(f"  Path: {skill['path']}")
            found_any = True
        else:
            lines.append(f"- {name}: [not found]")

    if not found_any:
        return ""  # No skills found at all, don't inject

    return "\n".join(lines)