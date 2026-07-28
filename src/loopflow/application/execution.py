"""Shared headless workflow execution used by CLI and Web commands."""

from __future__ import annotations

import json
import multiprocessing
import os
import time
import uuid
from pathlib import Path
from typing import Any

from loopflow.infrastructure import loop_state
from loopflow.infrastructure.context import RunContext, State, set_context
from loopflow.infrastructure.discovery import _load_loop_meta, load_loop
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
    from loopflow.runtime import agent, intervene, log, parallel, pipeline, set_mock, workflow

    recover = bool(options.get("recover") or options.get("resume"))
    module, metadata, loop_dir = load_loop(loop)
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
            if key in {"backend", "model", "mock"}
        },
        "pid": pid,
        "process_group_id": os.getpgrp(),
        "process_started_at": SystemProcessProbe().identity(pid),
        # Explicit run working directory (ADR-0042): the child process has
        # already chdir'd, so cwd is the authoritative value
        "working_directory": str(Path.cwd()),
    }
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
    # Apply mock after the frozen execution_options merge so recovery of a
    # mock-executed run does not resolve a real backend (sys.exit when absent)
    if options.get("mock"):
        set_mock(options["mock"])
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
    context.default_backend = options.get("backend")
    context.default_model = options.get("model")
    # File change observation (ADR-0039): initialize observer from loop meta
    from loopflow.infrastructure.file_observation import FileChangeObserver, FileObservationConfig
    obs_config = FileObservationConfig.from_meta(metadata)
    if obs_config.enabled:
        context.file_observer = FileChangeObserver(
            run_dir=run_dir,
            working_dir=Path.cwd(),
            config=obs_config,
        )
        # Baseline snapshot (ADR-0043): pre-existing files are not "created"
        context.file_observer.seed()
    set_context(context)
    kwargs = {"agent": agent, "parallel": parallel, "pipeline": pipeline, "log": log, "args": args, "workflow": workflow, "intervene": intervene}
    kwargs["state"] = state
    try:
        module.run(**accepted_kwargs(module.run, kwargs))
    except KeyboardInterrupt:
        status, error = "cancelled", None
        error_traceback = None
    except Exception as exc:
        from loopflow.infrastructure.intervention import InterventionPending
        from loopflow.infrastructure.recovery import ReplayDiverged

        if isinstance(exc, InterventionPending):
            status, error = "waiting_input", None
        elif isinstance(exc, ReplayDiverged):
            status, error = "failed", "replay_diverged"
        else:
            status, error = "failed", str(exc)
        import traceback as _tb
        error_traceback = "".join(_tb.format_exception(exc))
    except BaseException as exc:
        status, error = "failed", str(exc)
        import traceback as _tb
        error_traceback = "".join(_tb.format_exception(exc))
    else:
        if recover and context.recovery_target_call_id and not context.recovery_target_reached:
            status, error = "failed", "replay_diverged"
            error_traceback = None
        else:
            status, error = "done", None
            error_traceback = None
    # Final file observation: capture files written after the last agent call
    if context.file_observer is not None:
        try:
            call_id = getattr(context, '_current_call_id', None) or "unknown"
            context.file_observer.observe(call_id, call_id)
        except Exception:
            pass
    finished = now_iso()
    run_metadata.update({"status": status, "counter": context._counter, "finished_at": finished, "updated_at": finished, "error_summary": error, "error_traceback": error_traceback})
    if recover:
        run_metadata["recovery_verification"] = (
            "unverified" if context.legacy_recovery else "verified"
        )
    if status == "failed" and context._current_call_id:
        run_metadata["failed_call_id"] = context._current_call_id
        run_metadata["active_call_id"] = context._current_call_id
        run_metadata["failed_session_id"] = context.failed_session_id
        run_metadata["can_recover_continue"] = context.failed_can_continue
        if context.failed_error_category is not None:
            # ADR-0044 §3 / BR-049：与 error_summary 并列的失败分类
            run_metadata["error_category"] = context.failed_error_category
    elif status == "done":
        run_metadata.pop("failed_call_id", None)
        run_metadata.pop("failed_session_id", None)
        run_metadata.pop("can_recover_continue", None)
        run_metadata.pop("error_category", None)
        run_metadata.pop("cancel_point", None)
        run_metadata.pop("active_call_id", None)
        run_metadata.pop("active_worker_atomic", None)
        if "state" in accepted_kwargs(module.run, {"state": state}) and context.state is not None:
            atomic_write_json(run_dir / "state.json", context.state.to_dict())
    run_metadata.pop("pid", None)
    run_metadata.pop("process_started_at", None)
    run_metadata.pop("process_group_id", None)
    # Stale grace (BR-052): the worker's terminal write is authoritative and
    # clears stale_since recorded by the read model while it was unreachable
    run_metadata.pop("stale_since", None)
    current = read_json(run_dir / "run.json")
    if (
        current.get("execution_epoch") == run_metadata.get("execution_epoch")
        and current.get("status") == "running"
    ):
        atomic_write_json(run_dir / "run.json", run_metadata)
    # Circuit breaker (ADR-0045 §2 / BR-050): count terminal failures per loop
    # and pause at the threshold; a done run resets the streak. Manual and
    # dispatch-triggered runs alike land here, so both are counted.
    if status == "failed":
        loop_state.record_failure(loop, run_id, threshold=loop_state.failure_threshold(metadata))
    elif status == "done":
        loop_state.record_success(loop)


