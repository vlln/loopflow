"""Shared headless workflow execution used by CLI and Web commands."""

from __future__ import annotations

import json
import multiprocessing
import os
import time
import uuid
from pathlib import Path
from typing import Any

from loopflow.infrastructure.context import RunContext, State, set_context
from loopflow.infrastructure.discovery import load_loop
from loopflow.infrastructure.web_storage import SystemProcessProbe, append_run_index, atomic_write_json, now_iso, read_json
from loopflow.infrastructure.workflow_args import accepted_kwargs


def execute_workflow(
    loop: str,
    args: dict[str, Any],
    options: dict[str, Any],
    run_id: str,
    run_dir: Path,
) -> None:
    """Execute one workflow in the current process and persist its lifecycle."""
    from loopflow.runtime import agent, intervene, log, parallel, phase, pipeline, set_mock, workflow

    recover = bool(options.get("recover") or options.get("resume"))
    module, metadata, loop_dir = load_loop(loop)
    if options.get("mock"):
        set_mock(options["mock"])
    started = now_iso()
    pid = os.getpid()
    run_metadata = {
        "loop": loop,
        "run_id": run_id,
        "status": "running",
        "created": started,
        "started_at": started,
        "finished_at": None,
        "args": args,
        "counter": 0,
        "execution_epoch": 1,
        "execution_options": {
            key: value
            for key, value in options.items()
            if key in {"backend", "model", "mock", "from_phase", "only_phase"}
        },
        "pid": pid,
        "process_group_id": os.getpgrp(),
        "process_started_at": SystemProcessProbe().identity(pid),
    }
    declared_phases = metadata.get("phases")
    if isinstance(declared_phases, list):
        valid_phases = [
            {"title": str(p.get("title", "")).strip(), "detail": str(p.get("detail") or "")}
            for p in declared_phases
            if isinstance(p, dict) and isinstance(p.get("title"), str) and p["title"].strip()
        ]
        if valid_phases:
            run_metadata["declared_phases"] = valid_phases
    if recover and (run_dir / "run.json").is_file():
        previous = read_json(run_dir / "run.json")
        run_metadata.update(previous)
        frozen_options = dict(previous.get("execution_options") or {})
        run_metadata.update({
            "status": "running",
            "started_at": started,
            "finished_at": None,
            "pid": pid,
            "process_group_id": os.getpgrp(),
            "process_started_at": SystemProcessProbe().identity(pid),
            "counter": 0,
            "execution_epoch": int(previous.get("execution_epoch", 0)) + 1,
            "execution_options": frozen_options,
        })
        options = {**frozen_options, **{key: value for key, value in options.items() if key in {"recover", "resume", "recovery_mode"}}}
    atomic_write_json(run_dir / "run.json", run_metadata)

    defaults = metadata.get("state", {})
    state = State(defaults)
    context = RunContext(
        run_id=run_id,
        run_dir=run_dir,
        resume=recover,
        loop_dir=loop_dir,
        state=state,
        counter=0,
        recovery_mode=options.get("recovery_mode", "retry") if recover else None,
        recovery_target_call_id=run_metadata.get("failed_call_id") if recover else None,
        execution_options=run_metadata.get("execution_options"),
    )
    context.from_phase = options.get("from_phase")
    context.only_phase = options.get("only_phase")
    context.default_backend = options.get("backend")
    context.default_model = options.get("model")
    set_context(context)
    kwargs = {"agent": agent, "parallel": parallel, "pipeline": pipeline, "phase": phase, "log": log, "args": args, "workflow": workflow, "intervene": intervene}
    kwargs["state"] = state
    try:
        module.run(**accepted_kwargs(module.run, kwargs))
    except KeyboardInterrupt:
        status, error = "cancelled", None
    except Exception as exc:
        from loopflow.infrastructure.intervention import InterventionPending
        from loopflow.infrastructure.recovery import ReplayDiverged

        if isinstance(exc, InterventionPending):
            status, error = "waiting_input", None
        elif isinstance(exc, ReplayDiverged):
            status, error = "failed", "replay_diverged"
        else:
            status, error = "failed", str(exc)
    except BaseException as exc:
        status, error = "failed", str(exc)
    else:
        if recover and context.recovery_target_call_id and not context.recovery_target_reached:
            status, error = "failed", "replay_diverged"
        else:
            status, error = "done", None
    finished = now_iso()
    run_metadata.update({"status": status, "counter": context._counter, "finished_at": finished, "updated_at": finished, "error_summary": error})
    if recover:
        run_metadata["recovery_verification"] = (
            "unverified" if context.legacy_recovery else "verified"
        )
    if status == "failed" and context._current_call_id:
        run_metadata["failed_call_id"] = context._current_call_id
        run_metadata["active_call_id"] = context._current_call_id
        run_metadata["failed_session_id"] = context.failed_session_id
        run_metadata["can_recover_continue"] = context.failed_can_continue
    elif status == "done":
        run_metadata.pop("failed_call_id", None)
        run_metadata.pop("failed_session_id", None)
        run_metadata.pop("can_recover_continue", None)
        run_metadata.pop("cancel_point", None)
        run_metadata.pop("active_call_id", None)
        run_metadata.pop("active_worker_atomic", None)
        if "state" in accepted_kwargs(module.run, {"state": state}) and context.state is not None:
            atomic_write_json(run_dir / "state.json", context.state.to_dict())
    run_metadata.pop("pid", None)
    run_metadata.pop("process_started_at", None)
    run_metadata.pop("process_group_id", None)
    current = read_json(run_dir / "run.json")
    if (
        current.get("execution_epoch") == run_metadata.get("execution_epoch")
        and current.get("status") == "running"
    ):
        atomic_write_json(run_dir / "run.json", run_metadata)


