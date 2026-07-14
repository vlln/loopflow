"""Agent definition, marshalling, and goal loop — domain layer."""

from __future__ import annotations

import json as json_mod
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


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
    """Convert a JSON Schema input definition to a list of ParamSpec.

    Args:
        input_schema: JSON Schema dict with optional 'properties' and 'required'.

    Returns:
        List of ParamSpec, empty if input_schema is None or has no properties.
    """
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
    # Merge properties
    props = dict(parent.get("properties", {}))
    props.update(child.get("properties", {}))
    if props:
        result["properties"] = props
    # Merge required
    req = list(parent.get("required", []))
    for r in child.get("required", []):
        if r not in req:
            req.append(r)
    if req:
        result["required"] = req
    return result


def _merge_agents(parent: AgentDef, child: AgentDef) -> AgentDef:
    """Merge parent agent into child, returning a new AgentDef.

    Rules:
    - body: parent body + child body (parent first)
    - list fields (skills, env, mcp_servers): merged
    - scalar fields: child overrides parent
    - input/output: child overrides parent
    - name, description, file_path: child wins
    """
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


def parse_agent(file_path: str | Path) -> AgentDef:
    """Parse an agent definition .md file.

    Expected format (aligned with Claude Code subagent schema):
    ```
    ---
    name: agent-name
    description: What this agent does
    model: sonnet
    skills:
      - skill-name
    mcpServers:
      - server-name
    tools:
      - Read
      - Bash
    disallowedTools: []
    maxTurns: 10
    hooks: {}
    effort: high
    color: blue
    background: false
    memory: project
    isolation: worktree
    permissionMode: bypassPermissions
    env:
      - API_KEY
    input:
      type: object
      properties:
        param_name:
          type: string
          default: default_value
      required:
        - param_name
    output:
      type: object
      properties:
        field_name:
          type: string
      required:
        - field_name
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

    # Parse input schema
    input_schema = fm.get("input")
    if input_schema is not None and not isinstance(input_schema, dict):
        input_schema = None

    # Parse output schema
    output = fm.get("output")
    if output is not None and not isinstance(output, dict):
        output = None  # output must be a JSON Schema dict

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

        # Claude Code aligned — implemented
        model=fm.get("model"),
        skills=_str_list("skills"),
        mcp_servers=_str_list("mcpServers"),
        isolation=fm.get("isolation"),

        # Claude Code aligned — parsed but not yet implemented
        tools=_str_list("tools") if fm.get("tools") is not None else None,
        disallowed_tools=_str_list("disallowedTools") if fm.get("disallowedTools") is not None else None,
        max_turns=fm.get("maxTurns"),
        hooks=fm.get("hooks"),
        effort=fm.get("effort"),
        color=fm.get("color"),
        background=bool(fm.get("background", False)),
        memory=fm.get("memory"),
        permission_mode=fm.get("permissionMode"),

        # loopflow-specific
        env=_str_list("env"),
        input=input_schema,
        output=output,
    )

    # Resolve extends: load parent agent and merge
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
    """List all agent definitions in a directory.

    Returns:
        List of parsed AgentDef objects, skipping files that fail to parse.
    """
    directory = Path(agents_dir)
    if not directory.is_dir():
        return []

    agents: list[AgentDef] = []
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_"):
            continue  # skip abstract agents
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

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", _replace, body)


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


# ── Marshalling: domain service ──────────────────────────────────────────────

def marshal(
    ad: AgentDef | None,
    prompt: str,
    goal: str | None = None,
    backend: Any = None,
    **params: str,
) -> tuple[str, dict | None, bool]:
    """Assemble the final prompt from agent capabilities.

    Follows "best effort" principle: use backend native support when
    available, otherwise fall back to text injection or framework loops.

    Args:
        ad: Agent definition (or None for raw prompt).
        prompt: The user task prompt.
        goal: Optional goal for feedback loop.
        backend: Backend instance for capability queries.
        **params: Template parameters for body rendering.

    Returns:
        (resolved_prompt, schema, use_native_goal)
    """
    resolved = prompt
    schema = None

    # 3. Goal — query backend capability (independent of ad)
    native_goal = (
        goal
        and backend is not None
        and getattr(backend, 'supports_native_goal', False)
    )
    if native_goal:
        resolved = f"/goal {goal}\n\n{resolved}"

    if ad is None:
        return resolved, schema, native_goal

    # 1. Body + template rendering
    body = render_template(ad.body, **resolve_params(_input_to_params(ad.input), **params))
    if body:
        resolved = f"{body}\n\n---\n\nTask: {prompt}"

    # 2. Schema
    schema = ad.output

    return resolved, schema, native_goal


def build_goal_steering(goal: str, iteration: int,
                        max_iterations: int) -> str:
    """Generate steering prompt for goal mode."""
    if iteration == 1:
        return (
            f"<goal-steering>\n"
            f"You are working toward a goal. Continue working until the "
            f"goal is fully accomplished.\n\n"
            f"## Goal\n{goal}\n\n"
            f"## Completion Audit\n"
            f"Before declaring complete, verify:\n"
            f"1. Each requirement in the goal is met\n"
            f"2. Verification is based on evidence (files, command "
            f"output, test results)\n"
            f"3. \"I made a plan\" or \"I wrote a summary\" is NOT "
            f"completion\n\n"
            f"## Blocked Audit\n"
            f"Before declaring blocked:\n"
            f"1. The same blocking condition must persist for 3 "
            f"consecutive attempts\n"
            f"2. \"Difficult\", \"slow\", or \"not fully done\" is NOT "
            f"a blocker\n"
            f"3. Only truly insurmountable obstacles qualify (missing "
            f"credentials, external service down, etc.)\n\n"
            f"Signal your status in the __goal field of your response.\n"
            f"</goal-steering>"
        )
    else:
        return (
            f"<goal-steering>\n"
            f"Continue working toward the goal. "
            f"Iteration {iteration}/{max_iterations}.\n\n"
            f"## Goal\n{goal}\n\n"
            f"Same completion and blocked audit rules apply. "
            f"Continue from where you left off.\n"
            f"</goal-steering>"
        )


def add_goal_to_schema(schema: dict | None) -> dict:
    """Wrap business schema with __goal framework schema."""
    goal_prop = {
        "__goal": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "complete", "blocked"],
                },
                "reason": {"type": "string"},
            },
            "required": ["status"],
        }
    }
    if schema is None:
        return {
            "type": "object",
            "properties": {**goal_prop},
            "required": ["__goal"],
        }
    if "__goal" in (schema.get("properties") or {}):
        import warnings
        warnings.warn(
            "Business schema contains '__goal' field which is reserved "
            "for goal mode. Framework will override it."
        )
    return {
        **schema,
        "properties": {
            **(schema.get("properties") or {}),
            **goal_prop,
        },
        "required": (schema.get("required") or []) + ["__goal"],
    }


def run_goal_loop(
    resolved_prompt: str,
    schema: dict | None,
    goal: str,
    goal_max_iterations: int,
    call_fn: Callable,
    emit_log: Callable[[str], None] | None = None,
) -> Any:
    """Run goal loop: iterate until complete or blocked.

    call_fn(prompt, session, resume_session_id) -> (result, backend_sid)
    """
    goal_schema = add_goal_to_schema(schema)

    session = "goal_1"
    resume_session_id: str | None = None
    blocked_reason: str | None = None
    blocked_count = 0

    def _log(msg: str) -> None:
        if emit_log:
            emit_log(msg)

    for iteration in range(1, goal_max_iterations + 1):
        steering = build_goal_steering(goal, iteration,
                                        goal_max_iterations)
        full_prompt = f"{steering}\n\n{resolved_prompt}"

        # Inject goal schema
        schema_hint = (
            f"\n\n---\nOutput format — you MUST respond with a single "
            f"JSON object matching this schema:\n"
            f"{json_mod.dumps(goal_schema, indent=2)}\n\n"
            f"Do NOT wrap the JSON in markdown code blocks. "
            f"Return ONLY the JSON object."
        )

        try:
            result, backend_sid = call_fn(
                full_prompt + schema_hint, session, resume_session_id,
            )
        except Exception as e:
            msg = str(e)
            if "valid JSON" not in msg:
                raise
            _log(f"Goal iter {iteration}: JSON parse error, retrying...")
            continue

        # Extract goal state
        goal_state: dict = result.pop("__goal", {}) if isinstance(result, dict) else {}
        status = goal_state.get("status", "active")

        if status == "complete":
            return result

        if status == "blocked":
            reason = goal_state.get("reason") or "unknown"
            if reason == blocked_reason:
                blocked_count += 1
            else:
                blocked_reason = reason
                blocked_count = 1
            _log(f"Goal blocked ({blocked_count}/3): {reason}")
            if blocked_count >= 3:
                raise GoalBlocked(
                    f"Goal blocked after {iteration} iterations: "
                    f"{reason} (3 consecutive identical reasons)"
                )

        # Setup for next iteration
        resume_session_id = backend_sid
        session = f"goal_{iteration + 1}"

    raise GoalBlocked(
        f"Goal not completed after {goal_max_iterations} iterations"
    )