"""Persisted Run event envelopes and Web read projections."""

from __future__ import annotations

import json
import os
import threading
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


def _needs_call_id(event: dict[str, Any]) -> bool:
    event_type = event.get("type", "")
    return event_type.startswith("agent_") or event_type in {
        "tool_call", "tool_call_update", "usage_update", "message", "retry"
    }


def is_valid_v2(event: dict[str, Any]) -> bool:
    required = {"version", "event_id", "type", "ts", "run_id", "payload"}
    if event.get("version") != 2 or not required.issubset(event):
        return False
    if not isinstance(event["event_id"], int) or event["event_id"] < 1:
        return False
    if not isinstance(event["payload"], dict):
        return False
    event_type = event.get("type", "")
    if event_type.startswith("agent_") or event_type in {
        "tool_call", "tool_call_update", "usage_update", "message", "retry"
    }:
        if not event.get("call_id"):
            return False
    return True


@dataclass
class EventProjection:
    agent_graph: dict[str, Any] = field(default_factory=lambda: {"nodes": [], "edges": [], "current": None})
    calls: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    unattributed: list[dict[str, Any]] = field(default_factory=list)
    malformed: list[dict[str, Any]] = field(default_factory=list)
    legacy: bool = False


def _dedup_events(raw: list[dict]) -> list[dict]:
    """Remove duplicate agent_session events (same call_id + session_id), keep last (BL-035)."""
    last_idx: dict[tuple[str, str], int] = {}
    for i, event in enumerate(raw):
        if event.get("version") == 2 and event.get("type") == "agent_session":
            payload = event.get("payload", {})
            key = (event.get("call_id", ""), payload.get("session_id", ""))
            last_idx[key] = i
    return [
        event for i, event in enumerate(raw)
        if event.get("version") != 2 or event.get("type") != "agent_session"
        or last_idx.get((
            event.get("call_id", ""),
            event.get("payload", {}).get("session_id", ""),
        )) == i
    ]


def project_events(path: Path) -> EventProjection:
    projection = EventProjection()
    raw = read_complete_jsonl(path)
    projection.events = _dedup_events(raw)
    calls: dict[str, dict[str, Any]] = {}
    agent_nodes: list[dict[str, Any]] = []
    agent_edges: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    previous_call_id: str | None = None
    fork_active: bool = False            # inside a fork (between fork_start and fork_end)
    fork_parent: str | None = None       # call_id of the agent before fork (fan-out source)
    fork_children: list[str] = []        # call_ids of parallel agents
    pending_join: list[str] = []         # fork children waiting for join edges
    join_sources: list[str] = []         # back-to-back join sources, emitted per-child in agent_start

    for event in projection.events:
        if event.get("version") == 2:
            if not is_valid_v2(event):
                reason = "missing_call_id" if _needs_call_id(event) and not event.get("call_id") else "invalid_event"
                projection.malformed.append({"reason": reason, "raw": event})
                continue
            event_type = event["type"]
            call_id = event.get("call_id")
            if event_type == "fork_start":
                fork_active = True
                fork_children = []
                # Back-to-back fork: pending_join from previous fork becomes
                # the join source for this fork's children (no fork_parent).
                # Normal fork: fork_parent is the preceding agent.
                fork_parent = previous_call_id if not pending_join else None
                join_sources = list(pending_join)
                pending_join = []
                continue
            if event_type == "fork_end":
                # Emit fork edges (fan-out from parent to children)
                if fork_parent is not None:
                    for child_id in fork_children:
                        agent_edges.append({
                            "from": fork_parent,
                            "to": child_id,
                            "kind": "fork",
                        })
                # Back-to-back join edges are emitted in agent_start (join_sources)
                # so they appear immediately during live run, before fork_end.
                # Children become pending_join for the next agent or fork
                if fork_children:
                    pending_join = list(fork_children)
                fork_active = False
                fork_parent = None
                fork_children = []
                join_sources = []
                continue
            if call_id:
                call = calls.setdefault(
                    call_id,
                    {
                        "call_id": call_id,
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
                    if call_id not in seen_call_ids:
                        seen_call_ids.add(call_id)
                        label = payload.get("label") or call_id
                        agent_def = payload.get("agent_def")
                        agent_nodes.append({
                            "id": call_id,
                            "label": label,
                            "agent_def": agent_def,
                            "status": "running",
                        })
                        # Graph edge logic
                        if fork_active:
                            # Inside a fork: track as child and emit join edges
                            # from back-to-back fork sources immediately (not
                            # deferred to fork_end) so live-run graphs are correct.
                            fork_children.append(call_id)
                            for join_source in join_sources:
                                if join_source != call_id:
                                    agent_edges.append({
                                        "from": join_source,
                                        "to": call_id,
                                        "kind": "join",
                                    })
                        elif pending_join:
                            # Fan-in: join edges from fork children to this agent
                            for child_id in pending_join:
                                if child_id != call_id:
                                    agent_edges.append({
                                        "from": child_id,
                                        "to": call_id,
                                        "kind": "join",
                                    })
                            pending_join = []
                        elif previous_call_id is not None:
                            agent_edges.append({
                                "from": previous_call_id,
                                "to": call_id,
                                "kind": "sequential",
                            })
                        previous_call_id = call_id
                elif event_type == "agent_done":
                    call["exit_code"] = payload.get("exit_code")
                    call["status"] = "done" if payload.get("exit_code") == 0 else "failed"
                    call["finished_at"] = event.get("ts")
                    for node in agent_nodes:
                        if node["id"] == call_id:
                            node["status"] = call["status"]
                elif event_type == "retry":
                    call["status"] = "retrying"
        else:
            projection.legacy = True
            if event.get("type") == "agent_start" and event.get("call_id"):
                call_id = str(event["call_id"])
                call = calls.setdefault(
                    call_id,
                    {
                        "call_id": call_id,
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
            elif event.get("type") != "agent_start" and event.get("call_id"):
                call_id = str(event["call_id"])
                if call_id in calls:
                    calls[call_id]["events"].append(event)
            elif event.get("type") != "phase":
                projection.unattributed.append(event)

    projection.calls = list(calls.values())
    projection.agent_graph = {
        "nodes": agent_nodes,
        "edges": agent_edges,
        "current": previous_call_id,
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


def replay_file_changes(path: Path, last_seq: int) -> tuple[list[dict[str, Any]], int]:
    """Replay file_changes.jsonl records with seq > last_seq.

    Returns (pending_records, max_seq). If the file does not exist,
    returns ([], 0) — the topic is silently empty, not an error.
    Raises IndexError(max_seq) if last_seq > max_seq.
    """
    if not path.is_file():
        return [], 0
    records = read_complete_jsonl(path)
    valid = [
        rec for rec in records
        if isinstance(rec, dict) and isinstance(rec.get("seq"), int) and rec["seq"] >= 1
    ]
    maximum = max((rec["seq"] for rec in valid), default=0)
    if last_seq > maximum:
        raise IndexError(maximum)
    return [rec for rec in valid if rec["seq"] > last_seq], maximum
