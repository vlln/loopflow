"""Durable Call cache primitives used by deterministic workflow recovery."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ReplayDiverged(RuntimeError):
    """The replayed logical Call no longer matches its persisted identity."""


@dataclass(frozen=True)
class CallSegment:
    call_id: str | None
    input_digest: str | None
    events: tuple[dict[str, Any], ...]
    corrupt: bool = False
    legacy: bool = False

    @property
    def done(self) -> dict[str, Any] | None:
        return next(
            (event for event in reversed(self.events) if event.get("type") == "agent_done"),
            None,
        )

    @property
    def text(self) -> str:
        return "\n".join(
            str(event["content"])
            for event in self.events
            if event.get("type") in {"agent_message", "agent_message_chunk", "agent_text"}
            and "content" in event
        )

    @property
    def session_id(self) -> str | None:
        for event in reversed(self.events):
            value = event.get("session_id")
            if isinstance(value, str) and value:
                return value
        return None

    @property
    def committed(self) -> bool:
        done = self.done
        return bool(
            not self.corrupt
            and done
            and done.get("status", "succeeded" if self.legacy else None) == "succeeded"
            and done.get("exit_code") == 0
        )


@dataclass(frozen=True)
class ReplaySelection:
    outcome: str
    segment: CallSegment | None = None


def stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def workflow_digest(loop_dir: Path | None) -> str | None:
    if loop_dir is None:
        return None
    path = loop_dir / "workflow.py"
    try:
        content = path.read_bytes()
    except OSError:
        return None
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def call_input_digest(
    *,
    loop_dir: Path | None,
    prompt: str,
    schema: dict[str, Any] | None,
    backend: str | None,
    model: str | None,
    agent_definition: str | None,
    execution_options: dict[str, Any] | None = None,
) -> str:
    return stable_digest(
        {
            "workflow": workflow_digest(loop_dir),
            "prompt": prompt,
            "schema": schema,
            "backend": backend,
            "model": model,
            "agent_definition": agent_definition,
            "execution_options": execution_options or {},
        }
    )


def parallel_call_id(parent: int | str, branch: int, local: int = 1) -> str:
    parent_id = f"{parent:04d}" if isinstance(parent, int) else str(parent)
    return f"{parent_id}.{branch:04d}.{local:04d}"


def append_cache_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
        stream.write("\n")


def read_call_segments(path: Path) -> list[CallSegment]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    legacy_events: list[dict[str, Any]] = []
    legacy_corrupt = False
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if current is not None:
                current["corrupt"] = True
            else:
                legacy_corrupt = True
            break
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"agent_start", "agent_resume"}:
            current = {
                "call_id": event.get("call_id"),
                "input_digest": event.get("input_digest"),
                "events": [event],
                "corrupt": False,
            }
            segments.append(current)
        elif current is not None:
            current["events"].append(event)
        else:
            legacy_events.append(event)
    if not segments and legacy_events:
        return [
            CallSegment(
                call_id=None,
                input_digest=None,
                events=tuple(legacy_events),
                corrupt=legacy_corrupt,
                legacy=True,
            )
        ]
    return [
        CallSegment(
            call_id=item["call_id"],
            input_digest=item["input_digest"],
            events=tuple(item["events"]),
            corrupt=item["corrupt"],
        )
        for item in segments
    ]


def select_for_replay(path: Path, *, call_id: str, input_digest: str) -> ReplaySelection:
    segments = read_call_segments(path)
    if not segments:
        return ReplaySelection("missing")
    latest = segments[-1]
    if latest.legacy:
        return ReplaySelection("legacy_hit" if latest.committed else "uncommitted", latest)
    if latest.call_id != call_id or latest.input_digest != input_digest:
        raise ReplayDiverged(
            f"Call {call_id} input differs from cached {latest.call_id or '<missing>'}"
        )
    return ReplaySelection("hit" if latest.committed else "uncommitted", latest)
