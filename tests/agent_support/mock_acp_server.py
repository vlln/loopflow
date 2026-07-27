"""Mock ACP server for CI testing of loopflow's ACP transport.

Implements the agent-client-protocol SDK's ``Agent`` Protocol as a stdio ACP
server.  Behaviour is controlled by the ``MOCK_ACP_MODE`` environment variable
so that AC-030 scenarios can be exercised in CI without a real pi-acp backend
(which consumes quota and is not reproducible).

Modes
-----
- ``normal`` (default): streaming thought/message/tool_call/usage then end_turn
- ``permission``: send a tool_call + request_permission, then end_turn
- ``load_session``: declare loadSession=true, retain context across session/load
- ``startup_fail``: exit immediately (non-zero) before serving any request
- ``context_prefix``: first agent_message_chunk contains context prefix text

Run as::

    MOCK_ACP_MODE=normal python tests/agent_support/mock_acp_server.py

The server is spawned as a subprocess by the SDK client side
(``spawn_agent_process``), exactly like a real ACP agent (pi-acp).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any

from acp import PROTOCOL_VERSION, run_agent
from acp.helpers import (
    start_tool_call,
    text_block,
    update_agent_message_text,
    update_agent_thought_text,
    update_tool_call,
)
from acp.schema import (
    AgentCapabilities,
    Implementation,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PermissionOption,
    PromptResponse,
    PromptCapabilities,
    SessionCapabilities,
    SessionListCapabilities,
    ToolCallUpdate,
    UsageUpdate,
)

__all__ = ["MockAcpAgent"]


def _mode() -> str:
    return os.environ.get("MOCK_ACP_MODE", "normal")


class MockAcpAgent:
    """Scriptable mock ACP agent implementing the SDK ``Agent`` Protocol."""

    def __init__(self) -> None:
        self._conn: Any = None  # AgentSideConnection, set in on_connect
        # session_id → list of user message texts (context store)
        self._sessions: dict[str, list[str]] = {}
        # track which sessions have already emitted context prefix
        self._context_prefix_done: set[str] = set()

    # ── Agent Protocol lifecycle ────────────────────────────────────────

    def on_connect(self, conn: Any) -> None:
        self._conn = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: Any = None,
        client_info: Any = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        mode = _mode()
        load_session = mode in ("load_session",)
        caps = AgentCapabilities(
            load_session=load_session,
            prompt_capabilities=PromptCapabilities(),
        )
        if load_session:
            caps.session_capabilities = SessionCapabilities(
                list=SessionListCapabilities(),
            )
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=caps,
            agent_info=Implementation(
                name="mock-acp",
                version="0.1.0",
            ),
        )

    async def new_session(
        self,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: Any = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        sid = str(uuid.uuid4())
        self._sessions[sid] = []
        return NewSessionResponse(session_id=sid)

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: Any = None,
        additional_directories: list[str] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        if session_id not in self._sessions:
            return None
        return LoadSessionResponse()

    async def list_sessions(
        self, cwd: str | None = None, cursor: str | None = None, **kwargs: Any
    ) -> Any:
        from acp.schema import ListSessionsResponse, SessionInfo

        sessions = [
            SessionInfo(session_id=sid, cwd=cwd or "")
            for sid in self._sessions
        ]
        return ListSessionsResponse(sessions=sessions)

    async def authenticate(self, method_id: str, **kwargs: Any) -> Any:
        from acp.schema import AuthenticateResponse
        return AuthenticateResponse()

    async def set_session_mode(self, session_id: str, mode_id: str, **kwargs: Any) -> Any:
        return None

    async def set_config_option(
        self, config_id: str, session_id: str, value: Any, **kwargs: Any
    ) -> Any:
        return None

    async def fork_session(
        self,
        session_id: str,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: Any = None,
        **kwargs: Any,
    ) -> Any:
        from acp.schema import ForkSessionResponse
        new_sid = str(uuid.uuid4())
        self._sessions[new_sid] = list(self._sessions.get(session_id, []))
        return ForkSessionResponse(session_id=new_sid)

    async def resume_session(
        self,
        session_id: str,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: Any = None,
        **kwargs: Any,
    ) -> Any:
        from acp.schema import ResumeSessionResponse
        return ResumeSessionResponse(session_id=session_id)

    async def close_session(self, session_id: str, **kwargs: Any) -> Any:
        self._sessions.pop(session_id, None)
        return None

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        pass

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        pass

    # ── prompt — main behaviour dispatch ───────────────────────────────

    async def prompt(
        self,
        session_id: str,
        prompt: list[Any],
        **kwargs: Any,
    ) -> PromptResponse:
        mode = _mode()
        user_text = self._extract_text(prompt)

        # store user message for context retention
        history = self._sessions.setdefault(session_id, [])
        history.append(user_text)

        if mode == "permission":
            await self._do_permission(session_id, user_text)
        elif mode == "context_prefix":
            await self._do_context_prefix(session_id, user_text)
        else:
            await self._do_normal(session_id, user_text)

        return PromptResponse(stop_reason="end_turn")

    # ── behaviour implementations ──────────────────────────────────────

    async def _do_normal(self, session_id: str, user_text: str) -> None:
        """Stream thought → tool_call → tool_call_update → message → usage."""
        conn = self._conn

        # thought
        await conn.session_update(
            session_id,
            update_agent_thought_text("Let me think about this..."),
        )

        # tool call start
        await conn.session_update(
            session_id,
            start_tool_call(
                tool_call_id="tc-1",
                title="search",
                kind="search",
                status="in_progress",
            ),
        )

        # tool call progress
        await conn.session_update(
            session_id,
            update_tool_call(
                tool_call_id="tc-1",
                status="completed",
            ),
        )

        # agent message (the actual answer)
        reply = self._make_reply(session_id, user_text)
        await conn.session_update(
            session_id,
            update_agent_message_text(reply),
        )

        # usage update
        await conn.session_update(
            session_id,
            UsageUpdate(session_update="usage_update", used=100, size=8192),
        )

    async def _do_permission(self, session_id: str, user_text: str) -> None:
        """Send tool_call + request_permission, then continue after approval."""
        conn = self._conn

        # tool call start (the tool that needs permission)
        await conn.session_update(
            session_id,
            start_tool_call(
                tool_call_id="tc-perm",
                title="write_file",
                kind="edit",
                status="pending",
            ),
        )

        # request permission from client
        tool_call_update = ToolCallUpdate(
            tool_call_id="tc-perm",
            status="pending",
            title="write_file",
        )
        options = [
            PermissionOption(
                option_id="allow_once",
                name="Allow once",
                kind="allow_once",
            ),
            PermissionOption(
                option_id="reject_once",
                name="Reject once",
                kind="reject_once",
            ),
        ]
        resp = await conn.request_permission(
            session_id=session_id,
            tool_call=tool_call_update,
            options=options,
        )

        # after approval (or rejection), send the result
        outcome = resp.outcome if resp else None
        if outcome is not None and hasattr(outcome, "option_id"):
            approved = outcome.option_id.startswith("allow")
        else:
            approved = True  # best-effort

        await conn.session_update(
            session_id,
            update_tool_call(
                tool_call_id="tc-perm",
                status="completed" if approved else "failed",
            ),
        )

        reply = "Permission granted, task done." if approved else "Permission denied."
        await conn.session_update(
            session_id,
            update_agent_message_text(reply),
        )

    async def _do_context_prefix(self, session_id: str, user_text: str) -> None:
        """First message chunk contains context prefix (pi-acp quirk)."""
        conn = self._conn
        if session_id not in self._context_prefix_done:
            # pi-acp sends context (AGENTS.md, skills) before the answer
            context_text = "[context] AGENTS.md: project rules\n[context] skills: available tools"
            await conn.session_update(
                session_id,
                update_agent_message_text(context_text),
            )
            self._context_prefix_done.add(session_id)

        reply = self._make_reply(session_id, user_text)
        await conn.session_update(
            session_id,
            update_agent_message_text(reply),
        )

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_text(prompt: list[Any]) -> str:
        """Extract plain text from prompt content blocks."""
        parts: list[str] = []
        for block in prompt:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return " ".join(parts)

    def _make_reply(self, session_id: str, user_text: str) -> str:
        """Generate a reply, using stored context for load_session mode."""
        mode = _mode()
        history = self._sessions.get(session_id, [])

        if mode == "load_session":
            # If asked "what number", look through history for "Remember the number X"
            lowered = user_text.lower()
            if "what number" in lowered or "remember" in lowered and "?" in user_text:
                for msg in history:
                    # "Remember the number 42"
                    if "remember the number" in msg.lower():
                        # extract the number
                        tokens = msg.split()
                        for i, tok in enumerate(tokens):
                            if tok.lower() == "number" and i + 1 < len(tokens):
                                return tokens[i + 1].rstrip(".?!")
                return "I don't remember a number."

        # default reply
        return f"Echo: {user_text}"


def _main() -> None:
    mode = _mode()
    if mode == "startup_fail":
        # Exit immediately with non-zero code — simulates backend startup failure
        sys.stderr.write("[mock-acp] startup_fail: exiting before initialize\n")
        sys.exit(1)

    agent = MockAcpAgent()
    asyncio.run(run_agent(agent))


if __name__ == "__main__":
    _main()
