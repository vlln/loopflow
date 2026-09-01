"""Domain layer — pure entities, value objects, and domain services.

Zero dependencies on infrastructure, application, or presentation layers.
"""

from loopflow.domain.agent_def import (
    ERROR_CATEGORIES,
    AgentDef,
    AgentError,
    ParamSpec,
    render_template,
    resolve_params,
)
from loopflow.domain.capabilities import Capabilities
from loopflow.domain.goal_loop import AgentResult, run_goal_loop
from loopflow.domain.marshalling import (
    add_goal_to_schema,
    build_goal_steering,
    coerce_json,
    extract_json,
    marshal,
    validate_json,
)
from loopflow.domain.rerun_loop import (
    RerunOutcome,
    RerunResult,
    RouteDecision,
    Stage,
    run_rerun_loop,
)

__all__ = [
    "ERROR_CATEGORIES",
    "AgentDef",
    "AgentError",
    "Capabilities",
    "AgentResult",
    "ParamSpec",
    "RerunOutcome",
    "RerunResult",
    "RouteDecision",
    "Stage",
    "add_goal_to_schema",
    "build_goal_steering",
    "coerce_json",
    "extract_json",
    "marshal",
    "render_template",
    "resolve_params",
    "run_goal_loop",
    "run_rerun_loop",
    "validate_json",
]