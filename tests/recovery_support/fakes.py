from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Event
from types import SimpleNamespace
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class SessionCapabilities:
    resume_session: bool = True
    durable_session_id: bool = True


@dataclass(frozen=True)
class AttemptResult:
    """单次 create/resume 调用的脚本化结果（ADR-0048）。

    behavior 为 None 时沿用 fake 的固定 behavior 字段；
    error_category 为 None 表示后端未做结构化上报（ADR-0044 尽力而为通道）。
    """

    exit_code: int = 0
    stderr: str = ""
    error_category: str | None = None
    behavior: str | None = None


@dataclass
class SessionBackendFake:
    capabilities: SessionCapabilities = field(default_factory=SessionCapabilities)
    session_timing: str = "early"
    create_exit_code: int = 0
    resume_exit_code: int = 0
    session_id: str = "session-1"
    create_behavior: str = "success"
    resume_behavior: str = "success"
    create_script: list[AttemptResult] = field(default_factory=list)
    resume_script: list[AttemptResult] = field(default_factory=list)
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)
    results: list[AttemptResult] = field(default_factory=list)
    blocked: Event = field(default_factory=Event)
    release_block: Event = field(default_factory=Event)

    def _apply_behavior(self, behavior: str) -> None:
        if behavior == "exception":
            raise RuntimeError("injected backend exception")
        if behavior == "block":
            self.blocked.set()
            self.release_block.wait()
        elif behavior != "success":
            raise ValueError(f"unknown backend behavior: {behavior}")

    def _consume_attempt(
        self, script: list[AttemptResult], fixed_exit_code: int, fixed_behavior: str
    ) -> tuple[AttemptResult, str]:
        if script:
            attempt = script.pop(0)
            return attempt, attempt.behavior or fixed_behavior
        return AttemptResult(exit_code=fixed_exit_code), fixed_behavior

    def agent_done_payload(self) -> dict[str, Any]:
        """按 ADR-0044 契约产出 agent_done 事件 payload（基于最近一次调用结果）。"""
        if not self.results:
            raise RuntimeError("no session attempt recorded yet")
        last = self.results[-1]
        payload: dict[str, Any] = {
            "type": "agent_done",
            "exit_code": last.exit_code,
            "stderr": last.stderr,
            "session_id": self.session_id,
        }
        if last.error_category is not None:
            payload["error_category"] = last.error_category
        return payload

    def create_session(
        self,
        user: str,
        *,
        session_handler: Callable[[str], None] | None = None,
        **_: Any,
    ) -> tuple[str, int]:
        self.calls.append(("create", user, None))
        if self.session_timing == "early" and session_handler is not None:
            session_handler(self.session_id)
        attempt, behavior = self._consume_attempt(
            self.create_script, self.create_exit_code, self.create_behavior
        )
        self._apply_behavior(behavior)
        sid = self.session_id if self.session_timing != "never" else ""
        if self.session_timing == "complete" and session_handler is not None:
            session_handler(sid)
        self.results.append(attempt)
        return sid, attempt.exit_code

    def resume_session(self, session_id: str, user: str, **_: Any) -> int:
        if not (
            self.capabilities.resume_session
            and self.capabilities.durable_session_id
        ):
            raise RuntimeError("durable resume_session unsupported")
        self.calls.append(("resume", user, session_id))
        attempt, behavior = self._consume_attempt(
            self.resume_script, self.resume_exit_code, self.resume_behavior
        )
        self._apply_behavior(behavior)
        self.results.append(attempt)
        return attempt.exit_code

    def close(self) -> None:
        """与真实后端实例契约对齐（manager finally 分支调用）。"""

    @property
    def error_category(self) -> str | None:
        """ADR-0044 结构化上报通道：最近一次调用的分类（未上报为 None）。"""
        if not self.results:
            return None
        return self.results[-1].error_category

    @property
    def _transport(self) -> Any:
        """manager 读取 instance._transport.stderr_text 的契约桩。"""
        stderr = self.results[-1].stderr if self.results else ""
        return SimpleNamespace(stderr_text=stderr)


@dataclass
class AtomicWriterFake:
    fail_stage: str | None = None
    fail_on_call: int | None = None
    writes: list[tuple[str, Any]] = field(default_factory=list)
    published: dict[str, Any] = field(default_factory=dict)

    def write(self, path: str, value: Any) -> None:
        call_number = len(self.writes) + 1
        self.writes.append((path, value))
        if self.fail_on_call == call_number or self.fail_stage == "before_publish":
            raise OSError("injected atomic write failure")
        if self.fail_stage == "replace":
            raise OSError("injected replace failure")
        self.published[path] = value


@dataclass
class RunLockFake:
    occupied: bool = False
    acquisitions: int = 0
    releases: int = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        if self.occupied:
            raise RuntimeError("run lock occupied")
        self.occupied = True
        self.acquisitions += 1
        try:
            yield
        finally:
            self.occupied = False
            self.releases += 1


@dataclass
class ProcessGroupFake:
    identity_matches: bool = True
    exits_on_term: bool = True
    signals: list[str] = field(default_factory=list)

    def terminate(self) -> str:
        if not self.identity_matches:
            return "process_gone"
        self.signals.append("TERM")
        if self.exits_on_term:
            return "exited"
        self.signals.append("KILL")
        return "killed"


@dataclass
class EpochWriterFake:
    current_epoch: int
    states: list[str] = field(default_factory=list)

    def write_terminal(self, epoch: int, status: str) -> bool:
        if epoch != self.current_epoch:
            return False
        self.states.append(status)
        return True


@dataclass
class ClockFake:
    value: float = 0.0

    def monotonic(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds
