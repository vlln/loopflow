"""Application layer — coordinates domain services + infrastructure.

AgentRunner is the main application service. The public API functions
(agent, parallel, pipeline, workflow) live in runtime.py for backward
compatibility and delegate to AgentRunner internally.
"""

from loopflow.application.runner import AgentRunner

__all__ = ["AgentRunner"]