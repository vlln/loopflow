"""Agent definition — domain entity (aggregate root)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class AgentError(Exception):
    """Raised when an agent call fails at the infrastructure level."""


class GoalBlocked(Exception):
    """Raised when goal mode exits due to blocked or max_iterations."""


@dataclass
class ParamSpec:
    """Specification for a template parameter."""

    name: str
    required: bool = True
    default: Any = None


@dataclass
class AgentDef:
    """Parsed agent definition from a .md file."""

    name: str
    description: str
    body: str = ""       # entire .md file content (including frontmatter), used as system prompt
    file_path: str | None = None
    extends: str | None = None  # name of parent agent to inherit from

    # Claude Code aligned — implemented
    model: str | None = None
    skills: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    isolation: str | None = None

    # Claude Code aligned — parsed but not yet implemented
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    max_turns: int | None = None
    hooks: dict | None = None
    effort: str | None = None
    color: str | None = None
    background: bool = False
    memory: str | None = None
    permission_mode: str | None = None

    # loopflow-specific
    env: list[str] = field(default_factory=list)
    input: dict | None = None     # JSON Schema
    output: dict | None = None    # JSON Schema


def _input_to_params(input_schema: dict | None) -> list[ParamSpec]:
    """Convert a JSON Schema input definition to a list of ParamSpec."""
    if input_schema is None:
        return []

    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        return []

    required: set[str] = set(input_schema.get("required", []))
    if not isinstance(required, set):
        required = set(required)

    params: list[ParamSpec] = []
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            params.append(ParamSpec(str(name), required=(name in required)))
            continue
        has_default = "default" in prop
        params.append(ParamSpec(
            str(name),
            required=(name in required) and not has_default,
            default=prop.get("default") if has_default else None,
        ))
    return params


def _merge_schemas(parent: dict | None, child: dict | None) -> dict | None:
    """Merge two JSON Schemas (input or output). Child properties override parent."""
    if child is None:
        return parent
    if parent is None:
        return child
    result = dict(parent)
    result["type"] = child.get("type", parent.get("type", "object"))
    props = dict(parent.get("properties", {}))
    props.update(child.get("properties", {}))
    if props:
        result["properties"] = props
    req = list(parent.get("required", []))
    for r in child.get("required", []):
        if r not in req:
            req.append(r)
    if req:
        result["required"] = req
    return result


def _merge_agents(parent: AgentDef, child: AgentDef) -> AgentDef:
    """Merge parent agent into child, returning a new AgentDef."""
    def _merge_lists(a: list, b: list) -> list:
        return a + b

    return AgentDef(
        name=child.name,
        description=child.description,
        body=f"{parent.body}\n\n{child.body}",
        file_path=child.file_path,
        extends=child.extends,

        model=child.model if child.model is not None else parent.model,
        skills=_merge_lists(parent.skills, child.skills),
        mcp_servers=_merge_lists(parent.mcp_servers, child.mcp_servers),
        isolation=child.isolation if child.isolation is not None else parent.isolation,

        tools=child.tools if child.tools is not None else parent.tools,
        disallowed_tools=child.disallowed_tools if child.disallowed_tools is not None else parent.disallowed_tools,
        max_turns=child.max_turns if child.max_turns is not None else parent.max_turns,
        hooks=child.hooks if child.hooks is not None else parent.hooks,
        effort=child.effort if child.effort is not None else parent.effort,
        color=child.color if child.color is not None else parent.color,
        background=child.background if child.background else parent.background,
        memory=child.memory if child.memory is not None else parent.memory,
        permission_mode=child.permission_mode if child.permission_mode is not None else parent.permission_mode,

        env=_merge_lists(parent.env, child.env),
        input=_merge_schemas(parent.input, child.input),
        output=_merge_schemas(parent.output, child.output),
    )


def resolve_params(
    params: list[ParamSpec] | None,
    **kwargs: str,
) -> dict[str, str]:
    """Resolve template parameters with defaults."""
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
    """Render {{param}} placeholders in a template string."""
    def _replace(match: re.Match) -> str:
        name = match.group(1).strip()
        if name not in kwargs:
            raise ValueError(
                f"Template parameter '{{{name}}}' is required but not provided"
            )
        return kwargs[name]

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", _replace, body)