def _execute_workflow_process(
    loop: str,
    args: dict[str, Any],
    options: dict[str, Any],
    run_id: str,
    run_dir: Path,
    execution_lock: Path,
) -> None:
    try:
        if hasattr(os, "setsid"):
            try:
                os.setsid()
            except OSError:
                pass
        execute_workflow(loop, args, options, run_id, run_dir)
    finally:
        for path in (execution_lock, run_dir / ".recovery.ready"):
            try:
                path.unlink()
            except OSError:
                pass


class BackgroundRunExecutor:
    """Launch shared workflow execution without invoking the CLI presentation."""

    def __init__(self, runs_root: Path, start_method: str | None = None) -> None:
        self.runs_root = runs_root
        self.context = multiprocessing.get_context(start_method) if start_method else multiprocessing.get_context()

    def start(self, loop: str, args: dict[str, Any], options: dict[str, Any], run_id: str | None = None) -> str:
        run_id = run_id or uuid.uuid4().hex
        recover = bool(options.get("recover") or options.get("resume"))
        run_dir = self._existing(run_id) if recover else None
        working_directory = Path.cwd()
        encoded = str(working_directory.resolve()).lstrip("/").replace("/", "-")
        run_dir = run_dir or self.runs_root / f"lf_{encoded}" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        previous_epoch = None
        if recover:
            previous_epoch = int(read_json(run_dir / "run.json").get("execution_epoch", 0))
        if not recover:
            append_run_index(self.runs_root, working_directory, run_dir.parent, run_id)
        lock_path = run_dir / ".execution.lock"
        ready_path = run_dir / ".recovery.ready"
        try:
            ready_path.unlink()
        except OSError:
            pass
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, str(os.getpid()).encode())
            os.close(descriptor)
        except FileExistsError as error:
            raise RuntimeError("invalid_run_transition") from error
        process = self.context.Process(target=_execute_workflow_process, args=(loop, args, options, run_id, run_dir, lock_path), daemon=False)
        try:
            process.start()
        except BaseException:
            try:
                lock_path.unlink()
            except OSError:
                pass
            raise
        deadline = time.monotonic() + 2
        def started() -> bool:
            if not (run_dir / "run.json").is_file():
                return False
            if previous_epoch is None:
                return True
            try:
                metadata = read_json(run_dir / "run.json")
                epoch_started = int(metadata.get("execution_epoch", 0)) > previous_epoch
                return epoch_started and (
                    ready_path.is_file()
                    or metadata.get("status") in {"done", "failed", "cancelled", "waiting_input"}
                )
            except (OSError, ValueError, json.JSONDecodeError):
                return False

        while not started() and process.is_alive() and time.monotonic() < deadline:
            time.sleep(0.005)
        if not started():
            process.join(timeout=0.1)
            try:
                lock_path.unlink()
            except OSError:
                pass
            raise RuntimeError("run_process_start_failed")
        if recover:
            metadata = read_json(run_dir / "run.json")
            error = metadata.get("error_summary")
            if metadata.get("status") == "failed" and error in {
                "replay_diverged",
                "continue_not_supported",
            }:
                raise RuntimeError(error)
        return run_id

    def _existing(self, run_id: str) -> Path | None:
        direct = self.runs_root / run_id
        if (direct / "run.json").is_file():
            return direct
        return next((path.parent for path in self.runs_root.glob(f"*/{run_id}/run.json")), None)
