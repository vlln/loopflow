"""Domain layer — pure entities, value objects, and domain services.

Zero dependencies on infrastructure, application, or presentation layers.
"""

from loopflow.domain.agent_def import (
    AgentDef,
    AgentError,
    ParamSpec,
    render_template,
    resolve_params,
)
from loopflow.domain.capabilities import Capabilities
from loopflow.domain.goal_loop import GoalResult, run_goal_loop
from loopflow.domain.marshalling import (
    add_goal_to_schema,
    build_goal_steering,
    extract_json,
    marshal,
    validate_json,
)

__all__ = [
    "AgentDef",
    "AgentError",
    "Capabilities",
    "GoalResult",
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