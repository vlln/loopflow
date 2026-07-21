"""Persisted Run event envelopes and Web read projections."""

from __future__ import annotations

import json
import os
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_locks_guard = threading.Lock()
_locks: dict[Path, threading.Lock] = {}


def _lock_for(path: Path) -> threading.Lock:
    resolved = path.resolve()
    with _locks_guard:
        return _locks.setdefault(resolved, threading.Lock())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventWriter:
    def append(
        self,
        run_dir: Path,
        event_type: str,
        *,
        run_id: str,
        phase: str | None = None,
        phase_id: str | None = None,
        call_id: str | None = None,
        payload: dict[str, Any] | None = None,
        ts: str | None = None,
    ) -> dict[str, Any]:
        path = run_dir / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock_for(path):
            event_id = self.max_event_id(path) + 1
            event: dict[str, Any] = {
                "version": 2,
                "event_id": event_id,
                "type": event_type,
                "ts": ts or utc_now(),
                "run_id": run_id,
                "payload": payload or {},
            }
            if phase is not None:
                event["phase"] = phase
            if phase_id is not None:
                event["phase_id"] = phase_id
            if call_id is not None:
                event["call_id"] = call_id
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            return event

    @staticmethod
    def max_event_id(path: Path) -> int:
        maximum = 0
        for event in read_complete_jsonl(path):
            if event.get("version") == 2 and isinstance(event.get("event_id"), int):
                maximum = max(maximum, event["event_id"])
        return maximum


def read_complete_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        content = path.read_bytes()
    except OSError:
        raise
    if content and not content.endswith(b"\n"):
        content = content.rsplit(b"\n", 1)[0] + (b"\n" if b"\n" in content else b"")
    events: list[dict[str, Any]] = []
    for line in content.splitlines():
        if not line:
            continue
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            events.append({"_malformed_line": line.decode("utf-8", errors="replace")})
            continue
        events.append(value if isinstance(value, dict) else {"_malformed_value": value})
    return events


def is_valid_v2(event: dict[str, Any]) -> bool:
    required = {"version", "event_id", "type", "ts", "run_id", "payload"}
    if event.get("version") != 2 or not required.issubset(event):
        return False
    if not isinstance(event["event_id"], int) or event["event_id"] < 1:
        return False
    if not isinstance(event["payload"], dict):
        return False
    event_type = event.get("type", "")
    if event_type == "phase" and not all(event.get(key) for key in ("phase", "phase_id")):
        return False
    if event_type.startswith("agent_") or event_type in {
        "tool_call", "tool_call_update", "usage_update", "message", "retry"
    }:
        if not all(event.get(key) for key in ("phase", "phase_id", "call_id")):
            return False
    return True


@dataclass
class EventProjection:
    graph: dict[str, Any] = field(default_factory=lambda: {"nodes": [], "edges": [], "current_phase_id": None})
    occurrences: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    unattributed: list[dict[str, Any]] = field(default_factory=list)
    malformed: list[dict[str, Any]] = field(default_factory=list)
    legacy: bool = False


