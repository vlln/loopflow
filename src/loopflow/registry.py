"""Registry — agent session metadata persistence.

Stores session data in .agents/subagents/agents.json (compatible with
subagent-skills format). loopflow uses only the core functions: register,
complete, add_task, get_session_id, get_session_status, find_agent_for_session,
list_agents, list_sessions, get_all_data, get_session_data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _get_registry_path() -> Path:
    agents_dir = os.environ.get("SUBAGENT_AGENTS_DIR", ".agents/subagent")
    return Path(agents_dir) / "agents.json"


def _read() -> dict:
    path = _get_registry_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text()) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    path = _get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def register(agent: str, session: str, session_id: str, cwd: str | None = None, background: bool = False) -> None:
    data = _read()
    data.setdefault(agent, {}).setdefault("sessions", {})
    data[agent]["sessions"][session] = {
        "session_id": session_id,
        "status": "running",
        "created": datetime.now(timezone.utc).isoformat(),
        "tasks": [],
        "mode": "background" if background else "foreground",
        "queue": [],
        "current_task": None,
    }
    if cwd:
        data[agent]["sessions"][session]["cwd"] = cwd
    _write(data)


def complete(agent: str, session: str) -> None:
    data = _read()
    try:
        data[agent]["sessions"][session]["status"] = "done"
        _write(data)
    except KeyError:
        pass


def add_task(agent: str, session: str, prompt: str, status: str) -> None:
    data = _read()
    try:
        data[agent]["sessions"][session]["tasks"].append({
            "prompt": prompt,
            "status": status,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        _write(data)
    except KeyError:
        pass


def get_session_id(agent: str, session: str) -> str | None:
    data = _read()
    try:
        return data[agent]["sessions"][session]["session_id"]
    except KeyError:
        return None


def get_session_id_from_any(session: str) -> str | None:
    data = _read()
    for agent_name, agent_data in data.items():
        for session_name, session_data in agent_data.get("sessions", {}).items():
            if session_name == session:
                return session_data.get("session_id")
    return None


def get_session_status(agent: str, session: str) -> str:
    data = _read()
    try:
        return data[agent]["sessions"][session].get("status", "unknown")
    except KeyError:
        return "unknown"


def find_agent_for_session(session: str) -> str | None:
    data = _read()
    for agent_name, agent_data in data.items():
        if session in agent_data.get("sessions", {}):
            return agent_name
    return None


def list_agents() -> list[str]:
    data = _read()
    return list(data.keys())


def list_sessions(agent: str) -> list[str]:
    data = _read()
    try:
        return list(data[agent].get("sessions", {}).keys())
    except KeyError:
        return []


def get_all_data() -> dict:
    return _read()


def get_session_data(agent: str, session: str) -> dict | None:
    data = _read()
    try:
        return data[agent]["sessions"][session]
    except KeyError:
        return None