def execute_single_agent(
    loop_dir: Path,
    single_agent: dict[str, Any],
    options: dict[str, Any],
    run_id: str,
    run_dir: Path,
    working_directory: str | Path | None = None,
) -> tuple[str, Any]:
    """Execute one agent_def call as a full Run (ADR-0055).

    Mirrors execute_workflow()'s run.json lifecycle but never imports or
    executes workflow.py; the workflow digest component stays None
    (RunContext.digest_workflow=False). Callers chdir beforehand; when
    working_directory is given it is chdir'd into first.

    Returns (status, result_value) so foreground callers can print the
    agent result and derive their exit code.
    """
    from loopflow.runtime import agent, set_mock

    if working_directory is not None:
        os.chdir(working_directory)
    loop = loop_dir.name
    metadata = _load_loop_meta(loop_dir)
    recover = bool(options.get("recover") or options.get("resume"))
    started = now_iso()
    pid = os.getpid()
    run_metadata = {
        "loop": loop,
        "run_id": run_id,
        "status": "running",
        "created": started,
        "started_at": started,
        "finished_at": None,
        "args": {},
        "counter": 0,
        "execution_epoch": 1,
        "execution_options": {
            key: value
            for key, value in options.items()
            if key in {"backend", "model", "mock", "transport"}
        },
        "single_agent": single_agent,
        "pid": pid,
        "process_group_id": os.getpgrp(),
        "process_started_at": SystemProcessProbe().identity(pid),
        # The caller has already chdir'd, so cwd is the authoritative value
        "working_directory": str(Path.cwd()),
    }
    if recover and (run_dir / "run.json").is_file():
        previous = read_json(run_dir / "run.json")
        run_metadata.update(previous)
        # Frozen single-agent config (ADR-0036): recovery never accepts an
        # override; agent/prompt/params always come from run.json
        single_agent = previous.get("single_agent") or single_agent
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
            "single_agent": single_agent,
        })
        options = {**frozen_options, **{key: value for key, value in options.items() if key in {"recover", "resume", "recovery_mode"}}}
    if options.get("mock"):
        set_mock(options["mock"])
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
        digest_workflow=False,
    )
    context.default_backend = options.get("backend")
    context.default_model = options.get("model")
    # File change observation (ADR-0039): initialize observer from loop meta
    from loopflow.infrastructure.file_observation import FileChangeObserver, FileObservationConfig
    obs_config = FileObservationConfig.from_meta(metadata)
    if obs_config.enabled:
        context.file_observer = FileChangeObserver(
            run_dir=run_dir,
            working_dir=Path.cwd(),
            config=obs_config,
        )
        context.file_observer.seed()
    set_context(context)
    value = None
    try:
        result = agent(
            single_agent["prompt"],
            agent_def=single_agent["agent_def"],
            **(single_agent.get("params") or {}),
        )
        value = getattr(result, "value", result)
    except KeyboardInterrupt:
        status, error = "cancelled", None
        error_traceback = None
    except Exception as exc:
        from loopflow.infrastructure.intervention import InterventionPending
        from loopflow.infrastructure.recovery import ReplayDiverged

        if isinstance(exc, InterventionPending):
            status, error = "waiting_input", None
        elif isinstance(exc, ReplayDiverged):
            status, error = "failed", "replay_diverged"
        else:
            status, error = "failed", str(exc)
        import traceback as _tb
        error_traceback = "".join(_tb.format_exception(exc))
    except BaseException as exc:
        status, error = "failed", str(exc)
        import traceback as _tb
        error_traceback = "".join(_tb.format_exception(exc))
    else:
        if recover and context.recovery_target_call_id and not context.recovery_target_reached:
            status, error = "failed", "replay_diverged"
            error_traceback = None
        else:
            status, error = "done", None
            error_traceback = None
    # Final file observation: capture files written after the agent call
    if context.file_observer is not None:
        try:
            call_id = getattr(context, '_current_call_id', None) or "unknown"
            context.file_observer.observe(call_id, call_id)
        except Exception:
            pass
    finished = now_iso()
    run_metadata.update({"status": status, "counter": context._counter, "finished_at": finished, "updated_at": finished, "error_summary": error, "error_traceback": error_traceback})
    if recover:
        run_metadata["recovery_verification"] = (
            "unverified" if context.legacy_recovery else "verified"
        )
    if status == "failed" and context._current_call_id:
        run_metadata["failed_call_id"] = context._current_call_id
        run_metadata["active_call_id"] = context._current_call_id
        run_metadata["failed_session_id"] = context.failed_session_id
        run_metadata["can_recover_continue"] = context.failed_can_continue
        if context.failed_error_category is not None:
            run_metadata["error_category"] = context.failed_error_category
    elif status == "done":
        run_metadata.pop("failed_call_id", None)
        run_metadata.pop("failed_session_id", None)
        run_metadata.pop("can_recover_continue", None)
        run_metadata.pop("error_category", None)
        run_metadata.pop("cancel_point", None)
        run_metadata.pop("active_call_id", None)
        run_metadata.pop("active_worker_atomic", None)
        if context.state is not None:
            atomic_write_json(run_dir / "state.json", context.state.to_dict())
    run_metadata.pop("pid", None)
    run_metadata.pop("process_started_at", None)
    run_metadata.pop("process_group_id", None)
    run_metadata.pop("stale_since", None)
    current = read_json(run_dir / "run.json")
    if (
        current.get("execution_epoch") == run_metadata.get("execution_epoch")
        and current.get("status") == "running"
    ):
        atomic_write_json(run_dir / "run.json", run_metadata)
    if status == "failed":
        loop_state.record_failure(loop, run_id, threshold=loop_state.failure_threshold(metadata))
    elif status == "done":
        loop_state.record_success(loop)
    return status, value


