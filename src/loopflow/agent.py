"""Agent definition parser for .md files with YAML frontmatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AgentError(Exception):
    """Raised when an agent call fails at the infrastructure level."""


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
    output: dict | None = None  # JSON Schema for structured output


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
        - param_name: default_value
      mcps:
        - mcp_name
    output:
      type: object
      properties:
        field_name:
          type: string
    ---
    System prompt body...
    ```

    Raises:
        ValueError: if required fields are missing or frontmatter is malformed.
        FileNotFoundError: if the file does not exist.
    """
    import yaml

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Agent definition not found: {file_path}")

    content = path.read_text(encoding="utf-8")

    # Extract frontmatter between --- markers
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

    # Parse requires
    requires = None
    requires_data = fm.get("requires", {})
    if requires_data and isinstance(requires_data, dict):
        raw_params: list = requires_data.get("params", [])
        param_specs: list[ParamSpec] = []
        for p in raw_params:
            if isinstance(p, str):
                param_specs.append(ParamSpec(p.strip(), required=True))
            elif isinstance(p, dict):
                for pname, pdefault in p.items():
                    param_specs.append(ParamSpec(
                        str(pname).strip(),
                        required=False,
                        default=pdefault,
                    ))
            # Skip unknown types silently

        requires = AgentRequires(
            env=requires_data.get("env", []),
            skills=requires_data.get("skills", []),
            params=param_specs,
            mcps=requires_data.get("mcps", []),
        )

    # Parse output
    output = fm.get("output")
    if output is not None and not isinstance(output, dict):
        output = None  # output must be a JSON Schema dict

    return AgentDef(
        name=name,
        description=description,
        body=body,
        file_path=str(path),
        requires=requires,
        output=output,
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
            resolved[p.name] = str(p.default) if p.default is not None else ""
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


def extract_json(text: str, schema: dict) -> dict | None:
    """Extract a JSON object matching schema from agent text response.

    When an agent's text output wraps JSON in markdown or other text,
    this function finds the first { ... } block whose keys cover the
    schema's property keys, then validates it with jsonschema.

    Returns None if no matching JSON block is found.
    """
    required_keys = set(schema.get("properties", {}).keys())
    if not required_keys:
        return None

    import json as json_mod

    start = 0
    while True:
        idx = text.find("{", start)
        if idx == -1:
            break
        depth = 0
        for i, ch in enumerate(text[idx:], idx):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json_mod.loads(text[idx : i + 1])
                    except json_mod.JSONDecodeError:
                        pass
                    else:
                        if isinstance(obj, dict) and required_keys.issubset(obj.keys()):
                            if validate_json(obj, schema):
                                return obj
                    start = i + 1
                    break
        else:
            break

    return None


def validate_json(obj: dict, schema: dict) -> bool:
    """Validate obj against JSON Schema using jsonschema."""
    try:
        import jsonschema
    except ImportError:
        return False
    try:
        jsonschema.validate(obj, schema)
        return True
    except jsonschema.ValidationError:
        return False