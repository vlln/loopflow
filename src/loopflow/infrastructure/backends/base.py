"""Abstract backend interface for loopflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from loopflow.domain.capabilities import Capabilities

if TYPE_CHECKING:
    from loopflow.agent import AgentDef


class BaseBackend(ABC):
    """Abstract backend for running agent sessions.

    Each backend implements how to create, resume, and close sessions
    for a specific agent provider (e.g. kimi, claude, codex, pi, kiro).
    loopflow only needs create_session, resume_session, and close.
    """

    @property
    def capabilities(self) -> Capabilities:
        """Backend capability declaration. Override in subclasses."""
        return Capabilities()

    # Backward-compatible class-level flag
    supports_native_goal: bool = False

    @abstractmethod
    def create_session(
        self,
        user: str,
        system: str | None = None,
        model: str | None = None,
        system_mode: str = "append",
        agent_def: AgentDef | None = None,
    ) -> tuple[str, int]:
        """Create a new session and run the prompt.

        Args:
            user: The user prompt.
            system: Optional system prompt (agent definition body).
            model: Optional model name.
            system_mode: 'append' (default) or 'overwrite'.
            agent_def: Optional agent definition (skills, mcp_servers, etc.).
        """

    @abstractmethod
    def resume_session(
        self,
        session_id: str,
        user: str,
        system: str | None = None,
        model: str | None = None,
        system_mode: str = "append",
        agent_def: AgentDef | None = None,
    ) -> int:
        """Resume an existing session and run the prompt.

        Args:
            session_id: The backend session ID to resume.
            user: The user prompt.
            system: Optional system prompt (agent definition body).
            model: Optional model name.
            system_mode: 'append' (default) or 'overwrite'.
            agent_def: Optional agent definition (skills, mcp_servers, etc.).
        """

    def close(self) -> None:
        """Clean up backend resources. Optional override."""