def _loop_dir_for(loop: str) -> Path:
    """Resolve a loop's directory without importing its workflow.py (ADR-0055)."""
    from loopflow.infrastructure.discovery import _loops_dir

    return _loops_dir() / loop


def _execute_workflow_process(
    loop: str,
    args: dict[str, Any],
    options: dict[str, Any],
    run_id: str,
    run_dir: Path,
    execution_lock: Path,
    working_directory: str,
) -> None:
    try:
        # Explicit run working directory (ADR-0042): chdir first so every
        # downstream Path.cwd() consumer (observer, backends, workflow)
        # resolves inside the run's directory
        os.chdir(working_directory)
        if hasattr(os, "setsid"):
            try:
                os.setsid()
            except OSError:
                pass
        single_agent = options.get("single_agent")
        if single_agent is None and (run_dir / "run.json").is_file():
            single_agent = read_json(run_dir / "run.json").get("single_agent")
        if single_agent is not None:
            execute_single_agent(_loop_dir_for(loop), single_agent, options, run_id, run_dir)
        else:
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
        # Default to spawn for cross-platform determinism: every child gets a
        # fresh interpreter with the parent's *current* environment. The
        # platform defaults (fork / forkserver) leak stale state — forkserver
        # children inherit the forkserver process's env from its creation
        # time, not the parent's env at start() time.
        self.context = multiprocessing.get_context(start_method or "spawn")

    def start(
        self,
        loop: str,
        args: dict[str, Any],
        options: dict[str, Any],
        run_id: str | None = None,
        working_directory: str | Path | None = None,
    ) -> str:
        run_id = run_id or uuid.uuid4().hex
        recover = bool(options.get("recover") or options.get("resume"))
        run_dir = self._existing(run_id) if recover else None
        explicit = working_directory is not None
        if recover and run_dir is not None:
            # Recover/rerun reuse the persisted working directory (ADR-0042);
            # a new value never overrides it
            persisted = read_json(run_dir / "run.json").get("working_directory")
            if isinstance(persisted, str) and persisted:
                working_directory = persisted
                explicit = True
            else:
                working_directory = None
                explicit = False
        # For run_dir naming: use explicit working_directory or server cwd (ADR-0054)
        base = Path(working_directory) if working_directory is not None else Path.cwd()
        encoded = str(base.resolve()).lstrip("/").replace("/", "-")
        run_dir = run_dir or self.runs_root / f"lf_{encoded}" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        # Default isolation (ADR-0054): when no explicit working_directory,
        # create run_dir/work so the file observer and agent output stay
        # isolated from the server's cwd (typically the project root).
        if not explicit:
            working_directory = run_dir / "work"
            working_directory.mkdir(parents=True, exist_ok=True)
        else:
            working_directory = Path(working_directory)
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
        process = self.context.Process(target=_execute_workflow_process, args=(loop, args, options, run_id, run_dir, lock_path, str(working_directory)), daemon=False)
        try:
            process.start()
        except BaseException:
            try:
                lock_path.unlink()
            except OSError:
                pass
            raise
        # The child must signal a started run within this window. Keep it
        # generous: on loaded or low-core machines (CI), interpreter boot plus
        # coverage tracing can take several seconds before run.json appears.
        deadline = time.monotonic() + 15
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
