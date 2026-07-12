"""Gemini backend — CLI mode (default), ACP when explicitly requested."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopflow.backends.base import BaseBackend
from loopflow.backends.acp_backend import AcpBackend
from loopflow.backends.cli_backend import CliBackend

if TYPE_CHECKING:
    from loopflow.agent import AgentDef


class GeminiBackend(BaseBackend):
    """Backend for gemini-cli. CLI mode (default), ACP when explicitly requested."""

    def __init__(self, transport: str | None = None, text_handler=None, backend_name: str = "gemini"):
        use_acp = transport == "acp"
        self._th = text_handler
        if use_acp:
            self._acp = AcpBackend(["gemini", "--acp"], text_handler=text_handler)
            self._cli = None
        else:
            self._acp = None
            self._cli = _GeminiCli(text_handler=text_handler, backend_name=backend_name)

    def create_session(self, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", agent_def: AgentDef | None = None) -> tuple[str, int]:
        if self._acp:
            try:
                return self._acp.create_session(user, system, model, system_mode, requires)
            except Exception:
                self._acp = None
                self._cli = _GeminiCli(text_handler=self._th)
        return self._cli.create_session(user, system, model, system_mode, requires)

    def resume_session(self, sid: str, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", agent_def: AgentDef | None = None) -> int:
        if self._acp:
            try:
                return self._acp.resume_session(sid, user, system, model, system_mode, requires)
            except Exception:
                self._acp = None
                self._cli = _GeminiCli(text_handler=self._th)
        return self._cli.resume_session(sid, user, system, model, system_mode, requires)

    def list_sessions(self) -> list[dict]:
        return self._acp.list_sessions() if self._acp else []

    def close(self) -> None:
        if self._acp:
            self._acp.close()
        if self._cli:
            self._cli.close()


class _GeminiCli(CliBackend):
    def _cmd_create(self, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        prompt = f"System: {system}\n\nTask: {user}" if system else user
        cmd = ["gemini", "-p", prompt, "-y", "--skip-trust", "-o", "stream-json"]
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _cmd_resume(self, sid: str, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        prompt = f"System: {system}\n\nTask: {user}" if system else user
        cmd = ["gemini", "-p", prompt, "-y", "--skip-trust", "-o", "stream-json", "-r", sid]
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _parse_line(self, line: str) -> tuple[str | None, str | None]:
        data = self._try_parse_json(line)
        if data is None:
            return (line, None)
        tp = data.get("type", "")
        if tp == "init":
            return (None, data.get("session_id") or None)
        if tp == "message" and data.get("role") == "assistant":
            return (data.get("content", ""), None)
        if tp == "result":
            return (None, None)
        return (None, None)