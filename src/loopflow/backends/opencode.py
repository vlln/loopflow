"""Opencode backend — CLI mode (default), ACP when explicitly requested."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopflow.backends.base import BaseBackend
from loopflow.backends.acp_backend import AcpBackend
from loopflow.backends.cli_backend import CliBackend

if TYPE_CHECKING:
    from loopflow.agent import AgentRequires


class OpencodeBackend(BaseBackend):
    """Backend for opencode. CLI mode (default), ACP when explicitly requested."""

    def __init__(self, transport: str | None = None, text_handler=None, backend_name: str = "opencode"):
        use_acp = transport == "acp"
        self._th = text_handler
        if use_acp:
            self._acp = AcpBackend(["opencode", "acp"], text_handler=text_handler)
            self._cli = None
        else:
            self._acp = None
            self._cli = _OpencodeCli(text_handler=text_handler, backend_name=backend_name)

    def create_session(self, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", requires: AgentRequires | None = None) -> tuple[str, int]:
        if self._acp:
            try:
                return self._acp.create_session(user, system, model, system_mode, requires)
            except Exception:
                self._acp = None
                self._cli = _OpencodeCli(text_handler=self._th)
        return self._cli.create_session(user, system, model, system_mode, requires)

    def resume_session(self, sid: str, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", requires: AgentRequires | None = None) -> int:
        if self._acp:
            try:
                return self._acp.resume_session(sid, user, system, model, system_mode, requires)
            except Exception:
                self._acp = None
                self._cli = _OpencodeCli(text_handler=self._th)
        return self._cli.resume_session(sid, user, system, model, system_mode, requires)

    def list_sessions(self) -> list[dict]:
        return self._acp.list_sessions() if self._acp else []

    def close(self) -> None:
        if self._acp:
            self._acp.close()
        if self._cli:
            self._cli.close()


class _OpencodeCli(CliBackend):
    def _cmd_create(self, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        prompt = f"System: {system}\n\nTask: {user}" if system else user
        cmd = ["opencode", "run", "--format", "json", "--dangerously-skip-permissions", "--title", "subagents", prompt]
        if model:
            cmd.extend(["--model", model])
        return cmd

    def _cmd_resume(self, sid: str, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        cmd = ["opencode", "run", "--format", "json", "--dangerously-skip-permissions", "--session", sid, user]
        if model:
            cmd.extend(["--model", model])
        return cmd

    def _parse_line(self, line: str) -> tuple[str | None, str | None]:
        data = self._try_parse_json(line)
        if data is None:
            return (line, None)
        tp = data.get("type", "")
        if tp in ("step_start", "step_finish"):
            return (None, data.get("sessionID") or None)
        if tp == "text":
            return (data.get("part", {}).get("text", ""), None)
        return (None, None)