"""Kimi backend — CLI mode (default), ACP when explicitly requested."""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from loopflow.backends.base import BaseBackend
from loopflow.backends.acp_backend import AcpBackend
from loopflow.backends.cli_backend import CliBackend

if TYPE_CHECKING:
    from loopflow.agent import AgentDef

_SESSION_ID_RE = re.compile(r"kimi -r (session_[a-f0-9-]+)")


class KimiBackend(BaseBackend):
    """Backend for kimi-code. CLI mode (default), ACP when explicitly requested."""

    def __init__(self, transport: str | None = None, text_handler=None, thought_handler=None, backend_name: str = "kimi", **kwargs):
        use_acp = transport == "acp"
        self._th = text_handler
        self._thought_handler = thought_handler
        if use_acp:
            self._acp = AcpBackend(["kimi", "acp"], text_handler=text_handler)
            self._cli = None
        else:
            self._acp = None
            self._cli = _KimiCli(text_handler=text_handler, thought_handler=thought_handler, backend_name=backend_name)

    def create_session(self, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", agent_def: AgentDef | None = None) -> tuple[str, int]:
        if self._acp:
            try:
                return self._acp.create_session(user, system, model, system_mode, agent_def)
            except Exception:
                self._acp = None
                self._cli = _KimiCli(text_handler=self._th, thought_handler=self._thought_handler)
        return self._cli.create_session(user, system, model, system_mode, agent_def)

    def resume_session(self, sid: str, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", agent_def: AgentDef | None = None) -> int:
        if self._acp:
            try:
                return self._acp.resume_session(sid, user, system, model, system_mode, agent_def)
            except Exception:
                self._acp = None
                self._cli = _KimiCli(text_handler=self._th, thought_handler=self._thought_handler)
        return self._cli.resume_session(sid, user, system, model, system_mode, agent_def)

    def list_sessions(self) -> list[dict]:
        return self._acp.list_sessions() if self._acp else []

    def close(self) -> None:
        if self._acp:
            self._acp.close()
        if self._cli:
            self._cli.close()


class _KimiCli(CliBackend):
    _sid_on_stderr = True
    _skill_flag = "--skills-dir"

    def _cmd_create(self, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        prompt = f"System: {system}\n\nTask: {user}" if system else user
        cmd = ["kimi", "-p", prompt]
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _cmd_resume(self, sid: str, user: str, system: str | None, model: str | None, system_mode: str) -> list[str]:
        prompt = f"System: {system}\n\nTask: {user}" if system else user
        cmd = ["kimi", "-S", sid, "-p", prompt]
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _normalize_line(self, line: str) -> str:
        """Strip kimi's hardcoded bullet prefix."""
        if line.startswith("• "):
            return line[2:]
        return line

    def _parse_line(self, line: str) -> tuple[str | None, str | None]:
        m = _SESSION_ID_RE.search(line)
        return (None, m.group(1) if m else None)

    def _on_stderr_line(self, line: str) -> None:
        if line.startswith("\u2022") or "To resume this session:" in line:
            return
        if self._thought_handler:
            self._thought_handler(line)
        else:
            print(line, file=sys.stderr, flush=True)