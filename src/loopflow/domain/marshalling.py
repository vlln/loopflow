"""Marshalling domain service — "尽力而为" (best effort) capability mapping.

Pure functions: takes AgentDef + Capabilities + prompt → assembled prompt.
No dependency on infrastructure or application layers.
"""

from __future__ import annotations

import json as json_mod
import re
from typing import Any

from loopflow.domain.agent_def import (
    AgentDef,
    _input_to_params,
    render_template,
    resolve_params,
)
from loopflow.domain.capabilities import Capabilities


APPEND_PROMPT_MAX_BYTES = 65536


def normalize_append_prompt(value: str | None) -> str | None:
    """Validate and normalize a Run-level user prompt suffix."""
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("append_prompt must be a string")
    if len(value.encode("utf-8")) > APPEND_PROMPT_MAX_BYTES:
        raise ValueError("append_prompt exceeds 64 KiB")
    return value


def append_run_prompt(prompt: str, value: str | None) -> str:
    """Append the untrusted Run instruction as the final user-prompt section."""
    normalized = normalize_append_prompt(value)
    if normalized is None:
        return prompt
    return (
        f"{prompt}\n\n<run-append-prompt>\n"
        f"{normalized}\n"
        "</run-append-prompt>"
    )


AGENT_CONTROL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["__loopflow"],
    "properties": {
        "__loopflow": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "requests"],
            "properties": {
                "status": {"const": "waiting_input"},
                "requests": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["key", "prompt", "options", "allow_custom"],
                        "properties": {
                            "key": {"type": "string", "minLength": 1},
                            "prompt": {"type": "string", "minLength": 1},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "allow_custom": {"type": "boolean"},
                        },
                    },
                },
            },
        }
    },
}


def add_control_to_schema(schema: dict) -> dict:
    """Return the mutually exclusive business/control output schema."""
    business = {
        **schema,
        "properties": {
            **(schema.get("properties") or {}),
            "__loopflow": False,
        },
    }
    return {"oneOf": [business, AGENT_CONTROL_SCHEMA]}


def schema_mentions_reserved_control(value: Any) -> bool:
    """Return whether a JSON schema can claim the framework control field."""
    if not isinstance(value, dict):
        return False

    properties = value.get("properties")
    if isinstance(properties, dict):
        if "__loopflow" in properties:
            return True
        if any(
            schema_mentions_reserved_control(schema)
            for schema in properties.values()
        ):
            return True

    required = value.get("required")
    if isinstance(required, list) and "__loopflow" in required:
        return True

    schema_maps = ("$defs", "definitions", "dependentSchemas")
    for keyword in schema_maps:
        schemas = value.get(keyword)
        if isinstance(schemas, dict) and any(
            schema_mentions_reserved_control(schema)
            for schema in schemas.values()
        ):
            return True

    pattern_properties = value.get("patternProperties")
    if isinstance(pattern_properties, dict):
        for pattern, schema in pattern_properties.items():
            try:
                claims_reserved = re.search(pattern, "__loopflow") is not None
            except (re.error, TypeError):
                claims_reserved = False
            if claims_reserved or schema_mentions_reserved_control(schema):
                return True

    dependent_required = value.get("dependentRequired")
    if isinstance(dependent_required, dict) and any(
        isinstance(names, list) and "__loopflow" in names
        for names in dependent_required.values()
    ):
        return True

    property_names = value.get("propertyNames")
    if isinstance(property_names, dict) and (
        property_names.get("const") == "__loopflow"
        or (
            isinstance(property_names.get("enum"), list)
            and "__loopflow" in property_names["enum"]
        )
    ):
        return True

    schema_lists = ("allOf", "anyOf", "oneOf", "prefixItems")
    for keyword in schema_lists:
        schemas = value.get(keyword)
        if isinstance(schemas, list) and any(
            schema_mentions_reserved_control(schema) for schema in schemas
        ):
            return True

    schema_values = (
        "not", "if", "then", "else", "items", "contains",
        "additionalProperties", "unevaluatedProperties",
    )
    return any(
        schema_mentions_reserved_control(value.get(keyword))
        for keyword in schema_values
    )


def build_intervention_prompt() -> str:
    return (
        "<loopflow-intervention>\n"
        "Use this only when necessary human input is missing and the task "
        "cannot continue without it. Normal answers must keep the requested "
        "business output format. To wait for input, return only:\n"
        '{"__loopflow":{"status":"waiting_input","requests":['
        '{"key":"scope","prompt":"Which scope?","options":[],"allow_custom":true}'
        "]}}\n"
        "Each key and prompt must be non-empty; options must be strings and "
        "keys must be unique. Do not include default or timeout. The answers "
        "will return to this session in an input_received envelope.\n"
        "</loopflow-intervention>"
    )


def marshal(
    ad: AgentDef | None,
    prompt: str,
    *,
    goal: str | None = None,
    caps: Capabilities = Capabilities(),
    **params: str,
) -> tuple[str, dict | None, bool]:
    """Assemble the final prompt from agent capabilities.

    Follows "best effort" principle: use backend native support when
    available, otherwise fall back to text injection or framework loops.

    Args:
        ad: Agent definition (or None for raw prompt).
        prompt: The user task prompt.
        goal: Optional goal for feedback loop.
        caps: Backend capabilities (value object, not backend instance).
        **params: Template parameters for body rendering.

    Returns:
        (resolved_prompt, schema, use_native_goal)
    """
    resolved = prompt
    schema = None

    # Goal — check backend capability (independent of ad)
    native_goal = goal and caps.native_goal
    if native_goal:
        resolved = f"/goal {goal}\n\n{resolved}"

    if ad is None:
        return resolved, schema, native_goal

    # Body + template rendering
    body = render_template(
        ad.body,
        **resolve_params(_input_to_params(ad.input), **params),
    )
    if body:
        resolved = f"{body}\n\n---\n\nTask: {prompt}"

    # Schema
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


