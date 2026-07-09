"""Agent definition parser for .md files with YAML frontmatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParamSpec:
    """Specification for a template parameter."""

    name: str
    required: bool = True
    default: Any = None


@dataclass
class AgentRequires:
    """Optional requirements for an agent."""

    env: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    params: list[ParamSpec] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)


@dataclass
class AgentDef:
    """Parsed agent definition from a .md file."""

    name: str
    description: str
    body: str = ""       # entire .md file content (including frontmatter), used as system prompt
    file_path: str | None = None
    requires: AgentRequires | None = None


def parse_agent(file_path: str | Path) -> AgentDef:
    """Parse an agent definition .md file.

    Expected format:
    ```
    ---
    name: agent-name
    description: What this agent does
    requires:
      env:
        - ENV_VAR_NAME
      skills:
        - github:owner/repo@ref
      params:
        - param_name
      mcps:
        - mcp_name
    ---
    System prompt body...
    ```

    Raises:
        ValueError: if required fields are missing or frontmatter is malformed.
        FileNotFoundError: if the file does not exist.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Agent definition not found: {file_path}")

    content = path.read_text(encoding="utf-8")

    # Extract frontmatter between first and second ---
    lines = content.split("\n")
    frontmatter: dict[str, str] = {}
    requires_data: dict[str, list[str]] = {}
    in_fm = False
    fm_ended = False
    in_requires = False
    current_requires_key: str | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                fm_ended = True
                continue
        if in_fm and not fm_ended:
            if stripped == "":
                continue
            # Handle requires section (nested)
            if stripped == "requires:" or stripped.startswith("requires:"):
                in_requires = True
                continue
            if in_requires:
                # Check for sub-keys: env:, skills:, params:, mcps:
                if stripped in ("env:", "skills:", "params:", "mcps:"):
                    current_requires_key = stripped.rstrip(":")
                    requires_data[current_requires_key] = []
                    continue
                if stripped.startswith("- "):
                    if current_requires_key:
                        requires_data[current_requires_key].append(
                            stripped[2:].strip().strip('"').strip("'")
                        )
                    continue
                # If we hit a non-indented, non-list line, exit requires
                if not line.startswith(" ") and not line.startswith("\t"):
                    in_requires = False
                    current_requires_key = None
                    # Fall through to process as regular frontmatter
                else:
                    continue
            if ":" in line and not in_requires:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    if not frontmatter:
        raise ValueError(f"No YAML frontmatter found in {file_path}")

    name = frontmatter.get("name", "").strip()
    description = frontmatter.get("description", "").strip()

    if not name:
        raise ValueError(f"'name' is required in frontmatter of {file_path}")
    if not description:
        raise ValueError(f"'description' is required in frontmatter of {file_path}")

    body = content.strip()

    requires = None
    if requires_data:
        # Convert raw param strings to ParamSpec objects
        raw_params: list[str] = requires_data.get("params", [])
        param_specs: list[ParamSpec] = []
        for p in raw_params:
            if ":" in p:
                name, _, default = p.partition(":")
                param_specs.append(ParamSpec(
                    name.strip(),
                    required=False,
                    default=default.strip().strip('"').strip("'"),
                ))
            else:
                param_specs.append(ParamSpec(p.strip(), required=True))

        requires = AgentRequires(
            env=requires_data.get("env", []),
            skills=requires_data.get("skills", []),
            params=param_specs,
            mcps=requires_data.get("mcps", []),
        )

    return AgentDef(
        name=name,
        description=description,
        body=body,
        file_path=str(path),
        requires=requires,
    )


def list_agents(agents_dir: str | Path) -> list[AgentDef]:
    """List all agent definitions in a directory.

    Returns:
        List of parsed AgentDef objects, skipping files that fail to parse.
    """
    directory = Path(agents_dir)
    if not directory.is_dir():
        return []

    agents: list[AgentDef] = []
    for f in sorted(directory.glob("*.md")):
        try:
            agents.append(parse_agent(f))
        except (ValueError, FileNotFoundError):
            pass
    return agents


def resolve_params(
    params: list[ParamSpec] | None,
    **kwargs: str,
) -> dict[str, str]:
    """Resolve template parameters with defaults.

    Args:
        params: List of parameter specifications (or None for passthrough).
        **kwargs: Provided parameter values.

    Returns:
        Dict of resolved parameter values (provided kwargs + defaults).

    Raises:
        ValueError: if a required parameter is not provided.
    """
    if params is None:
        return dict(kwargs)

    resolved: dict[str, str] = dict(kwargs)
    for p in params:
        if p.name not in resolved:
            if p.required:
                raise ValueError(
                    f"Required parameter '{p.name}' is not provided"
                )
            resolved[p.name] = p.default
    return resolved


def render_template(body: str, **kwargs: str) -> str:
    """Render {{param}} placeholders in a template string.

    Args:
        body: Template string with optional {{param}} placeholders.
        **kwargs: Values for placeholders.

    Returns:
        Rendered string with all placeholders replaced.

    Raises:
        ValueError: if a placeholder has no matching kwarg.
    """
    import re

    def _replace(match: re.Match) -> str:
        name = match.group(1).strip()
        if name not in kwargs:
            raise ValueError(
                f"Template parameter '{{{name}}}' is required but not provided"
            )
        return kwargs[name]

    return re.sub(r"\{\{(\w+)\}\}", _replace, body)