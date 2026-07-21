"""Shared headless workflow execution used by CLI and Web commands."""

from __future__ import annotations

import inspect
import multiprocessing
import os
import time
import uuid
from pathlib import Path
from typing import Any

from loopflow.infrastructure.context import RunContext, State, set_context
from loopflow.infrastructure.discovery import load_loop
from loopflow.infrastructure.web_storage import SystemProcessProbe, append_run_index, atomic_write_json, now_iso, read_json


def execute_workflow(
    loop: str,
    args: dict[str, Any],
    options: dict[str, Any],
    run_id: str,
    run_dir: Path,
) -> None:
    """Execute one workflow in the current process and persist its lifecycle."""
    from loopflow.runtime import agent, log, parallel, phase, pipeline, set_mock, workflow

    resume = bool(options.get("resume"))
    module, metadata, loop_dir = load_loop(loop)
    if options.get("mock"):
        set_mock(options["mock"])
    started = now_iso()
    run_metadata = {
        "loop": loop,
        "run_id": run_id,
        "status": "running",
        "created": started,
        "started_at": started,
        "finished_at": None,
        "args": args,
        "counter": 0,
        "pid": os.getpid(),
        "process_started_at": SystemProcessProbe().identity(os.getpid()),
    }
    if resume and (run_dir / "run.json").is_file():
        previous = read_json(run_dir / "run.json")
        run_metadata.update(previous)
        run_metadata.update({"status": "running", "started_at": started, "finished_at": None, "pid": os.getpid(), "process_started_at": SystemProcessProbe().identity(os.getpid())})
    atomic_write_json(run_dir / "run.json", run_metadata)

    defaults = metadata.get("state", {})
    state = State(defaults)
    if resume and (run_dir / "state.json").is_file():
        try:
            state = State.from_dict(read_json(run_dir / "state.json"), defaults)
        except (OSError, ValueError):
            pass
    context = RunContext(run_id=run_id, run_dir=run_dir, resume=resume, loop_dir=loop_dir, state=state, counter=int(run_metadata.get("counter", 0)))
    context.from_phase = options.get("from_phase")
    context.only_phase = options.get("only_phase")
    context.default_backend = options.get("backend")
    context.default_model = options.get("model")
    set_context(context)
    kwargs = {"agent": agent, "parallel": parallel, "pipeline": pipeline, "phase": phase, "log": log, "args": args, "workflow": workflow}
    if "state" in inspect.signature(module.run).parameters:
        kwargs["state"] = state
    try:
        module.run(**kwargs)
    except KeyboardInterrupt:
        status, error = "stopped", None
    except BaseException as exc:
        status, error = "failed", str(exc)
    else:
        status, error = "done", None
    finished = now_iso()
    run_metadata.update({"status": status, "counter": context._counter, "finished_at": finished, "updated_at": finished, "error_summary": error})
    run_metadata.pop("pid", None)
    run_metadata.pop("process_started_at", None)
    atomic_write_json(run_dir / "run.json", run_metadata)


class BackgroundRunExecutor:
    """Launch shared workflow execution without invoking the CLI presentation."""

    def __init__(self, runs_root: Path, start_method: str | None = None) -> None:
        self.runs_root = runs_root
        self.context = multiprocessing.get_context(start_method) if start_method else multiprocessing.get_context()

    def start(self, loop: str, args: dict[str, Any], options: dict[str, Any], run_id: str | None = None) -> str:
        run_id = run_id or uuid.uuid4().hex
        run_dir = self._existing(run_id) if options.get("resume") else None
        working_directory = Path.cwd()
        encoded = str(working_directory.resolve()).lstrip("/").replace("/", "-")
        run_dir = run_dir or self.runs_root / f"lf_{encoded}" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        if not options.get("resume"):
            append_run_index(self.runs_root, working_directory, run_dir.parent, run_id)
        process = self.context.Process(target=execute_workflow, args=(loop, args, options, run_id, run_dir), daemon=False)
        process.start()
        deadline = time.monotonic() + 2
        while not (run_dir / "run.json").is_file() and process.is_alive() and time.monotonic() < deadline:
            time.sleep(0.005)
        if not (run_dir / "run.json").is_file():
            process.join(timeout=0.1)
            raise RuntimeError("run_process_start_failed")
        return run_id

    def _existing(self, run_id: str) -> Path | None:
        direct = self.runs_root / run_id
        if (direct / "run.json").is_file():
            return direct
        return next((path.parent for path in self.runs_root.glob(f"*/{run_id}/run.json")), None)
