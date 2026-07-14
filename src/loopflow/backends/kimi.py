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

    _supports_native_goal: bool = True  # kimi -p "/goal xxx" internal goal loop

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

    def create_session(self, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", agent_def: AgentDef | None = None, skills_dir: str | None = None) -> tuple[str, int]:
        if self._acp:
            try:
                return self._acp.create_session(user, system, model, system_mode, agent_def)
            except Exception:
                self._acp = None
                self._cli = _KimiCli(text_handler=self._th, thought_handler=self._thought_handler)
        return self._cli.create_session(user, system, model, system_mode, agent_def, skills_dir)

    def resume_session(self, sid: str, user: str, system: str | None = None, model: str | None = None, system_mode: str = "append", agent_def: AgentDef | None = None, skills_dir: str | None = None) -> int:
        if self._acp:
            try:
                return self._acp.resume_session(sid, user, system, model, system_mode, agent_def)
            except Exception:
                self._acp = None
                self._cli = _KimiCli(text_handler=self._th, thought_handler=self._thought_handler)
        return self._cli.resume_session(sid, user, system, model, system_mode, agent_def, skills_dir)

    def list_sessions(self) -> list[dict]:
        return self._acp.list_sessions() if self._acp else []

    def close(self) -> None:
        if self._acp:
            self._acp.close()
        if self._cli:
            self._cli.close()


class _KimiCli(CliBackend):
    """Kimi CLI backend with message-level buffering.

    Both stdout (text) and stderr (thinking) use • prefix as
    message delimiter. Lines are buffered until the next • or
    end-of-stream, then flushed as complete messages.
    """

    _sid_on_stderr = True
    _skill_flag = "--skills-dir"
    _supports_native_goal = True

    def __init__(self, text_handler=None, thought_handler=None, backend_name: str = "kimi"):
        super().__init__(text_handler=text_handler, thought_handler=thought_handler, backend_name=backend_name)
        self._stdout_buf: list[str] = []
        self._stderr_buf: list[str] = []

    # ── stdout: text messages ──────────────────────────────────────────

    def _normalize_line(self, line: str) -> str:
        """Buffer stdout lines by • delimiter. Returns empty string
        — complete messages are flushed directly to text_handler."""
        if line.startswith("• "):
            self._flush_stdout()
            self._stdout_buf = [line[2:]]  # strip "• "
        else:
            self._stdout_buf.append(line)
        return ""

    def _flush_stdout(self) -> None:
        if self._stdout_buf:
            text = "\n".join(self._stdout_buf).strip()
            self._stdout_buf = []
            if self._text_handler and text:
                self._text_handler(text)

    # ── stderr: thinking + system messages ─────────────────────────────

    def _on_stderr_line(self, line: str) -> None:
        if line.startswith("•"):
            self._flush_stderr()
            # Strip bullet prefix (with or without trailing space)
            prefix_len = 2 if line.startswith("• ") else 1
            self._stderr_buf = [line[prefix_len:]]
        elif "To resume this session:" in line:
            return
        elif self._stderr_buf:
            self._stderr_buf.append(line)
        elif self._thought_handler:
            self._thought_handler(line)
        else:
            print(line, file=sys.stderr, flush=True)

    def _flush_stderr(self) -> None:
        if self._stderr_buf:
            text = "\n".join(self._stderr_buf).strip()
            self._stderr_buf = []
            if self._thought_handler and text:
                self._thought_handler(text)

    # ── session lifecycle ──────────────────────────────────────────────

    def create_session(self, user: str, system: str | None = None,
                       model: str | None = None, system_mode: str = "append",
                       agent_def: AgentDef | None = None,
                       skills_dir: str | None = None) -> tuple[str, int]:
        sid, ec = super().create_session(user, system, model, system_mode, agent_def, skills_dir)
        self._flush_stdout()
        self._flush_stderr()
        return sid, ec

    def resume_session(self, sid: str, user: str, system: str | None = None,
                       model: str | None = None, system_mode: str = "append",
                       agent_def: AgentDef | None = None,
                       skills_dir: str | None = None) -> int:
        ec = super().resume_session(sid, user, system, model, system_mode, agent_def, skills_dir)
        self._flush_stdout()
        self._flush_stderr()
        return ec

    # ── commands ───────────────────────────────────────────────────────

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

    def _parse_line(self, line: str) -> tuple[str | None, str | None]:
        m = _SESSION_ID_RE.search(line)
        return (None, m.group(1) if m else None)