def extract_json(text: str, schema: dict) -> tuple[dict | None, str | None]:
    """Extract a JSON object matching schema from agent text response.

    Returns (parsed_obj, error_message). When extraction succeeds and the
    object passes schema validation, returns (obj, None). When extraction
    fails or schema validation fails, returns (None, error_detail).
    """
    required_keys = set(schema.get("properties", {}).keys())
    if not required_keys:
        return None, None

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
                            valid, err = validate_json(obj, schema)
                            if valid:
                                return obj, None
                            # Schema validation failed — try coercion
                            coerced, coercion_errors = coerce_json(obj, schema)
                            if coerced is not None:
                                re_valid, re_err = validate_json(coerced, schema)
                                if re_valid:
                                    return coerced, None
                            return None, err
                    start = i + 1
                    break
        else:
            break

    return None, None


def validate_json(obj: dict, schema: dict) -> tuple[bool, str | None]:
    """Validate obj against JSON Schema using jsonschema.

    Returns (is_valid, error_message). When valid, returns (True, None).
    When invalid, returns (False, formatted_error) where formatted_error
    includes the field path, expected type, and actual value.
    """
    try:
        import jsonschema
    except ImportError:
        return False, None
    try:
        jsonschema.validate(obj, schema)
        return True, None
    except jsonschema.ValidationError as e:
        path = ".".join(str(p) for p in e.absolute_path) or "(root)"
        expected = e.schema.get("type", e.schema.get("enum", "unknown"))
        actual = repr(e.instance)[:100]
        msg = f"Field '{path}': expected {expected}, got {actual}"
        return False, msg


def coerce_json(obj: dict, schema: dict) -> tuple[dict | None, list[str]]:
    """Attempt safe type coercion to satisfy schema constraints.

    Only top-level fields are coerced (no recursive nesting). Only safe
    conversions are attempted (string→number, string→bool, number→string,
    enum case-match, array-wrap).

    Returns (coerced_obj | None, errors). coerced_obj is non-None when all
    type conversions were applied successfully (but the caller MUST
    re-validate, as value constraints like maximum/minimum are not checked
    here). errors records all conversion attempts (success and failure).
    """
    import copy

    properties = schema.get("properties", {})
    if not properties:
        return None, []

    coerced = copy.deepcopy(obj)
    errors: list[str] = []

    for key, prop_schema in properties.items():
        if key not in coerced:
            continue

        value = coerced[key]
        expected_type = prop_schema.get("type")

        # string → number
        if expected_type == "number" and isinstance(value, str):
            try:
                coerced[key] = float(value)
                errors.append(f"Field '{key}': string '{value}' → number {coerced[key]}")
            except ValueError:
                errors.append(f"Field '{key}': string '{value}' cannot convert to number")

        # string → integer
        elif expected_type == "integer" and isinstance(value, str):
            if "." in value:
                errors.append(f"Field '{key}': string '{value}' has decimal, cannot convert to integer")
            else:
                try:
                    coerced[key] = int(value)
                    errors.append(f"Field '{key}': string '{value}' → integer {coerced[key]}")
                except ValueError:
                    errors.append(f"Field '{key}': string '{value}' cannot convert to integer")

        # string → boolean
        elif expected_type == "boolean" and isinstance(value, str):
            low = value.lower()
            if low == "true":
                coerced[key] = True
                errors.append(f"Field '{key}': string '{value}' → boolean True")
            elif low == "false":
                coerced[key] = False
                errors.append(f"Field '{key}': string '{value}' → boolean False")
            else:
                errors.append(f"Field '{key}': string '{value}' not 'true'/'false', cannot convert to boolean")

        # number/bool → string
        elif expected_type == "string" and isinstance(value, (int, float, bool)):
            coerced[key] = str(value)
            errors.append(f"Field '{key}': {type(value).__name__} {value} → string '{coerced[key]}'")

        # single value → array wrap
        elif expected_type == "array" and not isinstance(value, list):
            min_items = prop_schema.get("minItems", 0)
            if min_items <= 1:
                coerced[key] = [value]
                errors.append(f"Field '{key}': {type(value).__name__} {value} → array [{value!r}]")
            else:
                errors.append(f"Field '{key}': single value but minItems={min_items}, cannot wrap")

        # enum case-insensitive match
        elif "enum" in prop_schema and isinstance(value, str):
            enum_values = prop_schema["enum"]
            matches = [e for e in enum_values if isinstance(e, str) and e.lower() == value.lower()]
            if len(matches) == 1:
                coerced[key] = matches[0]
                errors.append(f"Field '{key}': string '{value}' → enum '{matches[0]}'")
            elif len(matches) > 1:
                errors.append(f"Field '{key}': string '{value}' matches multiple enum values: {matches}")
            else:
                errors.append(f"Field '{key}': string '{value}' not in enum {enum_values}")

    return coerced, errors
