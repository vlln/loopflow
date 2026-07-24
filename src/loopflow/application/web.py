"""HTTP-independent application services used by CLI and Web presentation."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from loopflow import __version__
from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
from loopflow.infrastructure.web_events import project_events, replay_file_changes, replay_v2
from loopflow.infrastructure.intervention import (
    InterventionAlreadyAnswered,
    InterventionNotFound,
    InterventionValidationError,
    answer_requests,
    list_requests,
    read_request,
)
from loopflow.infrastructure.web_storage import RunRepository, atomic_write_json, now_iso, read_json


class ApplicationError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class RunExecutor(Protocol):
    def start(
        self,
        loop: str,
        args: dict[str, Any],
        options: dict[str, Any],
        run_id: str | None = None,
        working_directory: str | Path | None = None,
    ) -> str: ...


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
        valid_statuses = {
            "running",
            "waiting_input",
            "cancelling",
            "cancelled",
            "done",
            "failed",
            "stopped",
            "stale",
            "unreadable",
        }
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
        _fields(body, {"loop", "args", "backend", "model", "mock", "from_phase", "only_phase", "working_directory"})
        loop = body.get("loop")
        if not isinstance(loop, str) or not loop:
            raise ApplicationError("validation_failed", "loop must be a non-empty string")
        if self.loops.find(loop) is None:
            raise ApplicationError("loop_not_found", f"Loop '{loop}' was not found")
        args = body.get("args", {})
        if not isinstance(args, dict):
            raise ApplicationError("validation_failed", "args must be an object")
        working_directory = body.get("working_directory")
        if working_directory is not None:
            if not isinstance(working_directory, str) or not working_directory:
                raise ApplicationError("validation_failed", "working_directory must be a non-empty string or null")
            candidate = Path(working_directory)
            if not candidate.is_absolute():
                raise ApplicationError(
                    "validation_failed",
                    "working_directory must be an absolute path",
                    {"reason": "not_absolute"},
                )
            if not candidate.exists():
                raise ApplicationError(
                    "validation_failed",
                    "working_directory does not exist",
                    {"reason": "not_found"},
                )
            if not candidate.is_dir():
                raise ApplicationError(
                    "validation_failed",
                    "working_directory is not a directory",
                    {"reason": "not_a_directory"},
                )
        options = self._execution_options(body)
        only_phase, from_phase = options.get("only_phase"), options.get("from_phase")
        if only_phase is not None and from_phase not in (None, only_phase):
            raise ApplicationError("validation_failed", "only_phase conflicts with from_phase")
        if only_phase is not None:
            options["from_phase"] = only_phase
        if self.executor is None:
            raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
        run_id = self.executor.start(loop, args, options, working_directory=working_directory)
        return self.runs.read_summary(self._run_dir(run_id))

    def stop_run(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        metadata = read_json(run_dir / "run.json")
        status = self.runs.read_summary(run_dir)["status"]
        if status not in {"running", "waiting_input"}:
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be stopped")
        if status == "waiting_input":
            metadata.update({
                "status": "cancelled",
                "finished_at": now_iso(),
                "stop_summary": "waiting_input_cancelled",
                "cancel_point": "no_worker_running",
            })
            self._clear_worker_identity(metadata)
            self._write_metadata(run_dir, metadata)
            return self.runs.read_summary(run_dir)

        identity = self._worker_identity(metadata)
        metadata.update({"status": "cancelling", "stop_requested_at": now_iso()})
        self._write_metadata(run_dir, metadata)
        stop_summary = "process_gone"
        if identity is not None and self._identity_matches(identity):
            stop_summary = self.runs.process_probe.terminate_group(identity["process_group_id"])
        finished = now_iso()
        current = read_json(run_dir / "run.json")
        if current.get("execution_epoch") != metadata.get("execution_epoch") or current.get("status") not in {"cancelling", "cancelled"}:
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be stopped")
        current.update({
            "status": "cancelled",
            "finished_at": finished,
            "error_summary": None,
            "stop_summary": stop_summary,
            "cancel_point": "worker_running",
        })
        if current.get("active_call_id") is None and current.get("failed_call_id") is not None:
            current["active_call_id"] = current["failed_call_id"]
        self._clear_worker_identity(current)
        self._write_metadata(run_dir, current)
        return self.runs.read_summary(run_dir)

    def recover_run(self, run_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        metadata = read_json(run_dir / "run.json")
        status = self.runs.read_summary(run_dir)["status"]
        if status not in {"failed", "cancelled"}:
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be recovered")
        body = body or {}
        _fields(body, {"mode"})
        mode = body.get("mode", "retry")
        if mode not in {"retry", "continue"}:
            raise ApplicationError("validation_failed", "mode must be retry or continue")
        if status == "cancelled" and not self._cancelled_has_recovery_boundary(run_dir, metadata):
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be recovered")
        if mode == "continue" and (
            not metadata.get("can_recover_continue") or metadata.get("active_worker_atomic")
        ):
            raise ApplicationError(
                "continue_not_supported",
                f"Run '{run_id}' has no durable failed session",
            )
        if self.executor is None:
            raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
        try:
            returned = self.executor.start(
                metadata["loop"],
                metadata.get("args", {}),
                {"recover": True, "recovery_mode": mode},
                run_id=run_id,
            )
        except RuntimeError as error:
            if str(error) in {
                "invalid_run_transition",
                "replay_diverged",
                "continue_not_supported",
            }:
                if str(error) == "replay_diverged":
                    raise ApplicationError("replay_diverged", f"Run '{run_id}' replay diverged") from error
                if str(error) == "continue_not_supported":
                    raise ApplicationError("continue_not_supported", f"Run '{run_id}' cannot continue its session") from error
                raise ApplicationError("invalid_run_transition", f"Run '{run_id}' already has a worker") from error
            raise
        if returned != run_id:
            raise ApplicationError("internal_error", "Executor changed run_id during recovery")
        return self.runs.read_summary(run_dir)

    def list_interventions(self, run_id: str) -> dict[str, Any]:
        return {"items": list_requests(self._run_dir(run_id))}

    def respond_intervention(self, run_id: str, request_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        _fields(body, {"response"})
        if "response" not in body:
            raise ApplicationError("validation_failed", "response is required")
        return self._respond_intervention_items(run_id, [{"request_id": request_id, "response": body["response"]}])

    def respond_interventions(self, run_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        _fields(body, {"responses"})
        responses = body.get("responses")
        if not isinstance(responses, list):
            raise ApplicationError("validation_failed", "responses must be an array")
        return self._respond_intervention_items(run_id, responses)

    def _respond_intervention_items(self, run_id: str, responses: list[dict[str, Any]]) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        try:
            existing = []
            seen: set[str] = set()
            if not responses:
                raise InterventionValidationError("responses must be a non-empty array")
            for item in responses:
                if not isinstance(item, dict):
                    raise InterventionValidationError("each response must be an object")
                request_id = item.get("request_id")
                if not isinstance(request_id, str) or not request_id:
                    raise InterventionValidationError("request_id is required")
                if request_id in seen:
                    raise InterventionValidationError("duplicate request_id")
                seen.add(request_id)
                existing.append(read_request(run_dir, request_id))
            for item in existing:
                if item.get("status") == "answered" or "response" in item:
                    raise InterventionAlreadyAnswered(str(item.get("request_id")))
            status = self.runs.read_summary(run_dir)["status"]
            if status not in {"waiting_input", "cancelled"}:
                raise ApplicationError("invalid_run_transition", f"Run '{run_id}' is not waiting for input")
            answered = answer_requests(run_dir, run_id, responses)
        except InterventionNotFound as error:
            raise ApplicationError("intervention_not_found", f"Intervention '{error}' was not found") from error
        except InterventionAlreadyAnswered as error:
            raise ApplicationError("intervention_already_answered", f"Intervention '{error}' was already answered") from error
        except InterventionValidationError as error:
            raise ApplicationError("validation_failed", str(error)) from error
        if self.executor is None:
            raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
        metadata = read_json(run_dir / "run.json")
        mode = "continue" if any(item.get("resume_mode") == "continue" for item in answered) else "retry"
        if mode == "continue":
            request = next(item for item in answered if item.get("resume_mode") == "continue")
            metadata["failed_call_id"] = request.get("call_id")
            metadata["failed_session_id"] = request.get("session_id")
            metadata["can_recover_continue"] = True
            self._write_metadata(run_dir, metadata)
        try:
            returned = self.executor.start(
                metadata["loop"],
                metadata.get("args", {}),
                {"recover": True, "recovery_mode": mode},
                run_id=run_id,
            )
        except RuntimeError as error:
            if str(error) == "replay_diverged":
                raise ApplicationError("replay_diverged", f"Run '{run_id}' replay diverged") from error
            if str(error) == "continue_not_supported":
                raise ApplicationError("continue_not_supported", f"Run '{run_id}' cannot continue its session") from error
            if str(error) == "invalid_run_transition":
                raise ApplicationError("invalid_run_transition", f"Run '{run_id}' already has a worker") from error
            raise
        if returned != run_id:
            raise ApplicationError("internal_error", "Executor changed run_id during intervention response")
        return self.runs.read_summary(run_dir)

    def resume_run(self, run_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Deprecated application alias retained for non-Web CLI callers."""
        return self.recover_run(run_id, {"mode": "retry"})

    def rerun(self, run_id: str) -> dict[str, Any]:
        source = self._run_dir(run_id)
        metadata = read_json(source / "run.json")
        if self.runs.read_summary(source)["status"] == "running":
            raise ApplicationError("invalid_run_transition", f"Run '{run_id}' cannot be rerun")
        if self.executor is None:
            raise ApplicationError("invalid_run_transition", "Run execution is unavailable")
        new_id = self.executor.start(
            metadata["loop"],
            metadata.get("args", {}),
            {},
            working_directory=metadata.get("working_directory"),
        )
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

    def preview_run_file(self, run_id: str, relative: str) -> dict[str, Any]:
        """Preview a single file inside a run's working directory (ADR-0042).

        Shares the Loop preview rules: relative POSIX path, resolved inside
        the run's working directory, UTF-8 text up to 1 MiB, read-only.
        """
        run_dir = self._run_dir(run_id)
        root = self.runs.resolve_working_directory(run_dir)
        if root is None:
            raise ApplicationError("file_not_found", f"File '{relative}' was not found")
        return self.loops.preview(root, relative)

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

    def list_backends(self) -> dict[str, Any]:
        return {"items": self.backends.list()}

    def system_meta(self) -> dict[str, Any]:
        """Server metadata for the WebUI: running loopflow version."""
        return {"version": __version__}

    def pick_directory(self) -> dict[str, Any]:
        """Launch the OS-native folder picker on the server machine (ADR-0042).

        macOS only: osascript `choose folder`. A user cancel (exit -128) or a
        timeout is reported as {"path": None, "cancelled": True}; other
        platforms and osascript invocation failures raise 501 not_supported.
        """
        if sys.platform != "darwin":
            raise ApplicationError("not_supported", "Directory picker is only supported on macOS")
        try:
            result = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select a working directory")'],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return {"path": None, "cancelled": True}
        except (OSError, subprocess.SubprocessError) as error:
            raise ApplicationError("not_supported", f"Directory picker is unavailable: {error}") from error
        if result.returncode != 0:
            return {"path": None, "cancelled": True}
        path = result.stdout.strip().rstrip("/") or "/"
        return {"path": path, "cancelled": False}

    def diagnose_backend(self, name: str, timeout_ms: int) -> dict[str, Any]:
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 100 <= timeout_ms <= 30000:
            raise ApplicationError("validation_failed", "timeout_ms must be 100..30000")
        try:
            return self.backends.diagnose(name, timeout_ms)
        except KeyError as error:
            raise ApplicationError("backend_not_found", f"Backend '{name}' was not found") from error

    def replay_events(self, run_id: str, last_event_id: int) -> tuple[list[dict[str, Any]], int, bool]:
        run_dir = self._run_dir(run_id)
        path = run_dir / "events.jsonl"
        projection = project_events(path)
        if projection.legacy:
            raise ApplicationError(
                "legacy_events_not_streamable",
                "Legacy events do not support SSE cursors",
                {"legacy_endpoint": f"/api/v1/runs/{run_id}/legacy-events"},
            )
        try:
            events, maximum = replay_v2(path, last_event_id)
        except IndexError as error:
            raise ApplicationError(
                "cursor_out_of_range",
                "Event cursor is beyond persisted history",
                {"max_event_id": error.args[0]},
            ) from error
        terminal = self.runs.read_summary(run_dir)["status"] not in {"running", "stale"}
        return events, maximum, terminal

    def replay_file_changes(self, run_id: str, last_seq: int) -> tuple[list[dict[str, Any]], int, bool]:
        """Replay file_changes.jsonl records for SSE file_changes topic.

        Returns (pending, max_seq, terminal). If file_changes.jsonl does not
        exist, returns ([], 0, terminal) — the topic is silently empty.
        Raises ApplicationError(cursor_out_of_range) if last_seq > max_seq.
        """
        run_dir = self._run_dir(run_id)
        path = run_dir / "file_changes.jsonl"
        try:
            records, maximum = replay_file_changes(path, last_seq)
        except IndexError as error:
            raise ApplicationError(
                "cursor_out_of_range",
                "File changes cursor is beyond persisted history",
                {"max_file_changes_id": error.args[0]},
            ) from error
        terminal = self.runs.read_summary(run_dir)["status"] not in {"running", "stale"}
        return records, maximum, terminal

    def list_file_changes(self, run_id: str) -> dict[str, Any]:
        """REST query: return all file_changes.jsonl records for a run.

        Returns {"items": [...], "count": N}. If file_changes.jsonl does not
        exist, returns {"items": [], "count": 0}.
        """
        run_dir = self._run_dir(run_id)
        path = run_dir / "file_changes.jsonl"
        if not path.is_file():
            return {"items": [], "count": 0}
        from loopflow.infrastructure.web_events import read_complete_jsonl
        records = read_complete_jsonl(path)
        valid = [
            rec for rec in records
            if isinstance(rec, dict) and isinstance(rec.get("seq"), int) and rec["seq"] >= 1
        ]
        valid.sort(key=lambda r: r["seq"])
        return {"items": valid, "count": len(valid)}

    def legacy_events(self, run_id: str) -> dict[str, Any]:
        detail = self.get_run(run_id)
        return {
            "items": detail["events"],
            "unattributed_count": detail["unattributed_count"],
            "malformed_count": detail["malformed_count"],
        }

    def _run_dir(self, run_id: str) -> Path:
        path = self.runs.find(run_id)
        if path is None:
            raise ApplicationError("run_not_found", f"Run '{run_id}' was not found")
        return path

    def _write_metadata(self, run_dir: Path, metadata: dict[str, Any]) -> None:
        try:
            self.runs.write_metadata(run_dir, metadata)
        except OSError as error:
            raise ApplicationError("atomic_write_failed", str(error)) from error

    def _worker_identity(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        pid = metadata.get("pid")
        process_group_id = metadata.get("process_group_id")
        process_started_at = metadata.get("process_started_at")
        execution_epoch = metadata.get("execution_epoch")
        if (
            isinstance(pid, int)
            and isinstance(process_group_id, int)
            and isinstance(process_started_at, str)
            and process_started_at
            and isinstance(execution_epoch, int)
        ):
            return {
                "pid": pid,
                "process_group_id": process_group_id,
                "process_started_at": process_started_at,
                "execution_epoch": execution_epoch,
            }
        return None

    def _identity_matches(self, identity: dict[str, Any]) -> bool:
        pid = identity["pid"]
        return (
            self.runs.process_probe.identity(pid) == identity["process_started_at"]
            and self.runs.process_probe.group_id(pid) == identity["process_group_id"]
        )

    def _cancelled_has_recovery_boundary(self, run_dir: Path, metadata: dict[str, Any]) -> bool:
        return bool(
            metadata.get("cancel_point")
            or metadata.get("active_call_id")
            or metadata.get("failed_call_id")
            or self._has_pending_intervention(run_dir)
        )

    def _has_pending_intervention(self, run_dir: Path) -> bool:
        interventions = run_dir / "interventions"
        if not interventions.is_dir():
            return False
        for path in interventions.glob("*.json"):
            try:
                value = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("status") in {None, "pending"}:
                return True
        return False

    def _clear_worker_identity(self, metadata: dict[str, Any]) -> None:
        metadata.pop("pid", None)
        metadata.pop("process_started_at", None)
        metadata.pop("process_group_id", None)

    def _execution_options(self, body: dict[str, Any], resume: bool = False) -> dict[str, Any]:
        # working_directory is validated and consumed by create_run itself
        allowed = {"backend", "model", "mock"} if resume else {"backend", "model", "mock", "from_phase", "only_phase", "loop", "args", "working_directory"}
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
