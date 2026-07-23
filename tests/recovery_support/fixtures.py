from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class InterventionFactory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _write_atomic(self, path: Path, value: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(dir=self.root, prefix=f".{path.stem}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def create(
        self,
        request_id: str,
        *,
        key: str = "approve",
        prompt: str = "Approve?",
        schema: dict[str, Any] | None = None,
        status: str = "pending",
        response: Any = None,
        resume_mode: str = "replay",
        call_id: str | None = None,
        session_id: str | None = None,
    ) -> Path:
        value: dict[str, Any] = {
            "request_id": request_id,
            "key": key,
            "prompt": prompt,
            "schema": schema,
            "call_id": call_id,
            "session_id": session_id,
            "resume_mode": resume_mode,
            "status": status,
            "created_at": "2026-07-22T08:00:00Z",
            "answered_at": "2026-07-22T08:01:00Z" if status == "answered" else None,
        }
        if status == "answered":
            value["response"] = response
        path = self.root / f"{request_id}.json"
        self._write_atomic(path, value)
        return path

    def answer(self, request_id: str, response: Any) -> Path:
        path = self.root / f"{request_id}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("status") != "pending":
            raise RuntimeError("intervention already answered")
        value["status"] = "answered"
        value["response"] = response
        value["answered_at"] = "2026-07-22T08:01:00Z"
        self._write_atomic(path, value)
        return path


class WorkflowFactory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, body: str) -> Path:
        path = self.root / f"{name}.py"
        path.write_text(body.rstrip() + "\n", encoding="utf-8")
        return path

    def sequential(self, prompts: tuple[str, ...] = ("one", "two")) -> Path:
        calls = "\n".join(f"    agent({prompt!r})" for prompt in prompts)
        return self.write("sequential", f"def run(agent, **kwargs):\n{calls}")

    def early_return(self) -> Path:
        return self.write(
            "early_return",
            "def run(agent, args, **kwargs):\n"
            "    if args.get('stop'):\n"
            "        return\n"
            "    agent('target')",
        )

    def parallel(self) -> Path:
        return self.write(
            "parallel",
            "def run(parallel, **kwargs):\n"
            "    return parallel(['branch-0', 'branch-1', 'branch-2'])",
        )

    def state_loop(self) -> Path:
        return self.write(
            "state_loop",
            "meta = {'state': {'attempt': 0}}\n"
            "def run(agent, state, **kwargs):\n"
            "    while state['attempt'] < 2:\n"
            "        agent(f\"attempt-{state['attempt']}\")\n"
            "        state['attempt'] += 1",
        )

    def digest_path(self, prompt: str) -> Path:
        return self.write(
            f"digest_{stable_name(prompt)}",
            f"def run(agent, **kwargs):\n    return agent({prompt!r})",
        )

    def intervention(self) -> Path:
        return self.write(
            "intervention",
            "def run(intervene, **kwargs):\n"
            "    return intervene(key='approve', prompt='Approve?', "
            "schema={'type': 'boolean'})",
        )


def stable_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def recovery_boundary_metadata(
    *,
    status: str = "cancelled",
    cancel_point: str = "worker_running",
    active_call_id: str | None = "0002",
    active_worker_atomic: bool = False,
    can_recover_continue: bool = False,
) -> dict[str, Any]:
    return {
        "run_id": "run-cancelled",
        "loop": "hello",
        "status": status,
        "args": {},
        "created": "2026-07-22T08:00:00Z",
        "started_at": "2026-07-22T08:00:00Z",
        "finished_at": "2026-07-22T08:01:00Z",
        "execution_epoch": 2,
        "cancel_point": cancel_point,
        "active_call_id": active_call_id,
        "active_worker_atomic": active_worker_atomic,
        "can_recover_continue": can_recover_continue,
    }
