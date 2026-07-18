from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FIXED_TIME = "2026-07-18T22:00:00Z"


@dataclass
class WebFixtureFactory:
    root: Path
    runs: Path = field(init=False)
    loops: Path = field(init=False)

    def __post_init__(self) -> None:
        self.runs = self.root / "runs"
        self.loops = self.root / "loops"
        self.runs.mkdir(parents=True)
        self.loops.mkdir(parents=True)

    def create_run(
        self,
        run_id: str,
        *,
        status: str = "done",
        loop: str = "hello",
        args: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
        pid: int | None = None,
        process_started_at: str | None = None,
    ) -> Path:
        run_dir = self.runs / run_id
        run_dir.mkdir()
        metadata = {
            "run_id": run_id,
            "loop": loop,
            "status": status,
            "args": args or {},
            "created": FIXED_TIME,
            "started_at": FIXED_TIME,
            "finished_at": FIXED_TIME if status != "running" else None,
            "updated_at": FIXED_TIME,
            "pid": pid,
            "process_started_at": process_started_at,
        }
        self.write_json(run_dir / "run.json", metadata)
        if state is not None:
            self.write_json(run_dir / "state.json", state)
        return run_dir

    def create_unreadable_run(self, run_id: str) -> Path:
        run_dir = self.runs / run_id
        run_dir.mkdir()
        (run_dir / "run.json").write_text('{"run_id":', encoding="utf-8")
        return run_dir

    def append_v2_event(
        self,
        run_dir: Path,
        event_id: int,
        event_type: str,
        *,
        phase: str | None = None,
        phase_id: str | None = None,
        call_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "version": 2,
            "event_id": event_id,
            "type": event_type,
            "ts": FIXED_TIME,
            "run_id": run_dir.name,
            "payload": payload or {},
        }
        for name, value in (("phase", phase), ("phase_id", phase_id), ("call_id", call_id)):
            if value is not None:
                event[name] = value
        self.append_jsonl(run_dir / "events.jsonl", event)
        return event

    def append_legacy_event(self, run_dir: Path, event: dict[str, Any]) -> None:
        self.append_jsonl(run_dir / "events.jsonl", event)

    def append_malformed_line(self, run_dir: Path, content: str = '{"partial":') -> None:
        with (run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(content)

    def create_loop(self, name: str, *, description: str = "Fixture loop") -> Path:
        loop_dir = self.loops / name
        (loop_dir / "agents").mkdir(parents=True)
        (loop_dir / "loop.md").write_text(
            f"---\ndescription: {description}\n---\n\n# {name}\n",
            encoding="utf-8",
        )
        (loop_dir / "workflow.py").write_text("def run():\n    return None\n", encoding="utf-8")
        return loop_dir

    @staticmethod
    def create_symlink_escape(loop_dir: Path, outside: Path) -> Path:
        link = loop_dir / "outside-link"
        os.symlink(outside, link)
        return link

    def create_performance_runs(self, count: int = 1000, event_count: int = 1000) -> Path:
        selected: Path | None = None
        for index in range(count):
            selected = self.create_run(f"perf-{index:04d}")
        assert selected is not None
        payload = {"message": "x" * 900}
        for event_id in range(1, event_count + 1):
            self.append_v2_event(selected, event_id, "message", payload=payload)
        return selected

    @staticmethod
    def write_json(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    @staticmethod
    def append_jsonl(path: Path, value: Any) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")


class BackendManagerStub:
    def __init__(self, backends: list[dict[str, Any]] | None = None) -> None:
        self.backends = backends or []
        self.diagnostics: dict[str, dict[str, Any] | Exception] = {}
        self.calls: list[tuple[str, int]] = []

    def list_backends(self) -> list[dict[str, Any]]:
        return list(self.backends)

    def set_diagnostic(self, name: str, result: dict[str, Any] | Exception) -> None:
        self.diagnostics[name] = result

    def diagnose(self, name: str, timeout_ms: int) -> dict[str, Any]:
        self.calls.append((name, timeout_ms))
        result = self.diagnostics[name]
        if isinstance(result, Exception):
            raise result
        return dict(result)


@dataclass(frozen=True)
class ProcessProbeStub:
    identities: dict[int, str]

    def started_at(self, pid: int) -> str | None:
        return self.identities.get(pid)


@dataclass(frozen=True)
class ClockStub:
    now_value: str = FIXED_TIME

    def now(self) -> str:
        return self.now_value
