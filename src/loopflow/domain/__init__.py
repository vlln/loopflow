"""Domain layer — pure entities, value objects, and domain services.

Zero dependencies on infrastructure, application, or presentation layers.
"""

from loopflow.domain.agent_def import (
    AgentDef,
    AgentError,
    GoalBlocked,
    ParamSpec,
    render_template,
    resolve_params,
)
from loopflow.domain.capabilities import Capabilities
from loopflow.domain.marshalling import (
    add_goal_to_schema,
    build_goal_steering,
    extract_json,
    marshal,
    validate_json,
)
from loopflow.domain.goal_loop import run_goal_loop

__all__ = [
    "AgentDef",
    "AgentError",
    "Capabilities",
    "GoalBlocked",
    "ParamSpec",
    "add_goal_to_schema",
    "build_goal_steering",
    "extract_json",
    "marshal",
    "render_template",
    "resolve_params",
    "run_goal_loop",
    "validate_json",
]