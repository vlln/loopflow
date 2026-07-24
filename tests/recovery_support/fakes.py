from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Event
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class SessionCapabilities:
    resume_session: bool = True
    durable_session_id: bool = True


@dataclass
class SessionBackendFake:
    capabilities: SessionCapabilities = field(default_factory=SessionCapabilities)
    session_timing: str = "early"
    create_exit_code: int = 0
    resume_exit_code: int = 0
    session_id: str = "session-1"
    create_behavior: str = "success"
    resume_behavior: str = "success"
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)
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
        self._apply_behavior(self.create_behavior)
        sid = self.session_id if self.session_timing != "never" else ""
        if self.session_timing == "complete" and session_handler is not None:
            session_handler(sid)
        return sid, self.create_exit_code

    def resume_session(self, session_id: str, user: str, **_: Any) -> int:
        if not (
            self.capabilities.resume_session
            and self.capabilities.durable_session_id
        ):
            raise RuntimeError("durable resume_session unsupported")
        self.calls.append(("resume", user, session_id))
        self._apply_behavior(self.resume_behavior)
        return self.resume_exit_code


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