def project_events(path: Path) -> EventProjection:
    projection = EventProjection()
    raw = read_complete_jsonl(path)
    projection.events = raw
    phase_order: list[tuple[str, str]] = []
    occurrence_by_id: dict[str, dict[str, Any]] = {}
    calls: dict[str, dict[str, Any]] = {}
    node_counts: Counter[str] = Counter()
    edge_counts: Counter[tuple[str, str]] = Counter()
    seen_phases: set[str] = set()
    backedges: set[tuple[str, str]] = set()
    previous_phase: str | None = None

    for event in raw:
        if event.get("version") == 2:
            if not is_valid_v2(event):
                projection.malformed.append(event)
                continue
            event_type = event["type"]
            phase = event.get("phase")
            phase_id = event.get("phase_id")
            call_id = event.get("call_id")
            if event_type == "phase":
                occurrence = {
                    "phase_id": phase_id,
                    "phase": phase,
                    "occurrence": event["payload"].get("occurrence", node_counts[phase] + 1),
                    "started_at": event.get("ts"),
                    "ended_at": None,
                    "call_ids": [],
                }
                if phase_order and phase_order[-1][1] in occurrence_by_id:
                    occurrence_by_id[phase_order[-1][1]]["ended_at"] = event.get("ts")
                occurrence_by_id[phase_id] = occurrence
                projection.occurrences.append(occurrence)
                phase_order.append((phase, phase_id))
                node_counts[phase] += 1
                if previous_phase is not None:
                    edge = (previous_phase, phase)
                    edge_counts[edge] += 1
                    if phase in seen_phases:
                        backedges.add(edge)
                seen_phases.add(phase)
                previous_phase = phase
            elif call_id:
                call = calls.setdefault(
                    call_id,
                    {
                        "call_id": call_id,
                        "phase_id": phase_id,
                        "session": None,
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "exit_code": None,
                        "backend": None,
                        "model": None,
                        "events": [],
                    },
                )
                call["events"].append(event)
                payload = event["payload"]
                for key in ("session", "backend", "model"):
                    if payload.get(key) is not None:
                        call[key] = payload[key]
                if event_type == "agent_start":
                    call["status"] = "running"
                    call["started_at"] = event.get("ts")
                elif event_type == "agent_done":
                    call["exit_code"] = payload.get("exit_code")
                    call["status"] = "done" if payload.get("exit_code") == 0 else "failed"
                    call["finished_at"] = event.get("ts")
                elif event_type == "retry":
                    call["status"] = "retrying"
                if phase_id in occurrence_by_id and call_id not in occurrence_by_id[phase_id]["call_ids"]:
                    occurrence_by_id[phase_id]["call_ids"].append(call_id)
        else:
            projection.legacy = True
            if event.get("type") == "phase" and event.get("title"):
                phase = event["title"]
                phase_id = event.get("phase_id") or f"legacy-phase-{len(phase_order) + 1}"
                occurrence = {
                    "phase_id": phase_id,
                    "phase": phase,
                    "occurrence": node_counts[phase] + 1,
                    "started_at": None,
                    "ended_at": None,
                    "call_ids": [],
                }
                occurrence_by_id[phase_id] = occurrence
                projection.occurrences.append(occurrence)
                phase_order.append((phase, phase_id))
                node_counts[phase] += 1
                if previous_phase is not None:
                    edge_counts[(previous_phase, phase)] += 1
                previous_phase = phase
            elif event.get("phase_id") and event.get("call_id"):
                call_id = str(event["call_id"])
                phase_id = str(event["phase_id"])
                call = calls.setdefault(
                    call_id,
                    {
                        "call_id": call_id,
                        "phase_id": phase_id,
                        "session": event.get("session"),
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "exit_code": None,
                        "backend": None,
                        "model": None,
                        "events": [],
                    },
                )
                call["events"].append(event)
            elif event.get("type") != "phase":
                projection.unattributed.append(event)

    projection.calls = list(calls.values())
    current_phase_id = phase_order[-1][1] if phase_order else None
    projection.graph = {
        "nodes": [
            {"phase": phase, "occurrence_count": count, "is_current": phase_order[-1][0] == phase}
            for phase, count in node_counts.items()
        ],
        "edges": [
            {
                "from": source,
                "to": target,
                "count": count,
                "is_backedge": (source, target) in backedges,
            }
            for (source, target), count in edge_counts.items()
        ],
        "current_phase_id": current_phase_id,
    }
    return projection


def replay_v2(path: Path, last_event_id: int) -> tuple[list[dict[str, Any]], int]:
    projection = project_events(path)
    if projection.legacy:
        raise ValueError("legacy_events_not_streamable")
    valid = [event for event in projection.events if event.get("version") == 2 and is_valid_v2(event)]
    maximum = max((event["event_id"] for event in valid), default=0)
    if last_event_id > maximum:
        raise IndexError(maximum)
    return [event for event in valid if event["event_id"] > last_event_id], maximum
