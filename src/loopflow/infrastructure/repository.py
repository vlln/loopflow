"""Agent definition repository — file I/O for agent .md files (infrastructure layer)."""

from __future__ import annotations

from pathlib import Path

from loopflow.domain.agent_def import AgentDef, _merge_agents


def parse_agent(file_path: str | Path) -> AgentDef:
    """Parse an agent definition .md file."""
    import yaml

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Agent definition not found: {file_path}")

    content = path.read_text(encoding="utf-8")

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"No YAML frontmatter found in {file_path}")

    frontmatter_text = parts[1].strip()
    body = content.strip()

    try:
        fm = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter in {file_path}: {e}")

    if not isinstance(fm, dict):
        raise ValueError(f"Invalid frontmatter in {file_path}")

    name = str(fm.get("name", "")).strip()
    description = str(fm.get("description", "")).strip()

    if not name:
        raise ValueError(f"'name' is required in frontmatter of {file_path}")
    if not description:
        raise ValueError(f"'description' is required in frontmatter of {file_path}")

    input_schema = fm.get("input")
    if input_schema is not None and not isinstance(input_schema, dict):
        input_schema = None

    output = fm.get("output")
    if output is not None and not isinstance(output, dict):
        output = None

    def _str_list(key: str) -> list[str]:
        val = fm.get(key, [])
        if isinstance(val, list):
            return [str(v) for v in val]
        return []

    ad = AgentDef(
        name=name,
        description=description,
        body=body,
        file_path=str(path),
        extends=fm.get("extends"),

        model=fm.get("model"),
        skills=_str_list("skills"),
        mcp_servers=_str_list("mcpServers"),
        isolation=fm.get("isolation"),

        tools=_str_list("tools") if fm.get("tools") is not None else None,
        disallowed_tools=_str_list("disallowedTools") if fm.get("disallowedTools") is not None else None,
        max_turns=fm.get("maxTurns"),
        hooks=fm.get("hooks"),
        effort=fm.get("effort"),
        color=fm.get("color"),
        background=bool(fm.get("background", False)),
        memory=fm.get("memory"),
        permission_mode=fm.get("permissionMode"),

        env=_str_list("env"),
        input=input_schema,
        output=output,
    )

    if ad.extends:
        parent_path = path.parent / f"{ad.extends}.md"
        if not parent_path.is_file():
            raise ValueError(
                f"Agent '{ad.name}' extends '{ad.extends}' but "
                f"parent agent not found at {parent_path}"
            )
        parent = parse_agent(parent_path)
        ad = _merge_agents(parent, ad)

    return ad


def list_agents(agents_dir: str | Path) -> list[AgentDef]:
    """List all agent definitions in a directory."""
    directory = Path(agents_dir)
    if not directory.is_dir():
        return []

    agents: list[AgentDef] = []
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_"):
            continue
        try:
            agents.append(parse_agent(f))
        except (ValueError, FileNotFoundError):
            pass
    return agents