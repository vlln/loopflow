from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ReplayDiverged(ValueError):
    pass


def stable_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def parallel_call_id(parent: int | str, branch: int, local: int = 1) -> str:
    parent_id = f"{parent:04d}" if isinstance(parent, int) else parent
    return f"{parent_id}.{branch:04d}.{local:04d}"


@dataclass(frozen=True)
class CacheSegment:
    kind: str
    call_id: str
    input_digest: str | None
    events: tuple[dict[str, Any], ...]
    corrupt: bool = False

    @property
    def messages(self) -> list[str]:
        return [
            str(event["content"])
            for event in self.events
            if event.get("type") in {"agent_message", "agent_message_chunk"}
            and "content" in event
        ]

    @property
    def done(self) -> dict[str, Any] | None:
        return next(
            (event for event in reversed(self.events) if event.get("type") == "agent_done"),
            None,
        )


def read_segments(path: Path) -> list[CacheSegment]:
    """Parse complete lifecycle segments without borrowing events across segments."""
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            if current is not None:
                current["corrupt"] = True
            break
        if event.get("type") in {"agent_start", "agent_resume"}:
            current = {
                "kind": event["type"],
                "call_id": str(event.get("call_id", "")),
                "input_digest": event.get("input_digest"),
                "events": [event],
                "corrupt": False,
            }
            segments.append(current)
        elif current is not None:
            current["events"].append(event)
    return [
        CacheSegment(
            kind=item["kind"],
            call_id=item["call_id"],
            input_digest=item["input_digest"],
            events=tuple(item["events"]),
            corrupt=item["corrupt"],
        )
        for item in segments
    ]


def select_replay_segment(
    path: Path, *, call_id: str, input_digest: str
) -> CacheSegment | None:
    """Return only a committed latest segment, rejecting semantic drift."""
    segments = read_segments(path)
    if not segments:
        return None
    segment = segments[-1]
    if segment.call_id != call_id or segment.input_digest != input_digest:
        raise ReplayDiverged(
            f"cached call {segment.call_id!r}/{segment.input_digest!r} does not match "
            f"{call_id!r}/{input_digest!r}"
        )
    done = segment.done
    if (
        segment.corrupt
        or done is None
        or done.get("status") != "succeeded"
        or done.get("exit_code") != 0
    ):
        return None
    return segment


class CallCacheFactory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, call_id: str) -> Path:
        return self.root / f"{call_id}.jsonl"

    def append_segment(
        self,
        call_id: str,
        *,
        input_digest: str,
        kind: str = "retry",
        status: str | None = "succeeded",
        messages: tuple[str, ...] = ("result",),
        session_id: str | None = "session-1",
        exit_code: int | None = 0,
    ) -> Path:
        path = self.path(call_id)
        start_type = "agent_resume" if kind == "continue" else "agent_start"
        events: list[dict[str, Any]] = [
            {
                "type": start_type,
                "call_id": call_id,
                "input_digest": input_digest,
            }
        ]
        if session_id is not None:
            events.append(
                {"type": "agent_session", "call_id": call_id, "session_id": session_id}
            )
        events.extend(
            {"type": "agent_message_chunk", "content": message}
            for message in messages
        )
        if status is not None:
            done = {
                "type": "agent_done",
                "call_id": call_id,
                "status": status,
                "exit_code": exit_code,
            }
            if session_id is not None:
                done["session_id"] = session_id
            events.append(done)
        with path.open("a", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
                stream.write("\n")
        return path

    def succeeded(self, call_id: str, input_digest: str, message: str = "result") -> Path:
        return self.append_segment(
            call_id, input_digest=input_digest, messages=(message,), status="succeeded"
        )

    def failed(
        self, call_id: str, input_digest: str, *, session_id: str | None = "session-1"
    ) -> Path:
        return self.append_segment(
            call_id,
            input_digest=input_digest,
            messages=("failed-output",),
            status="failed",
            session_id=session_id,
            exit_code=1,
        )

    def interrupted(
        self, call_id: str, input_digest: str, *, session_id: str | None = "session-1"
    ) -> Path:
        return self.append_segment(
            call_id,
            input_digest=input_digest,
            messages=("partial",),
            status=None,
            session_id=session_id,
            exit_code=None,
        )

    def segmented(self, call_id: str, input_digest: str) -> Path:
        self.failed(call_id, input_digest, session_id="session-old")
        return self.append_segment(
            call_id,
            input_digest=input_digest,
            kind="retry",
            messages=("new-output",),
            status="succeeded",
            session_id="session-new",
        )

    def corrupt(self, call_id: str, input_digest: str) -> Path:
        path = self.interrupted(call_id, input_digest)
        with path.open("a", encoding="utf-8") as stream:
            stream.write('{"type":"agent_message_chunk"')
        return path

    def legacy(self, sequence: int, message: str = "legacy") -> Path:
        path = self.root / f"{sequence:04d}.jsonl"
        events = [
            {"type": "agent_message", "content": message},
            {"type": "agent_done", "exit_code": 0},
        ]
        path.write_text(
            "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events),
            encoding="utf-8",
        )
        return path
