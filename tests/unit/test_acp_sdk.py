"""Unit tests for AcpSdkTransport — sync/async bridge, notification dispatch, permission auto-approve.

Covers the internal mechanics of the SDK-backed ACP transport without
spawning real subprocesses (where feasible), per ADR-0049.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

MOCK_SERVER = str(
    Path(__file__).resolve().parent.parent / "agent_support" / "mock_acp_server.py"
)


def _mock_command() -> list[str]:
    return [sys.executable, MOCK_SERVER]


def _mock_env(mode: str) -> dict[str, str]:
    return {**os.environ, "MOCK_ACP_MODE": mode}


# ── sync/async bridge ────────────────────────────────────────────────────


def test_transport_event_loop_starts_and_stops():
    """The dedicated daemon thread + persistent event loop starts and stops cleanly."""
    from loopflow.infrastructure.transports.acp_sdk import AcpSdkTransport

    transport = AcpSdkTransport(command=_mock_command())
    transport._start_loop()
    assert transport._loop is not None
    assert transport._loop.is_running()
    assert transport._loop_thread is not None
    assert transport._loop_thread.is_alive()

    # Submit a trivial coroutine
    async def _trivial():
        return 42

    result = transport._run_async(_trivial(), timeout=5.0)
    assert result == 42

    # Stop
    transport._stop_loop()
    assert transport._loop is None or not transport._loop.is_running()


def test_transport_run_async_blocks_until_complete():
    """_run_async blocks the calling thread until the coroutine resolves."""
    from loopflow.infrastructure.transports.acp_sdk import AcpSdkTransport

    transport = AcpSdkTransport(command=_mock_command())
    transport._start_loop()

    async def _slow():
        await asyncio.sleep(0.05)
        return "done"

    start = time.monotonic()
    result = transport._run_async(_slow(), timeout=5.0)
    elapsed = time.monotonic() - start
    assert result == "done"
    assert elapsed >= 0.04  # blocked until coroutine completed

    transport._stop_loop()


# ── _AutoApproveClient ───────────────────────────────────────────────────


def test_auto_approve_client_returns_allowed_outcome():
    """request_permission returns AllowedOutcome with outcome='selected'."""
    from loopflow.infrastructure.transports.acp_sdk import _AutoApproveClient

    received_updates: list[Any] = []
    client = _AutoApproveClient(on_update=lambda sid, upd: received_updates.append((sid, upd)))

    # Create mock options
    from acp.schema import PermissionOption

    options = [
        PermissionOption(option_id="allow_once", name="Allow once", kind="allow_once"),
        PermissionOption(option_id="reject_once", name="Reject once", kind="reject_once"),
    ]

    # Run the coroutine
    result = asyncio.run(client.request_permission("session-1", None, options))
    assert result is not None
    assert result.outcome is not None
    # The outcome should be an AllowedOutcome
    assert result.outcome.option_id == "allow_once"
    assert result.outcome.outcome == "selected"


def test_auto_approve_client_session_update_forwarded():
    """session_update notifications are forwarded to the on_update callback."""
    from loopflow.infrastructure.transports.acp_sdk import _AutoApproveClient

    received: list[tuple[str, Any]] = []
    client = _AutoApproveClient(on_update=lambda sid, upd: received.append((sid, upd)))

    # Create a mock update object
    mock_update = MagicMock()
    mock_update.session_update = "agent_message_chunk"

    asyncio.run(client.session_update("session-1", mock_update))
    assert len(received) == 1
    assert received[0][0] == "session-1"
    assert received[0][1] is mock_update


# ── notification dispatch ────────────────────────────────────────────────


def test_transport_notification_handler_registered():
    """on_notification registers a handler that _handle_session_update dispatches to."""
    from loopflow.infrastructure.transports.acp_sdk import AcpSdkTransport

    transport = AcpSdkTransport(command=_mock_command())
    received: list[dict] = []
    transport.on_notification("session/update", received.append)

    # Create a mock update with Pydantic-like model_dump
    mock_update = MagicMock()
    mock_update.session_update = "agent_message_chunk"
    mock_update.model_dump.return_value = {
        "session_update": "agent_message_chunk",
        "content": {"type": "text", "text": "hello"},
    }

    transport._handle_session_update("session-1", mock_update)
    assert len(received) == 1
    params = received[0]
    assert "update" in params


# ── context prefix filtering ─────────────────────────────────────────────


def test_context_filter_strips_context_prefix():
    """The backend's context filter strips [context] prefixed lines from message chunks."""
    from loopflow.infrastructure.backends.acp_sdk_backend import AcpSdkBackend

    backend = AcpSdkBackend(command=["echo"])

    # Test the filter method directly
    assert backend._is_context_line("[context] AGENTS.md: project rules")
    assert backend._is_context_line("[context] skills: available tools")
    assert not backend._is_context_line("This is a real agent message")
    assert not backend._is_context_line("Echo: Hello")


def test_context_filter_empty_string():
    """Empty strings are not context lines."""
    from loopflow.infrastructure.backends.acp_sdk_backend import AcpSdkBackend

    backend = AcpSdkBackend(command=["echo"])
    assert not backend._is_context_line("")


# ── capabilities timing ──────────────────────────────────────────────────


def test_capabilities_before_initialize_returns_defaults():
    """Before initialize, capabilities returns default Capabilities (no crash)."""
    from loopflow.domain.capabilities import Capabilities
    from loopflow.infrastructure.backends.acp_sdk_backend import AcpSdkBackend

    backend = AcpSdkBackend(command=["echo"])
    caps = backend.capabilities
    assert isinstance(caps, Capabilities)
    assert caps.resume_session is False
    assert caps.durable_session_id is False


# ── import guard ─────────────────────────────────────────────────────────


def test_acp_not_installed_error_constant():
    """ACP_NOT_INSTALLED_ERROR contains actionable install hint."""
    from loopflow.infrastructure.backends.acp_sdk_backend import ACP_NOT_INSTALLED_ERROR

    assert "acp" in ACP_NOT_INSTALLED_ERROR.lower()
    assert "install" in ACP_NOT_INSTALLED_ERROR.lower()
