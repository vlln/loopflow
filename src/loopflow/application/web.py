"""HTTP-independent application services used by CLI and Web presentation."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
from loopflow.infrastructure.web_storage import RunRepository, now_iso, read_json


class ApplicationError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class RunExecutor(Protocol):
    def start(self, loop: str, args: dict[str, Any], options: dict[str, Any], run_id: str | None = None) -> str: ...


@dataclass
class WebApplication:
    runs: RunRepository
    loops: LoopRepository
    queue: QueueRepository
    backends: BackendRepository
    executor: RunExecutor | None = None
    allowed_backends: set[str] = field(default_factory=set)

    def list_runs(self, *, statuses: list[str] | None = None, loop: str | None = None, q: str | None = None, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        limit, offset = _page(limit, cursor)
        valid_statuses = {"running", "done", "failed", "stopped", "stale", "unreadable"}
        if statuses and not set(statuses) <= valid_statuses:
            raise ApplicationError("validation_failed", "Unknown Run status")
        items = [self.runs.read_summary(path) for path in self.runs.list_dirs()]
        if statuses:
            items = [item for item in items if item["status"] in statuses]
        if loop:
            items = [item for item in items if item["loop"] == loop]
        if q:
            needle = q.casefold()
            items = [item for item in items if needle in item["run_id"].casefold() or needle in str(item["loop"] or "").casefold()]
        items.sort(key=lambda item: (item.get("created") or "", item["run_id"]), reverse=True)
        return _slice(items, offset, limit)

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.runs.read_detail(self._run_dir(run_id))

    def create_run(self, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, {"loop", "args", "backend", "model", "mock", "from_phase", "only_phase"})
        loop = body.get("loop")
        if not isinstance(loop, str) or not loop:
            raise ApplicationError("validation_failed", "loop must be a non-empty string")
        if self.loops.find(loop) is None:
            raise ApplicationError("loop_not_found", f"Loop '{loop}' was not found")
        args = body.get("args", {})
        if not isinstance(args, dict):
            raise ApplicationError("validation_failed", "args must be an object")
        options = self._execution_options(body)
        only_phase, from_phase = options.get("only_phase"), options.get("from_phase")
        if only_phase is not None and from_phase not in (None, only_phase):
            raise ApplicationError("validation_failed", "only_phase conflicts with from_phase")
        if only_phase is not None:
            options["from_phase"] = only_phase
        if self.executor is None:
            raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
        run_id = self.executor.start(loop, args, options)
        return self.runs.read_summary(self._run_dir(run_id))

    def stop_run(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        metadata = read_json(run_dir / "run.json")
        if self.runs.read_summary(run_dir)["status"] != "running":
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be stopped")
        pid = metadata.get("pid")
        if not isinstance(pid, int) or not self.runs.process_probe.terminate(pid):
            raise ApplicationError("process_gone", f"Run '{run_id}' process is unavailable")
        finished = now_iso()
        metadata.update({"status": "stopped", "finished_at": finished})
        metadata.pop("pid", None)
        metadata.pop("process_started_at", None)
        self.runs.write_metadata(run_dir, metadata)
        return self.runs.read_summary(run_dir)

    def resume_run(self, run_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        metadata = read_json(run_dir / "run.json")
        if self.runs.read_summary(run_dir)["status"] not in {"failed", "stopped"}:
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be resumed")
        options = self._execution_options(body or {}, resume=True)
        if self.executor is None:
            raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
        returned = self.executor.start(metadata["loop"], metadata.get("args", {}), {**options, "resume": True}, run_id=run_id)
        if returned != run_id:
            raise ApplicationError("internal_error", "Executor changed run_id during resume")
        return self.runs.read_summary(run_dir)

    def rerun(self, run_id: str) -> dict[str, Any]:
        source = self._run_dir(run_id)
        metadata = read_json(source / "run.json")
        if self.runs.read_summary(source)["status"] == "running":
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be rerun")
        if self.executor is None:
            raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
        new_id = self.executor.start(metadata["loop"], metadata.get("args", {}), {})
        return self.runs.read_summary(self._run_dir(new_id))

    def reconcile(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        if self.runs.read_summary(run_dir)["status"] != "stale":
            raise ApplicationError("run_not_stale", f"Run '{run_id}' is not stale")
        try:
            return self.runs.reconcile(run_dir)
        except RuntimeError as error:
            raise ApplicationError("process_alive", f"Run '{run_id}' process is alive") from error

    def list_loops(self, *, q: str | None = None, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        limit, offset = _page(limit, cursor)
        items = self.loops.list()
        if q:
            needle = q.casefold()
            items = [item for item in items if needle in item["name"].casefold() or needle in item["description"].casefold()]
        return _slice(items, offset, limit)

    def get_loop(self, name: str) -> dict[str, Any]:
        loop_dir = self.loops.find(name)
        if loop_dir is None:
            raise ApplicationError("loop_not_found", f"Loop '{name}' was not found")
        return self.loops.detail(loop_dir)

    def preview_loop_file(self, name: str, relative: str) -> dict[str, Any]:
        loop_dir = self.loops.find(name)
        if loop_dir is None:
            raise ApplicationError("loop_not_found", f"Loop '{name}' was not found")
        return self.loops.preview(loop_dir, relative)

    def list_queue(self, *, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        limit, offset = _page(limit, cursor)
        return _slice(self.queue.list(), offset, limit)

    def enqueue(self, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, {"loop", "args", "resources", "priority"})
        loop = body.get("loop")
        if not isinstance(loop, str) or not loop:
            raise ApplicationError("validation_failed", "loop must be a non-empty string")
        if self.loops.find(loop) is None:
            raise ApplicationError("loop_not_found", f"Loop '{loop}' was not found")
        args, resources, priority = body.get("args", {}), body.get("resources", {}), body.get("priority", 5)
        if not isinstance(args, dict) or not isinstance(resources, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in resources.items()):
            raise ApplicationError("validation_failed", "args/resources are invalid")
        if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
            raise ApplicationError("validation_failed", "priority must be 0..100")
        return self.queue.enqueue(loop, args, resources, priority)

    def _run_dir(self, run_id: str) -> Path:
        path = self.runs.find(run_id)
        if path is None:
            raise ApplicationError("run_not_found", f"Run '{run_id}' was not found")
        return path

    def _execution_options(self, body: dict[str, Any], resume: bool = False) -> dict[str, Any]:
        allowed = {"backend", "model", "mock"} if resume else {"backend", "model", "mock", "from_phase", "only_phase", "loop", "args"}
        _fields(body, allowed)
        backend = body.get("backend")
        if backend is not None and (not isinstance(backend, str) or self.allowed_backends and backend not in self.allowed_backends):
            raise ApplicationError("validation_failed", "backend is unknown")
        model = body.get("model")
        if model is not None and (not isinstance(model, str) or not model):
            raise ApplicationError("validation_failed", "model must be non-empty or null")
        mock = body.get("mock")
        if mock not in (None, "bash", "auto"):
            raise ApplicationError("validation_failed", "mock must be bash, auto, or null")
        for key in ("from_phase", "only_phase"):
            if key in body and body[key] is not None and (not isinstance(body[key], str) or not body[key]):
                raise ApplicationError("validation_failed", f"{key} must be non-empty or null")
        return {key: body.get(key) for key in ("backend", "model", "mock", "from_phase", "only_phase") if key in body}


def _fields(body: dict[str, Any], allowed: set[str]) -> None:
    if not isinstance(body, dict):
        raise ApplicationError("validation_failed", "request must be an object")
    unknown = set(body) - allowed
    if unknown:
        raise ApplicationError("validation_failed", "Unknown fields", {"fields": sorted(unknown)})


def _page(limit: int, cursor: str | None) -> tuple[int, int]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ApplicationError("validation_failed", "limit must be 1..200")
    if cursor is None:
        return limit, 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii") + b"===").decode("ascii")
        offset = int(raw)
    except (ValueError, UnicodeError) as error:
        raise ApplicationError("validation_failed", "cursor is invalid") from error
    if offset < 0:
        raise ApplicationError("validation_failed", "cursor is invalid")
    return limit, offset


def _slice(items: list[dict[str, Any]], offset: int, limit: int) -> dict[str, Any]:
    end = offset + limit
    cursor = base64.urlsafe_b64encode(str(end).encode("ascii")).decode("ascii").rstrip("=") if end < len(items) else None
    return {"items": items[offset:end], "next_cursor": cursor}
