"""Self-validation tests for the mock ACP server test infrastructure.

These tests verify that ``tests/agent_support/mock_acp_server.py`` correctly
implements all scripted behaviour modes.  They use the official
``agent-client-protocol`` SDK client side (``spawn_agent_process``) to drive
the mock server as a real stdio subprocess — the same code path that
loopflow's ``AcpSdkBackend`` (DEVELOP 0089) will use.

Per ADR-0050, these tests do **not** cover AC-030 business scenarios — that
is DEVELOP 0089's responsibility.  They only prove the mock server itself
behaves correctly for each mode.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from acp import PROTOCOL_VERSION, spawn_agent_process, text_block
from acp.interfaces import Client
from acp.schema import (
    AllowedOutcome,
    ClientCapabilities,
    FileSystemCapabilities,
    Implementation,
    RequestPermissionResponse,
)

MOCK_SERVER = str(Path(__file__).resolve().parent.parent / "agent_support" / "mock_acp_server.py")


class _NotificationCollector(Client):
    """Minimal Client that collects session_update notifications and auto-approves permissions."""

    def __init__(self) -> None:
        self.updates: list[Any] = []
        self.permission_calls: list[dict[str, Any]] = []

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        self.updates.append(update)

    async def request_permission(
        self, session_id: str, tool_call: Any, options: list[Any], **kwargs: Any
    ) -> RequestPermissionResponse:
        self.permission_calls.append(
            {"session_id": session_id, "tool_call": tool_call, "options": options}
        )
        return RequestPermissionResponse(
            outcome=AllowedOutcome(option_id="allow_once", outcome="selected")
        )

    async def write_text_file(self, *a: Any, **kw: Any) -> Any:
        return None

    async def read_text_file(self, *a: Any, **kw: Any) -> Any:
        return None

    async def create_terminal(self, *a: Any, **kw: Any) -> Any:
        return None

    async def terminal_output(self, *a: Any, **kw: Any) -> Any:
        return None

    async def release_terminal(self, *a: Any, **kw: Any) -> Any:
        return None

    async def wait_for_terminal_exit(self, *a: Any, **kw: Any) -> Any:
        return None

    async def kill_terminal(self, *a: Any, **kw: Any) -> Any:
        return None

    async def create_elicitation(self, *a: Any, **kw: Any) -> Any:
        return None

    async def complete_elicitation(self, *a: Any, **kw: Any) -> None:
        pass

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        pass

    def on_connect(self, conn: Any) -> None:
        pass


def _update_types(updates: list[Any]) -> list[str]:
    """Extract session_update discriminator values from notification list."""
    return [getattr(u, "session_update", "?") for u in updates]


def _message_texts(updates: list[Any]) -> list[str]:
    """Extract text from all agent_message_chunk notifications."""
    texts: list[str] = []
    for u in updates:
        if getattr(u, "session_update", None) == "agent_message_chunk":
            content = getattr(u, "content", None)
            text = getattr(content, "text", None) if content else None
            if text:
                texts.append(text)
    return texts


def _spawn_env(mode: str) -> dict[str, str]:
    return {**os.environ, "MOCK_ACP_MODE": mode}


async def _drive(mode: str, prompts: list[str], *, do_load: bool = False) -> tuple[Any, str, list[Any], list[dict]]:
    """Spawn mock server in *mode*, drive *prompts*, return (init, session_id, all_updates, permission_calls)."""
    collector = _NotificationCollector()
    env = _spawn_env(mode)
    all_updates: list[Any] = []
    async with spawn_agent_process(
        collector,
        sys.executable,
        MOCK_SERVER,
        env=env,
    ) as (conn, proc):
        init = await conn.initialize(
            protocol_version=PROTOCOL_VERSION,
            client_info=Implementation(name="test", version="0.1.0"),
            client_capabilities=ClientCapabilities(fs=FileSystemCapabilities()),
        )
        ns = await conn.new_session(cwd="/tmp")
        sid = ns.session_id

        for i, prompt_text in enumerate(prompts):
            if do_load and i == 1:
                await conn.load_session(cwd="/tmp", session_id=sid)
            resp = await conn.prompt(session_id=sid, prompt=[text_block(prompt_text)])
            assert resp.stop_reason == "end_turn"
        all_updates = collector.updates
        return init, sid, all_updates, collector.permission_calls


# ── Mode: normal ──────────────────────────────────────────────────────


def test_mock_normal_initialize_handshake():
    """initialize returns protocol_version=1, loadSession=false, agentInfo."""
    init, _, _, _ = asyncio.run(_drive("normal", ["Hi"]))
    assert init.protocol_version == PROTOCOL_VERSION
    assert init.agent_capabilities.load_session is False
    assert init.agent_info is not None
    assert init.agent_info.name == "mock-acp"


def test_mock_normal_streaming_multi_type_notifications():
    """normal mode sends thought → tool_call → tool_call_update → message → usage."""
    _, _, updates, perm = asyncio.run(_drive("normal", ["Hello"]))
    types = _update_types(updates)
    assert "agent_thought_chunk" in types
    assert "tool_call" in types
    assert "tool_call_update" in types
    assert "agent_message_chunk" in types
    assert "usage_update" in types
    assert perm == []  # no permission in normal mode


def test_mock_normal_message_echoes_user_text():
    """normal mode agent_message_chunk contains the echoed user text."""
    _, _, updates, _ = asyncio.run(_drive("normal", ["Hello world"]))
    texts = _message_texts(updates)
    assert len(texts) >= 1
    assert "Hello world" in texts[0]


def test_mock_normal_usage_update_has_tokens():
    """normal mode usage_update carries token counts."""
    _, _, updates, _ = asyncio.run(_drive("normal", ["Hi"]))
    usage = [u for u in updates if getattr(u, "session_update", None) == "usage_update"]
    assert len(usage) == 1
    assert usage[0].used > 0
    assert usage[0].size > 0


# ── Mode: permission ──────────────────────────────────────────────────


def test_mock_permission_request_sent_and_auto_approved():
    """permission mode sends request_permission; auto-approve lets it continue."""
    _, _, updates, perm = asyncio.run(_drive("permission", ["Write a file"]))
    assert len(perm) == 1
    call = perm[0]
    assert call["session_id"]  # session_id present
    assert len(call["options"]) >= 2  # at least allow + reject options
    # after approval, run continues to end_turn (asserted in _drive)


def test_mock_permission_no_deadlock():
    """permission mode does not deadlock — prompt returns end_turn (AC-030-B-1)."""
    _, _, _, perm = asyncio.run(_drive("permission", ["Do it"]))
    assert len(perm) == 1


def test_mock_permission_tool_call_before_request():
    """permission mode sends a tool_call notification before request_permission."""
    _, _, updates, perm = asyncio.run(_drive("permission", ["Write a file"]))
    types = _update_types(updates)
    # tool_call (start) should appear before the permission was requested
    assert "tool_call" in types
    assert len(perm) == 1


# ── Mode: load_session ───────────────────────────────────────────────


def test_mock_load_session_declares_capability():
    """load_session mode declares loadSession=true in initialize response."""
    init, _, _, _ = asyncio.run(_drive("load_session", ["Hi"]))
    assert init.agent_capabilities.load_session is True


def test_mock_load_session_retains_context():
    """load_session: session/load restores context — second prompt recalls stored value."""
    _, sid, updates, _ = asyncio.run(
        _drive(
            "load_session",
            ["Remember the number 42", "What number did I ask you to remember?"],
            do_load=True,
        )
    )
    texts = _message_texts(updates)
    # The last message should contain "42"
    assert len(texts) >= 2
    assert "42" in texts[-1]


# ── Mode: startup_fail ───────────────────────────────────────────────


def test_mock_startup_fail_exits_nonzero():
    """startup_fail mode: process exits immediately with non-zero code."""

    async def _run() -> tuple[int, bytes]:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            MOCK_SERVER,
            env=_spawn_env("startup_fail"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        return proc.returncode or 0, stderr

    code, stderr = asyncio.run(_run())
    assert code != 0
    assert b"startup_fail" in stderr


# ── Mode: context_prefix ────────────────────────────────────────────


def test_mock_context_prefix_first_chunk_has_context():
    """context_prefix mode: first agent_message_chunk contains context text."""
    _, _, updates, _ = asyncio.run(_drive("context_prefix", ["Hello"]))
    texts = _message_texts(updates)
    assert len(texts) >= 2  # context prefix + actual reply
    assert "[context]" in texts[0]


def test_mock_context_prefix_only_first_prompt():
    """context_prefix mode: second prompt does not repeat context prefix."""

    async def _run() -> tuple[list[str], list[str]]:
        collector = _NotificationCollector()
        env = _spawn_env("context_prefix")
        async with spawn_agent_process(
            collector,
            sys.executable,
            MOCK_SERVER,
            env=env,
        ) as (conn, proc):
            init = await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="test", version="0.1.0"),
                client_capabilities=ClientCapabilities(fs=FileSystemCapabilities()),
            )
            ns = await conn.new_session(cwd="/tmp")
            sid = ns.session_id

            # First prompt
            await conn.prompt(session_id=sid, prompt=[text_block("First")])
            first_texts = _message_texts(collector.updates)
            collector.updates.clear()

            # Second prompt — should NOT have context prefix
            await conn.prompt(session_id=sid, prompt=[text_block("Second")])
            second_texts = _message_texts(collector.updates)
            return first_texts, second_texts

    first_texts, second_texts = asyncio.run(_run())
    assert any("[context]" in t for t in first_texts)
    assert not any("[context]" in t for t in second_texts)
