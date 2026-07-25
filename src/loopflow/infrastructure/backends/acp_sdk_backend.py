"""ACP SDK backend — uses the official ``agent-client-protocol`` SDK transport.

Replaces the stub ``AcpBackend`` with a real implementation backed by
``AcpSdkTransport``.  Implements ``BaseBackend``: create_session,
resume_session, close.  Maps SDK ``SessionNotification`` updates to
loopflow events via text/thought handler callbacks.

Per ADR-0049:
  - §4: permission auto-approve-all (no read/write grading)
  - §5: notification full mapping (agent_message_chunk → agent_message,
    agent_thought_chunk → thought, tool_call_start/progress informational,
    usage_update)
  - §7: capabilities dynamically declared from initialize result
  - context prefix filtering (spike leftover: pi-acp emits context in
    first message chunk)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from loopflow.domain.capabilities import Capabilities
from loopflow.infrastructure.backends.base import BaseBackend

if TYPE_CHECKING:
    from loopflow.domain import AgentDef

# ── import guard ───────────────────────────────────────────────────────

ACP_NOT_INSTALLED_ERROR = (
    "ACP transport requires the 'agent-client-protocol' package.\n"
    "Install it with: pip install loopflow[acp]\n"
    "Or: uv add agent-client-protocol"
)

try:
    import acp  # noqa: F401
    _ACP_AVAILABLE = True
except ImportError:
    _ACP_AVAILABLE = False


# ── per-backend ACP commands ───────────────────────────────────────────

ACP_COMMANDS: dict[str, list[str]] = {
    "pi": ["pi-acp"],
    "grok": ["grok", "agent", "stdio"],
    "kimi": ["kimi", "acp"],
    "gemini": ["gemini", "--acp"],
    "opencode": ["opencode", "acp"],
    "qwen": ["qwen", "--acp"],
    "kiro": ["kiro-cli", "acp"],
}

# CLI-only backends that have no ACP transport
_CLI_ONLY_BACKENDS = frozenset({"claude", "codex"})


class AcpSdkBackend(BaseBackend):
    """ACP backend using the official agent-client-protocol SDK.

    Args:
        command: Command list to spawn the ACP agent.
        env: Optional environment dict for the spawned subprocess.
        text_handler: Callback for agent_message chunks.
        thought_handler: Callback for agent_thought chunks.
        session_handler: Callback for session_id after session/new.
    """

    supports_native_goal: bool = False

    def __init__(
        self,
        command: list[str] | None = None,
        env: dict[str, str] | None = None,
        text_handler: Callable[[str], None] | None = None,
        thought_handler: Callable[[str], None] | None = None,
        session_handler: Callable[[str], None] | None = None,
        **kwargs,
    ) -> None:
        if not _ACP_AVAILABLE:
            raise RuntimeError(ACP_NOT_INSTALLED_ERROR)

        self._command = command or ["pi-acp"]
        self._env = env
        self._text_handler = text_handler
        self._thought_handler = thought_handler
        self._session_handler = session_handler
        self._auth_methods: list[dict] = []
        self._initialized = False

        # Import here to defer until acp is confirmed available
        from loopflow.infrastructure.transports.acp_sdk import AcpSdkTransport

        self._transport = AcpSdkTransport(
            command=self._command, env=self._env
        )
        self._transport.on_notification("session/update", self._on_update)

    # ── capabilities (lazy, ADR-0049 §7) ────────────────────────────────

    @property
    def capabilities(self) -> Capabilities:
        """Dynamically declare capabilities based on initialize result.

        Before initialize: returns default Capabilities (resume_session=False,
        durable_session_id=False).  After initialize: if the agent declares
        loadSession=true, declares resume_session + durable_session_id.

        This fixes the spike leftover where capabilities were queried before
        start(), causing load_session_supported to always be False.
        """
        if not self._initialized:
            return Capabilities()
        load_session = getattr(self._transport, "load_session_supported", False)
        if load_session:
            return Capabilities(
                native_goal=False,
                resume_session=True,
                durable_session_id=True,
            )
        return Capabilities()

    # ── notification → loopflow event mapping (ADR-0049 §5) ─────────────

    def _on_update(self, params: dict) -> None:
        u = params.get("update", {})
        # Support both camelCase (aliased) and snake_case keys
        su = u.get("sessionUpdate") or u.get("session_update") or ""

        if su == "agent_message_chunk":
            c = u.get("content", {})
            if isinstance(c, dict):
                text = c.get("text", "")
            else:
                text = getattr(c, "text", "") if c else ""
            if text:
                # Context prefix filtering (spike leftover)
                if self._is_context_line(text):
                    return  # skip context-prefixed chunks
                self._emit_text(text)

        elif su == "agent_thought_chunk":
            c = u.get("content", {})
            if isinstance(c, dict):
                text = c.get("text", "")
            else:
                text = getattr(c, "text", "") if c else ""
            if text and self._thought_handler:
                self._thought_handler(text)

        elif su in ("tool_call", "tool_call_start"):
            # Informational — tool call started (no client response needed)
            title = u.get("title", "")
            if title:
                sys.stderr.write(f"[acp] tool: {title}\n")

        elif su == "tool_call_update":
            # Informational — tool call progress
            pass

        elif su == "usage_update":
            # Usage info — informational, not mapped to a loopflow event
            pass

    # ── context prefix filtering ───────────────────────────────────────

    @staticmethod
    def _is_context_line(text: str) -> bool:
        """Check if a text chunk is a context prefix line (pi-acp quirk).

        pi-acp emits context (AGENTS.md, skills list) as the first
        agent_message_chunk before the actual agent answer.  This filter
        strips those lines so they don't pollute the business output.
        """
        if not text:
            return False
        # A context-prefixed chunk starts with [context]
        return text.lstrip().startswith("[context]")

    def _emit_text(self, text: str) -> None:
        if self._text_handler:
            self._text_handler(text)
        else:
            sys.stdout.write(text)
            sys.stdout.flush()

    # ── lifecycle ───────────────────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            self._transport.start()
        except (ConnectionError, RuntimeError, OSError) as e:
            raise RuntimeError(
                f"ACP backend unavailable: {e}"
            ) from e
        self._auth_methods = self._transport.auth_methods
        self._initialized = True

    def _authenticate(self) -> None:
        """Try to authenticate. pi-acp typically doesn't require auth if already configured."""
        for method in self._auth_methods:
            method_id = method.get("id", "")
            if not method_id:
                continue
            try:
                if self._transport.authenticate(method_id):
                    return
            except Exception:
                continue

    def _build_prompt(self, user: str, system: str | None) -> str:
        if system:
            return f"{system}\n\n{user}"
        return user

    # ── BaseBackend interface ────────────────────────────────────────────

    def create_session(
        self,
        user: str,
        system: str | None = None,
        model: str | None = None,
        system_mode: str = "append",
        agent_def: AgentDef | None = None,
        skills_dir: str | None = None,
    ) -> tuple[str, int]:
        self._ensure_initialized()

        # Try session/new; authenticate if needed
        try:
            sid = self._transport.new_session(cwd=str(Path.cwd()))
        except Exception:
            self._authenticate()
            sid = self._transport.new_session(cwd=str(Path.cwd()))

        if self._session_handler:
            self._session_handler(sid)

        prompt = self._build_prompt(user, system)
        try:
            resp = self._transport.prompt(session_id=sid, text=prompt)
            return sid, 0 if resp.stop_reason == "end_turn" else 1
        except Exception:
            return sid, 1

    def resume_session(
        self,
        session_id: str,
        user: str,
        system: str | None = None,
        model: str | None = None,
        system_mode: str = "append",
        agent_def: AgentDef | None = None,
        skills_dir: str | None = None,
    ) -> int:
        self._ensure_initialized()

        # session/load (resume)
        try:
            self._transport.load_session(cwd=str(Path.cwd()), session_id=session_id)
        except Exception:
            self._authenticate()
            self._transport.load_session(cwd=str(Path.cwd()), session_id=session_id)

        prompt = self._build_prompt(user, system)
        try:
            resp = self._transport.prompt(session_id=session_id, text=prompt)
            return 0 if resp.stop_reason == "end_turn" else 1
        except Exception:
            return 1

    def list_sessions(self) -> list[dict]:
        self._ensure_initialized()
        return []

    def close(self) -> None:
        self._transport.close()
