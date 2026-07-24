"""Grok backend - calls the `grok` CLI or ACP stdio agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loopflow.infrastructure.backends.acp_backend import AcpBackend
from loopflow.infrastructure.backends.base import BaseBackend
from loopflow.infrastructure.backends.cli_backend import CliBackend

if TYPE_CHECKING:
    from loopflow.domain import AgentDef


class GrokBackend(BaseBackend):
    """Backend for Grok Build. CLI mode by default, ACP when explicitly requested."""

    @property
    def capabilities(self):
        return self._selected.capabilities

    def __init__(self, transport: str | None = None, text_handler=None, thought_handler=None, session_handler=None, backend_name: str = "grok"):
        if transport == "acp":
            self._selected = _GrokAcp(text_handler=text_handler, thought_handler=thought_handler, session_handler=session_handler)
        else:
            self._selected = _GrokCli(text_handler=text_handler, thought_handler=thought_handler, session_handler=session_handler, backend_name=backend_name)

    def create_session(
        self,
        user: str,
        system: str | None = None,
        model: str | None = None,
        system_mode: str = "append",
        agent_def: AgentDef | None = None,
    ) -> tuple[str, int]:
        return self._selected.create_session(user, system, model, system_mode, agent_def)

    def resume_session(
        self,
        session_id: str,
        user: str,
        system: str | None = None,
        model: str | None = None,
        system_mode: str = "append",
        agent_def: AgentDef | None = None,
    ) -> int:
        return self._selected.resume_session(session_id, user, system, model, system_mode, agent_def)

    def close(self) -> None:
        self._selected.close()


class _GrokCli(CliBackend):
    def _cmd_create(self, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        cmd = [
            "grok",
            "-p",
            user,
            "--output-format",
            "streaming-json",
            "--permission-mode",
            "bypassPermissions",
        ]
        if system:
            if system_mode == "overwrite":
                cmd.extend(["--system-prompt-override", system])
            else:
                cmd.extend(["--rules", system])
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _cmd_resume(self, sid: str, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        cmd = [
            "grok",
            "-p",
            user,
            "--output-format",
            "streaming-json",
            "--resume",
            sid,
            "--permission-mode",
            "bypassPermissions",
        ]
        if system:
            if system_mode == "overwrite":
                cmd.extend(["--system-prompt-override", system])
            else:
                cmd.extend(["--rules", system])
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _parse_line(self, line: str) -> tuple[str | None, str | None]:
        data = self._try_parse_json(line)
        if data is None:
            return (line, None)
        tp = data.get("type", "")
        if tp == "text":
            return (data.get("data", ""), None)
        if tp == "thought":
            if self._thought_handler:
                self._thought_handler(data.get("data", ""))
            return (None, None)
        if tp == "end":
            return (None, data.get("sessionId") or None)
        if tp == "error":
            return (data.get("message", ""), data.get("sessionId") or None)
        return (None, data.get("sessionId") or None)


class _GrokAcp(AcpBackend):
    def __init__(self, text_handler=None, thought_handler=None, session_handler=None):
        super().__init__(["grok", "agent", "stdio"], text_handler=text_handler)
        self._thought_handler = thought_handler
        self._session_handler = session_handler
        self._transport.on_notification("x.ai/session/update", self._on_update)

    def _on_update(self, params: dict) -> None:
        update = params.get("update")
        if not isinstance(update, dict):
            update = params.get("sessionUpdate")
        if not isinstance(update, dict):
            return

        kind = update.get("sessionUpdate")
        content = update.get("content", {})
        text = content.get("text") if isinstance(content, dict) else None
        if kind == "agent_message_chunk" and text:
            self._emit_text(text)
        elif kind == "agent_thought_chunk" and text and self._thought_handler:
            self._thought_handler(text)

    def _emit_text(self, text: str) -> None:
        if self._text_handler:
            self._text_handler(text)
        else:
            import sys

            sys.stdout.write(text)
            sys.stdout.flush()

    def _session_meta(self, system: str | None, system_mode: str) -> dict:
        if not system:
            return {}
        if system_mode == "overwrite":
            return {"systemPromptOverride": system}
        return {"rules": system}

    def create_session(
        self,
        user: str,
        system: str | None = None,
        model: str | None = None,
        system_mode: str = "append",
        agent_def: AgentDef | None = None,
    ) -> tuple[str, int]:
        self._ensure_initialized()
        params = {"cwd": str(Path.cwd()), "mcpServers": self._build_mcp_servers(agent_def)}
        meta = self._session_meta(system, system_mode)
        if meta:
            params["_meta"] = meta
        try:
            result = self._transport.call("session/new", params)
        except RuntimeError:
            self._authenticate()
            result = self._transport.call("session/new", params)

        sid = result.get("sessionId", "")
        if not sid:
            raise RuntimeError("ACP: session/new returned no sessionId")
        if self._session_handler:
            self._session_handler(sid)
        if model:
            self._transport.call("session/set_model", {"sessionId": sid, "modelId": model})
        try:
            self._transport.call(
                "session/prompt",
                {"sessionId": sid, "prompt": [{"type": "text", "text": user}]},
            )
            return sid, 0
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
    ) -> int:
        self._ensure_initialized()
        params = {
            "sessionId": session_id,
            "cwd": str(Path.cwd()),
            "mcpServers": self._build_mcp_servers(agent_def),
        }
        meta = self._session_meta(system, system_mode)
        if meta:
            params["_meta"] = meta
        try:
            self._transport.call("session/load", params)
        except RuntimeError:
            self._authenticate()
            self._transport.call("session/load", params)

        if model:
            self._transport.call("session/set_model", {"sessionId": session_id, "modelId": model})
        try:
            self._transport.call(
                "session/prompt",
                {"sessionId": session_id, "prompt": [{"type": "text", "text": user}]},
            )
            return 0
        except Exception:
            return 1
