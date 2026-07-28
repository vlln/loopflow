"""loopflow CLI — AI Agent loop orchestration tool.

Commands:
    loopflow run <name> [--args '<json>']
    loopflow resume <run-id>
    loopflow status <run-id>
    loopflow list
    loopflow stop <run-id>

The alias ``loop`` is also available (e.g. ``loop run <name>``).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import click

from loopflow.infrastructure.workflow_args import accepted_kwargs
from loopflow.infrastructure.web_storage import append_run_index, atomic_write_json


def _write_run(path: Path, metadata: dict) -> None:
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(path, metadata)


def _finish_run(metadata: dict, status: str) -> None:
    metadata["status"] = status
    metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
    metadata.pop("pid", None)
    metadata.pop("process_started_at", None)
    metadata.pop("stale_since", None)


def _runs_dir() -> Path:
    home = os.environ.get("HOME", os.path.expanduser("~"))
    runs = os.environ.get("LOOPFLOW_RUNS_DIR", str(Path(home) / ".loopflow" / "runs"))
    return Path(runs)


def _find_run_by_id(run_id: str) -> Path | None:
    """Find a run directory by run_id, searching all lf_*/ directories.

    Returns the run_dir Path, or None if not found.
    """
    runs = _runs_dir()
    if not runs.is_dir():
        return None
    for lf_dir in sorted(runs.iterdir()):
        if not lf_dir.is_dir() or not lf_dir.name.startswith("lf_"):
            continue
        run_dir = lf_dir / run_id
        if run_dir.is_dir() and (run_dir / "run.json").is_file():
            return run_dir
    return None


def _run_dir_for_pwd() -> Path:
    """Return the run directory for the current working directory.

    Creates runs/lf_<pwd-path>/ where pwd-path has '/' replaced with '-'.
    """
    pwd = str(Path.cwd().absolute()).lstrip("/").replace("/", "-")
    return _runs_dir() / f"lf_{pwd}"


def _check_environment(meta: dict, loop_dir: Path) -> None:
    """Check that declared environment file exists."""
    env_file = meta.get("requires", {}).get("environment")
    if not env_file:
        return
    env_path = loop_dir / env_file
    if not env_path.is_file():
        print(
            f"Error: environment file '{env_file}' not found in {loop_dir}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"[loopflow] Environment: {env_file} (make sure the environment is activated)",
        file=sys.stderr,
    )


@click.group()
def main():
    """loopflow — AI Agent loop orchestration tool."""
    pass


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=click.IntRange(0, 65535), default=8765, show_default=True)
@click.option("--allow-remote", is_flag=True, default=False)
def web(host: str, port: int, allow_remote: bool) -> None:
    """Serve the local WebUI and API."""
    from loopflow.presentation.web.server import create_server, is_loopback

    if not is_loopback(host) and not allow_remote:
        raise click.ClickException("remote host requires --allow-remote")
    if not is_loopback(host):
        click.echo(f"Warning: WebUI is exposed on remote host {host}", err=True)
    server = create_server(host, port, allow_remote=allow_remote)
    bound_host, bound_port = server.server_address[:2]
    click.echo(f"loopflow WebUI: http://{bound_host}:{bound_port}", err=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


@main.command()
@click.argument("name")
@click.option("--args", "wf_args", default=None, help="JSON args for workflow.py")
@click.option("--agent", "agent_name", default=None,
              help="Run a single agent_def from the loop's agents/ directory (ADR-0055)")
@click.option("--prompt", default=None,
              help="Task prompt for --agent mode (mutually exclusive with --prompt-file)")
@click.option("--prompt-file", "prompt_file", default=None,
              help="Read the --agent task prompt from a file")
@click.option("--param", "params", multiple=True,
              help="Template parameter for --agent mode, key=value (repeatable)")
@click.option("--mock", type=click.Choice(["bash", "auto"]), default=None,
              help="Mock mode: bash (shell execution) or auto (schema-based generation)")
@click.option("--backend", default=None, help="Agent backend (pi, kimi, claude, codex, ...)")
@click.option("--transport", default=None, help="Transport mode (cli, acp). ADR-0049")
@click.option("--work-dir", default=None,
              help="Working directory for the loop: a path to chdir into; "
                   "empty string to let the framework create one under run_dir; "
                   "omitted to use the current directory.")
def run(name, wf_args, mock, backend, transport, work_dir, agent_name, prompt, prompt_file, params):
    """Run a loop."""
    from loopflow.infrastructure.discovery import load_loop
    from loopflow.runtime import RunContext, set_context, set_mock, agent, parallel, pipeline, log, workflow, intervene

    if agent_name is not None:
        _run_single_agent(
            name, agent_name, prompt, prompt_file, params,
            wf_args, mock, backend, transport, work_dir,
        )
        return

    if mock:
        set_mock(mock)

    args_dict = {}
    if wf_args:
        try:
            args_dict = json.loads(wf_args)
        except json.JSONDecodeError as e:
            print(f"Error: invalid --args JSON: {e}", file=sys.stderr)
            sys.exit(1)

    mod, meta, loop_dir = load_loop(name)
    _check_environment(meta, loop_dir)

    run_id = uuid.uuid4().hex
    run_dir = _run_dir_for_pwd() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    append_run_index(_runs_dir(), Path.cwd(), run_dir.parent, run_id)

    # --work-dir: chdir to a loop working directory before execution.
    #   omitted  → current dir (Path.cwd() stays the loop-run location)
    #   ""       → framework-managed: run_dir/work (isolated from loopflow internals)
    #   <path>   → that path
    # The loop and its agents then see this as the current directory; the loop
    # does not handle paths itself.
    if work_dir is not None:
        target = run_dir / "work" if work_dir == "" else Path(work_dir)
        target.mkdir(parents=True, exist_ok=True)
        os.chdir(target)

    # Write run.json
    run_meta = {
        "loop": name,
        "run_id": run_id,
        "status": "running",
        "created": datetime.now(timezone.utc).isoformat(),
        "args": args_dict,
        "counter": 0,
        "execution_epoch": 1,
        "execution_options": {
            "mock": mock,
            "backend": backend,
            "transport": transport,
        },
    }
    _write_run(run_dir / "run.json", run_meta)

    ctx = RunContext(
        run_id=run_id,
        run_dir=run_dir,
        loop_dir=loop_dir,
        execution_options=run_meta["execution_options"],
    )
    set_context(ctx)

    # File change observation (ADR-0039): initialize observer from loop meta
    from loopflow.infrastructure.file_observation import FileChangeObserver, FileObservationConfig
    obs_config = FileObservationConfig.from_meta(meta)
    if obs_config.enabled:
        ctx.file_observer = FileChangeObserver(
            run_dir=run_dir,
            working_dir=Path.cwd(),
            config=obs_config,
        )
        ctx.file_observer.seed()

    # Create state from meta declaration
    from loopflow.runtime import State
    state_defaults = meta.get("state", {})
    state = State(state_defaults)
    ctx.state = state

    print(f"[loopflow] Running: {name} ({run_id})", file=sys.stderr)

    try:
        # Build kwargs, only pass state if run() accepts it
        run_kwargs = dict(
            agent=agent, parallel=parallel, pipeline=pipeline,
            log=log, args=args_dict, workflow=workflow,
            intervene=intervene,
        )
        run_kwargs["state"] = state
        result = mod.run(**accepted_kwargs(mod.run, run_kwargs))
        # Final file observation
        if ctx.file_observer is not None:
            try:
                call_id = getattr(ctx, '_current_call_id', None) or "unknown"
                ctx.file_observer.observe(call_id, call_id)
            except Exception:
                pass
    except KeyboardInterrupt:
        print("\n[loopflow] Interrupted", file=sys.stderr)
        _finish_run(run_meta, "stopped")
        run_meta["counter"] = ctx._counter
        _write_run(run_dir / "run.json", run_meta)
        sys.exit(0)
    except Exception as e:
        from loopflow.infrastructure.intervention import InterventionPending

        if isinstance(e, InterventionPending):
            _finish_run(run_meta, "waiting_input")
            run_meta["counter"] = ctx._counter
            _write_run(run_dir / "run.json", run_meta)
            print(f"[loopflow] Waiting for input: {run_id}", file=sys.stderr)
            sys.exit(0)
        print(f"[loopflow] Error: {e}", file=sys.stderr)
        _finish_run(run_meta, "failed")
        run_meta["failed_call_id"] = ctx._current_call_id
        run_meta["failed_session_id"] = ctx.failed_session_id
        run_meta["can_recover_continue"] = ctx.failed_can_continue
        run_meta["counter"] = ctx._counter
        _write_run(run_dir / "run.json", run_meta)
        # Circuit breaker (ADR-0045 §2 / BR-050): manual run failures count too
        from loopflow.infrastructure import loop_state
        loop_state.record_failure(name, run_id, threshold=loop_state.failure_threshold(meta))
        sys.exit(1)

    _finish_run(run_meta, "done")
    run_meta["counter"] = ctx._counter
    _write_run(run_dir / "run.json", run_meta)

    # Circuit breaker (ADR-0045 §2): a done run resets the failure streak
    from loopflow.infrastructure import loop_state
    loop_state.record_success(name)

    if result is not None:
        if isinstance(result, str):
            print(result)
        elif isinstance(result, dict) and "summary" in result:
            print(result["summary"])
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"[loopflow] Done: {run_id}", file=sys.stderr)


def _run_single_agent(name, agent_name, prompt, prompt_file, params, wf_args, mock, backend, transport, work_dir):
    """Run a single agent_def as a full Run (ADR-0055).

    Validates everything before any Run is created: agent_def exists, prompt
    is given exactly once, --args is rejected, and required template params
    are satisfied. Never imports or executes workflow.py.
    """
    from loopflow.domain.agent_def import _input_to_params, render_template, resolve_params
    from loopflow.infrastructure.discovery import _load_loop_meta, _loops_dir
    from loopflow.infrastructure.repository import parse_agent
    from loopflow.runtime import set_mock

    loop_dir = _loops_dir() / name
    if not loop_dir.is_dir():
        raise click.ClickException(f"loop '{name}' not found")
    agent_path = loop_dir / "agents" / f"{agent_name}.md"
    if not agent_path.is_file():
        raise click.ClickException(
            f"agent_def '{agent_name}' not found: {agent_path}"
        )
    if (prompt is None) == (prompt_file is None):
        raise click.UsageError(
            "--agent requires exactly one of --prompt or --prompt-file"
        )
    if wf_args is not None:
        raise click.UsageError("--args has no consumer in --agent mode")

    try:
        ad = parse_agent(agent_path)
    except (ValueError, FileNotFoundError) as error:
        raise click.ClickException(f"invalid agent_def '{agent_name}': {error}") from error

    param_dict: dict[str, str] = {}
    for item in params:
        if "=" not in item:
            raise click.UsageError(f"invalid --param '{item}', expected key=value")
        key, value = item.split("=", 1)
        param_dict[key] = value
    # Render up front so a missing template param fails before any Run exists
    try:
        render_template(ad.body, **resolve_params(_input_to_params(ad.input), **param_dict))
    except ValueError as error:
        raise click.UsageError(str(error)) from error

    if prompt_file is not None:
        prompt_path = Path(prompt_file)
        if not prompt_path.is_file():
            raise click.ClickException(f"prompt file not found: {prompt_file}")
        prompt_text = prompt_path.read_text(encoding="utf-8")
    else:
        prompt_text = prompt

    if mock:
        set_mock(mock)

    meta = _load_loop_meta(loop_dir)
    _check_environment(meta, loop_dir)

    run_id = uuid.uuid4().hex
    run_dir = _run_dir_for_pwd() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    append_run_index(_runs_dir(), Path.cwd(), run_dir.parent, run_id)

    # --work-dir: same semantics as a workflow run
    if work_dir is not None:
        target = run_dir / "work" if work_dir == "" else Path(work_dir)
        target.mkdir(parents=True, exist_ok=True)
        os.chdir(target)

    single_agent = {"agent_def": agent_name, "prompt": prompt_text, "params": param_dict}
    options = {"mock": mock, "backend": backend, "transport": transport}

    print(f"[loopflow] Running: {name} --agent {agent_name} ({run_id})", file=sys.stderr)
    from loopflow.application.execution import execute_single_agent
    status, value = execute_single_agent(loop_dir, single_agent, options, run_id, run_dir)

    if status == "done":
        if isinstance(value, str):
            print(value)
        elif value is not None:
            print(json.dumps(value, indent=2, ensure_ascii=False))
        print(f"[loopflow] Done: {run_id}", file=sys.stderr)
        sys.exit(0)
    if status == "waiting_input":
        print(f"[loopflow] Waiting for input: {run_id}", file=sys.stderr)
        sys.exit(0)
    print(f"[loopflow] {status}: {run_id}", file=sys.stderr)
    sys.exit(1)


def legacy_resume_internal(run_id, mock):
    """Resume a crashed loop run."""
    from loopflow.infrastructure.discovery import load_loop
    from loopflow.runtime import RunContext, set_context, set_mock, agent, parallel, pipeline, log, workflow, intervene

    if mock:
        set_mock(mock)

    run_dir = _find_run_by_id(run_id)
    if run_dir is None:
        print(f"Error: run '{run_id}' not found", file=sys.stderr)
        sys.exit(1)

    run_json = run_dir / "run.json"
    if not run_json.is_file():
        print(f"Error: run '{run_id}' has no run.json", file=sys.stderr)
        sys.exit(1)

    run_meta = json.loads(run_json.read_text())
    if run_meta["status"] == "running":
        print(f"Error: run '{run_id}' is still running", file=sys.stderr)
        sys.exit(1)

    loop_name = run_meta["loop"]
    mod, meta, loop_dir = load_loop(loop_name)
    _check_environment(meta, loop_dir)
    args_dict = run_meta.get("args", {})

    run_meta["status"] = "running"
    run_meta.pop("finished_at", None)
    _write_run(run_json, run_meta)

    ctx = RunContext(run_id=run_id, run_dir=run_dir, resume=True,
                     loop_dir=loop_dir, counter=run_meta.get("counter", 0))
    set_context(ctx)

    # Restore state from state.json, filling missing keys from meta defaults
    from loopflow.runtime import State
    state_defaults = meta.get("state", {})
    state_path = run_dir / "state.json"
    if state_path.is_file():
        try:
            saved = json.loads(state_path.read_text())
            state = State.from_dict(saved, state_defaults)
        except (json.JSONDecodeError, OSError):
            state = State(state_defaults)
    else:
        state = State(state_defaults)
    ctx.state = state

    print(f"[loopflow] Resuming: {loop_name} ({run_id})", file=sys.stderr)

    try:
        run_kwargs = dict(
            agent=agent, parallel=parallel, pipeline=pipeline,
            log=log, args=args_dict, workflow=workflow,
            intervene=intervene,
        )
        run_kwargs["state"] = state
        result = mod.run(**accepted_kwargs(mod.run, run_kwargs))
    except KeyboardInterrupt:
        print("\n[loopflow] Interrupted", file=sys.stderr)
        _finish_run(run_meta, "stopped")
        run_meta["counter"] = ctx._counter
        _write_run(run_json, run_meta)
        sys.exit(0)
    except Exception as e:
        from loopflow.infrastructure.intervention import InterventionPending

        if isinstance(e, InterventionPending):
            _finish_run(run_meta, "waiting_input")
            run_meta["counter"] = ctx._counter
            _write_run(run_json, run_meta)
            print(f"[loopflow] Waiting for input: {run_id}", file=sys.stderr)
            sys.exit(0)
        print(f"[loopflow] Error: {e}", file=sys.stderr)
        _finish_run(run_meta, "failed")
        _write_run(run_json, run_meta)
        sys.exit(1)

    _finish_run(run_meta, "done")
    run_meta["counter"] = ctx._counter
    _write_run(run_json, run_meta)

    if result is not None:
        if isinstance(result, str):
            print(result)
        elif isinstance(result, dict) and "summary" in result:
            print(result["summary"])
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"[loopflow] Done: {run_id}", file=sys.stderr)


@main.command()
@click.argument("run_id")
@click.option("--mode", type=click.Choice(["retry", "continue"]), default="retry", show_default=True)
def recover(run_id: str, mode: str) -> None:
    """Recover a failed Run using retry or durable session continue."""
    from loopflow.application.execution import BackgroundRunExecutor
    from loopflow.application.web import ApplicationError, WebApplication
    from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
    from loopflow.infrastructure.web_storage import RunRepository

    runs_root = _runs_dir()
    run_dir = _find_run_by_id(run_id)
    if run_dir is not None and mode == "retry":
        from loopflow.infrastructure.recovery import read_call_segments

        legacy = any(
            segments and segments[-1].legacy
            for path in run_dir.glob("*.jsonl")
            if (segments := read_call_segments(path))
        )
        if legacy:
            click.echo(
                "Warning: legacy cache recovery is unverified; cache files remain unchanged.",
                err=True,
            )
    loops_root = Path(os.environ.get("LOOPFLOW_LOOPS_DIR", Path.home() / ".loopflow" / "loops"))
    runs = RunRepository(runs_root)
    service = WebApplication(
        runs=runs,
        loops=LoopRepository(loops_root, runs),
        queue=QueueRepository(Path(os.environ.get("LOOPFLOW_QUEUE_DIR", Path.home() / ".loopflow" / "queue"))),
        backends=BackendRepository(),
        executor=BackgroundRunExecutor(runs_root),
    )
    try:
        result = service.recover_run(run_id, {"mode": mode})
    except ApplicationError as error:
        raise click.ClickException(f"{error.code}: {error.message}") from error
    click.echo(f"[loopflow] Recovering ({mode}): {result['run_id']}", err=True)


@main.command()
@click.argument("run_id")
@click.option("--mock", type=click.Choice(["bash", "auto"]), default=None, hidden=True)
@click.pass_context
def resume(ctx: click.Context, run_id: str, mock: str | None) -> None:
    """Deprecated alias for recover --mode retry."""
    click.echo("Warning: 'resume' is deprecated; use 'recover --mode retry'.", err=True)
    ctx.invoke(recover, run_id=run_id, mode="retry")


@main.command()
@click.argument("run_id")
def status(run_id):
    """Show status of a run."""
    run_dir = _find_run_by_id(run_id)
    if run_dir is None:
        print(f"Error: run '{run_id}' not found", file=sys.stderr)
        sys.exit(1)

    run_json = run_dir / "run.json"
    if not run_json.is_file():
        print(f"Error: run '{run_id}' has no run.json", file=sys.stderr)
        sys.exit(1)

    meta = json.loads(run_json.read_text())
    agent_jsonl = sorted(
        [f for f in run_dir.glob("*.jsonl") if f.name != "events.jsonl"]
    )

    print(f"Run: {run_id}")
    print(f"  Loop:   {meta['loop']}")
    print(f"  Status: {meta['status']}")
    print(f"  Created: {meta['created']}")
    print(f"  Agents: {len(agent_jsonl)} calls")
    if meta.get("args"):
        print(f"  Args:   {json.dumps(meta['args'], ensure_ascii=False)}")


@main.command()
def list():
    """List all loops and runs."""
    from loopflow.infrastructure.discovery import list_loops

    print("Loops:")
    loops = list_loops()
    if not loops:
        print("  (none)")
    else:
        for name, meta, path in loops:
            desc = meta.get("description", "")
            print(f"  {name} — {desc}")

    print()
    print("Runs:")
    runs = _runs_dir()
    if not runs.is_dir():
        print("  (none)")
    else:
        run_entries: list[tuple[str, str, str, str]] = []  # run_id, status, loop, created
        for lf_dir in sorted(runs.iterdir()):
            if not lf_dir.is_dir() or not lf_dir.name.startswith("lf_"):
                continue
            for entry in sorted(lf_dir.iterdir()):
                rj = entry / "run.json"
                if rj.is_file():
                    try:
                        m = json.loads(rj.read_text())
                    except (json.JSONDecodeError, OSError):
                        continue
                    run_entries.append((m.get("run_id", entry.name), m.get("status", "?"), m.get("loop", "?"), m.get("created", "?")))
        if not run_entries:
            print("  (none)")
        for rid, status, loop, created in sorted(run_entries, key=lambda x: x[3], reverse=True):
            print(f"  {rid[:8]}  [{status}]  {loop}  {created}")


@main.command()
@click.argument("run_id")
def stop(run_id):
    """Stop a running loop."""
    from loopflow.application.web import ApplicationError, WebApplication
    from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
    from loopflow.infrastructure.web_storage import RunRepository

    runs_root = _runs_dir()
    runs = RunRepository(runs_root)
    loops_root = Path(os.environ.get("LOOPFLOW_LOOPS_DIR", Path.home() / ".loopflow" / "loops"))
    service = WebApplication(
        runs=runs,
        loops=LoopRepository(loops_root, runs),
        queue=QueueRepository(Path(os.environ.get("LOOPFLOW_QUEUE_DIR", Path.home() / ".loopflow" / "queue"))),
        backends=BackendRepository(),
    )
    try:
        result = service.stop_run(run_id)
    except ApplicationError as error:
        raise click.ClickException(f"{error.code}: {error.message}") from error
    click.echo(f"Stopped run '{result['run_id']}' ({result['status']})", err=True)


@main.command()
@click.argument("name")
@click.option("--args", "wf_args", default=None, help="JSON args for workflow.py")
@click.option("--priority", default=5, help="Task priority (lower = higher priority)")
@click.option("--supersede", is_flag=True, default=False,
              help="Mark existing pending/deferred tasks of this loop as superseded")
def enqueue(name, wf_args, priority, supersede):
    """Add a task to the dispatch queue."""
    from loopflow.infrastructure.discovery import load_loop
    from loopflow.infrastructure.queue import enqueue as queue_enqueue

    # Validate loop exists
    load_loop(name)

    args_dict = {}
    if wf_args:
        try:
            args_dict = json.loads(wf_args)
        except json.JSONDecodeError as e:
            print(f"Error: invalid --args JSON: {e}", file=sys.stderr)
            sys.exit(1)

    path = queue_enqueue(name, args=args_dict, priority=priority, supersede=supersede)
    print(f"[loopflow] Enqueued: {name} → {path}", file=sys.stderr)


@main.command()
def dispatch():
    """Process pending tasks from the queue."""
    from loopflow.infrastructure.dispatch import dispatch as run_dispatch

    summary = run_dispatch()
    print(f"[loopflow] Dispatch: {summary['processed']} processed, "
          f"{summary['deferred']} deferred, {summary['superseded']} superseded, "
          f"{summary['errors']} errors",
          file=sys.stderr)


@main.command()
@click.argument("name")
def unpause(name: str) -> None:
    """Clear a loop's circuit-breaker pause (manual release, BR-051)."""
    from loopflow.application.web import ApplicationError, WebApplication
    from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
    from loopflow.infrastructure.web_storage import RunRepository

    runs_root = _runs_dir()
    loops_root = Path(os.environ.get("LOOPFLOW_LOOPS_DIR", Path.home() / ".loopflow" / "loops"))
    service = WebApplication(
        runs=RunRepository(runs_root),
        loops=LoopRepository(loops_root, RunRepository(runs_root)),
        queue=QueueRepository(Path(os.environ.get("LOOPFLOW_QUEUE_DIR", Path.home() / ".loopflow" / "queue"))),
        backends=BackendRepository(),
    )
    try:
        result = service.unpause_loop(name)
    except ApplicationError as error:
        raise click.ClickException(f"{error.code}: {error.message}") from error
    click.echo(f"[loopflow] Unpaused: {result['name']}", err=True)
