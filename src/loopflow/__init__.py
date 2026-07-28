"""loopflow — AI Agent loop orchestration tool."""

from importlib.metadata import version as _get_version, PackageNotFoundError

from loopflow.domain.agent_def import AgentError
from loopflow.domain.goal_loop import AgentResult

try:
    __version__ = _get_version("loopflow")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"
