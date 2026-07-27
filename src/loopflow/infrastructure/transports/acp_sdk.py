"""ACP transport backed by the official ``agent-client-protocol`` SDK.

Replaces the hand-rolled JSON-RPC pipeline in ``acp.py`` with the SDK's
stdio client transport + Pydantic schema models.  Provides a synchronous
API by running the SDK's asyncio coroutines on a dedicated daemon thread
with a persistent event loop.

Sync/async bridge (ADR-0049 §3, spike-verified):
    A dedicated daemon thread runs ``asyncio.new_event_loop()`` +
    ``run_forever()``.  All SDK coroutines are submitted via
    ``run_coroutine_threadsafe`` and blocked on with ``future.result()``.
    The persistent loop is required because the SDK's ``Connection`` class
    starts a background receive-loop task on construction — ``asyncio.run``
    per-op would tear down that task between calls.

This module is the protocol layer; session/notification mapping lives in
``backends/acp_sdk_backend.py``.  The sync/async bridge is fully
encapsulated here — no asyncio leaks to the application/domain layers.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

from acp import PROTOCOL_VERSION, spawn_agent_process, text_block
from acp.interfaces import Client
from acp.schema import (
    AllowedOutcome,
    ClientCapabilities,
    FileSystemCapabilities,
    Implementation,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PermissionOption,
    PromptResponse,
    RequestPermissionResponse,
)


class _AutoApproveClient(Client):
    """Minimal Client impl: auto-approve all permissions, forward session updates.

    Per ADR-0049 §4: fire-and-forget model → unified auto-approve-all
    (no read/write grading).  This eliminates the ADR-0018 authorization
    deadlock.
    """

    def __init__(self, on_update: Callable[[str, Any], None]) -> None:
        self._on_update = on_update

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        self._on_update(session_id, update)

    async def request_permission(
        self,
        session_id: str,
        tool_call: Any,
        options: list[PermissionOption],
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        # Auto-approve: pick the first allow_* option, else approve best-effort.
        # outcome="selected" is required by the SDK's Literal discriminator.
        for opt in options:
            if opt.kind in ("allow_once", "allow_always"):
                return RequestPermissionResponse(
                    outcome=AllowedOutcome(option_id=opt.option_id, outcome="selected"),
                )
        if options:
            return RequestPermissionResponse(
                outcome=AllowedOutcome(option_id=options[0].option_id, outcome="selected"),
            )
        return RequestPermissionResponse(
            outcome=AllowedOutcome(option_id="approve", outcome="selected"),
        )

    # ── unsupported client methods (fire-and-forget no-ops) ────────────

    async def write_text_file(self, *a: Any, **kw: Any) -> None:
        pass

    async def read_text_file(self, *a: Any, **kw: Any) -> Any:
        return None

    async def create_terminal(self, *a: Any, **kw: Any) -> Any:
        return None

    async def terminal_output(self, *a: Any, **kw: Any) -> Any:
        return None

    async def release_terminal(self, *a: Any, **kw: Any) -> None:
        pass

    async def wait_for_terminal_exit(self, *a: Any, **kw: Any) -> Any:
        return None

    async def kill_terminal(self, *a: Any, **kw: Any) -> None:
        pass

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


class AcpSdkTransport:
    """SDK-backed ACP transport with a synchronous API.

    Wraps ``spawn_agent_process`` + ``ClientSideConnection`` behind a
    thread-safe synchronous interface.  All asyncio work runs on a
    dedicated daemon-thread event loop.

    Args:
        command: Command list to spawn the ACP agent (e.g. ``["pi-acp"]``).
        client_info: Optional client identity for the initialize handshake.
        env: Optional environment dict for the spawned subprocess.
    """

    def __init__(
        self,
        command: list[str],
        client_info: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._client_info = client_info or {"name": "loopflow", "version": "0.21.0"}
        self._env = env
        self._conn: Any = None  # ClientSideConnection
        self._proc: Any = None  # asyncio subprocess
        self._cm: Any = None  # async context manager for spawn
        self._init_result: InitializeResponse | None = None
        self._notification_handlers: dict[str, Callable[[dict], None]] = {}

        # Sync/async bridge state
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_ready = threading.Event()

    # ── event loop bridge ────────────────────────────────────────────────

    def _start_loop(self) -> None:
        """Start the dedicated daemon thread + persistent event loop."""
        if self._loop is not None:
            return

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()

        self._loop_thread = threading.Thread(
            target=_run, daemon=True, name="acp-sdk-loop"
        )
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5.0)
        if self._loop is None:
            raise RuntimeError("Failed to start ACP SDK event loop thread")

    def _stop_loop(self) -> None:
        """Stop the event loop and join the daemon thread."""
        loop = self._loop
        thread = self._loop_thread
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)
        self._loop = None
        self._loop_thread = None
        self._loop_ready.clear()

    def _run_async(self, coro: Any, timeout: float = 120.0) -> Any:
        """Submit a coroutine to the persistent loop and block until it resolves."""
        if self._loop is None:
            raise RuntimeError("ACP SDK event loop not started")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ── notification dispatch ────────────────────────────────────────────

    def on_notification(self, method: str, handler: Callable[[dict], None]) -> None:
        """Register a handler for a notification method (e.g. 'session/update')."""
        self._notification_handlers[method] = handler

    def _handle_session_update(self, session_id: str, update: Any) -> None:
        """Map SDK SessionUpdate → loopflow-compatible notification dict."""
        handler = self._notification_handlers.get("session/update")
        if handler is None:
            return

        # Convert Pydantic model → dict for compatibility with backend handlers
        if hasattr(update, "model_dump"):
            u = update.model_dump(by_alias=True, exclude_none=True)
        elif isinstance(update, dict):
            u = update
        else:
            u = {}

        u["sessionId"] = session_id
        # Wrap in the params shape that the backend's _on_update expects
        params = {"update": {"sessionUpdate": u.get("session_update", ""), **u}}
        handler(params)

    # ── lifecycle ───────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the subprocess and perform ACP initialization."""
        if self._conn is not None:
            return
        self._start_loop()

        client = _AutoApproveClient(on_update=self._handle_session_update)

        async def _spawn_and_init():
            cm = spawn_agent_process(
                client,
                self._command[0],
                *self._command[1:],
                env=self._env,
            )
            self._cm = cm
            conn, proc = await cm.__aenter__()
            init_resp = await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(
                    name=self._client_info["name"],
                    version=self._client_info["version"],
                ),
                client_capabilities=ClientCapabilities(
                    fs=FileSystemCapabilities(
                        read_text_file=False, write_text_file=False
                    ),
                    terminal=False,
                ),
            )
            return conn, proc, init_resp

        self._conn, self._proc, self._init_result = self._run_async(_spawn_and_init())

    def close(self) -> None:
        """Shut down the subprocess and stop the event loop."""
        if self._conn is None:
            return

        async def _shutdown():
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass

        try:
            self._run_async(_shutdown(), timeout=10.0)
        except Exception:
            pass

        self._stop_loop()
        self._conn = None
        self._proc = None
        self._cm = None
        self._init_result = None

    # ── session methods (sync wrappers) ─────────────────────────────────

    @property
    def initialize_result(self) -> InitializeResponse | None:
        return self._init_result

    @property
    def agent_capabilities(self) -> dict[str, Any]:
        if self._init_result and self._init_result.agent_capabilities:
            return self._init_result.agent_capabilities.model_dump(
                by_alias=True, exclude_none=True
            )
        return {}

    def new_session(self, cwd: str) -> str:
        """session/new → returns sessionId."""
        resp: NewSessionResponse = self._run_async(self._conn.new_session(cwd=cwd))
        return resp.session_id

    def load_session(self, cwd: str, session_id: str) -> bool:
        """session/load → returns True on success."""
        try:
            resp = self._run_async(
                self._conn.load_session(cwd=cwd, session_id=session_id)
            )
            return resp is not None
        except Exception:
            return False

    def prompt(self, session_id: str, text: str) -> PromptResponse:
        """session/prompt → returns PromptResponse."""
        return self._run_async(
            self._conn.prompt(session_id=session_id, prompt=[text_block(text)])
        )

    def authenticate(self, method_id: str) -> bool:
        try:
            self._run_async(self._conn.authenticate(method_id=method_id))
            return True
        except Exception:
            return False

    @property
    def auth_methods(self) -> list[dict[str, Any]]:
        if self._init_result and self._init_result.auth_methods:
            return [
                m.model_dump(by_alias=True, exclude_none=True)
                for m in self._init_result.auth_methods
            ]
        return []

    @property
    def load_session_supported(self) -> bool:
        if self._init_result and self._init_result.agent_capabilities:
            return bool(self._init_result.agent_capabilities.load_session)
        return False

    @property
    def stderr_text(self) -> str:
        return ""  # SDK transport reads stderr via PIPE; text extraction is a future item
