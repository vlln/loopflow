"""loopflow CLI — AI Agent loop orchestration tool.

Commands:
    loop run <name> [--args '<json>']
    loop resume <run-id>
    loop status <run-id>
    loop list
    loop stop <run-id>
"""

from __future__ import annotations

import json
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import click


def _runs_dir() -> Path:
    home = os.environ.get("HOME", os.path.expanduser("~"))
    runs = os.environ.get("LOOPFLOW_RUNS_DIR", str(Path(home) / ".loopflow" / "runs"))
    return Path(runs)


def _print_graph(run_dir: Path) -> None:
    """Render and print the phase graph from events.jsonl."""
    events_path = run_dir / "events.jsonl"
    if not events_path.is_file():
        return

    from loopflow.graph import PhaseGraph
    from loopflow.display.graph_renderer import TerminalGraphRenderer

    events = []
    for line in events_path.read_text().strip().split("\n"):
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    pg = PhaseGraph.from_events(events)
    if not pg.nodes():
        return

    renderer = TerminalGraphRenderer(pg)
    rendered = renderer.render()
    if rendered.plain.strip():
        print(f"\n  {rendered.plain}", file=sys.stderr)


@click.group()
def main():
    """loopflow — AI Agent loop orchestration tool."""
    pass


@main.command()
@click.argument("name")
@click.option("--args", "wf_args", default=None, help="JSON args for workflow.py")
@click.option("--mock/--no-mock", default=False, help="Use mock backend (shell echo) for testing")
@click.option("--watch/--no-watch", default=False, help="Live-update phase graph during execution")
def run(name, wf_args, mock, watch):
    """Run a loop."""
    from loopflow.discovery import load_loop
    from loopflow.graph import PhaseGraph
    from loopflow.runtime import RunContext, set_context, set_mock, agent, parallel, pipeline, phase, log, workflow

    if mock:
        set_mock("shell")

    args_dict = {}
    if wf_args:
        try:
            args_dict = json.loads(wf_args)
        except json.JSONDecodeError as e:
            print(f"Error: invalid --args JSON: {e}", file=sys.stderr)
            sys.exit(1)

    mod, meta = load_loop(name)

    run_id = uuid.uuid4().hex[:8]
    run_dir = _runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write run.json
    run_meta = {
        "loop": name,
        "run_id": run_id,
        "status": "running",
        "created": datetime.now(timezone.utc).isoformat(),
        "args": args_dict,
        "counter": 0,
    }
    (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2))

    # Set up graph for live/watch mode
    pg = PhaseGraph() if watch else None
    live = None
    if watch:
        from rich.live import Live
        from loopflow.display.graph_renderer import TerminalGraphRenderer
        live = Live(TerminalGraphRenderer(pg).render(), refresh_per_second=10,
                     transient=True)
        live.start()

    ctx = RunContext(run_id=run_id, run_dir=run_dir, graph=pg, live=live)
    set_context(ctx)

    print(f"[loopflow] Running: {name} ({run_id})", file=sys.stderr)

    try:
        result = mod.run(
            agent=agent, parallel=parallel, pipeline=pipeline,
            phase=phase, log=log, args=args_dict, workflow=workflow,
        )
    except Exception as e:
        print(f"[loopflow] Error: {e}", file=sys.stderr)
        run_meta["status"] = "failed"
        (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2))
        if live:
            live.stop()
        sys.exit(1)

    if live:
        live.stop()

    run_meta["status"] = "done"
    run_meta["counter"] = ctx._counter
    (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2))

    if result is not None:
        if isinstance(result, str):
            print(result)
        elif isinstance(result, dict) and "summary" in result:
            print(result["summary"])
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"[loopflow] Done: {run_id}", file=sys.stderr)

    # Auto-render graph at end
    _print_graph(run_dir)


@main.command()
@click.argument("run_id")
@click.option("--mock/--no-mock", default=False, help="Use mock backend (shell echo) for testing")
@click.option("--watch/--no-watch", default=False, help="Live-update phase graph during execution")
def resume(run_id, mock, watch):
    """Resume a crashed loop run."""
    from loopflow.discovery import load_loop
    from loopflow.graph import PhaseGraph
    from loopflow.runtime import RunContext, set_context, set_mock, agent, parallel, pipeline, phase, log, workflow

    if mock:
        set_mock("shell")

    run_dir = _runs_dir() / run_id
    if not run_dir.is_dir():
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
    mod, meta = load_loop(loop_name)
    args_dict = run_meta.get("args", {})

    run_meta["status"] = "running"
    run_json.write_text(json.dumps(run_meta, indent=2))

    # Set up graph for live/watch mode
    pg = PhaseGraph() if watch else None
    live = None
    if watch:
        from rich.live import Live
        from loopflow.display.graph_renderer import TerminalGraphRenderer
        live = Live(TerminalGraphRenderer(pg).render(), refresh_per_second=10,
                     transient=True)
        live.start()

    ctx = RunContext(run_id=run_id, run_dir=run_dir, resume=True, graph=pg, live=live)
    set_context(ctx)

    print(f"[loopflow] Resuming: {loop_name} ({run_id})", file=sys.stderr)

    try:
        result = mod.run(
            agent=agent, parallel=parallel, pipeline=pipeline,
            phase=phase, log=log, args=args_dict, workflow=workflow,
        )
    except Exception as e:
        print(f"[loopflow] Error: {e}", file=sys.stderr)
        run_meta["status"] = "failed"
        run_json.write_text(json.dumps(run_meta, indent=2))
        if live:
            live.stop()
        sys.exit(1)

    if live:
        live.stop()

    run_meta["status"] = "done"
    run_meta["counter"] = ctx._counter
    run_json.write_text(json.dumps(run_meta, indent=2))

    if result is not None:
        if isinstance(result, str):
            print(result)
        elif isinstance(result, dict) and "summary" in result:
            print(result["summary"])
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"[loopflow] Done: {run_id}", file=sys.stderr)

    # Auto-render graph at end
    _print_graph(run_dir)


@main.command()
@click.argument("run_id")
@click.option("--graph/--no-graph", default=True, help="Show phase execution graph")
def status(run_id, graph):
    """Show status of a run."""
    run_dir = _runs_dir() / run_id
    if not run_dir.is_dir():
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
        print(f"  Args:   {json.dumps(meta['args'])}")

    # Show phase graph if events.jsonl exists
    if graph:
        events_path = run_dir / "events.jsonl"
        if events_path.is_file():
            from loopflow.graph import PhaseGraph
            from loopflow.display.graph_renderer import TerminalGraphRenderer

            events = []
            for line in events_path.read_text().strip().split("\n"):
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            pg = PhaseGraph.from_events(events)
            renderer = TerminalGraphRenderer(pg)
            rendered = renderer.render()
            if rendered.plain.strip():
                print(f"\n  Execution graph:")
                print(f"  {rendered.plain}")


@main.command()
def list():
    """List all loops and runs."""
    from loopflow.discovery import list_loops

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
        entries = sorted(runs.iterdir(), reverse=True)
        if not entries:
            print("  (none)")
        for entry in entries:
            rj = entry / "run.json"
            if rj.is_file():
                m = json.loads(rj.read_text())
                print(f"  {m['run_id']}  [{m['status']}]  {m['loop']}  {m['created']}")


@main.command()
@click.argument("run_id")
def stop(run_id):
    """Stop a running loop."""
    run_dir = _runs_dir() / run_id
    if not run_dir.is_dir():
        print(f"Error: run '{run_id}' not found", file=sys.stderr)
        sys.exit(1)

    run_json = run_dir / "run.json"
    if not run_json.is_file():
        print(f"Error: run '{run_id}' has no run.json", file=sys.stderr)
        sys.exit(1)

    meta = json.loads(run_json.read_text())
    if meta["status"] != "running":
        print(f"Run '{run_id}' is not running (status: {meta['status']})", file=sys.stderr)
        sys.exit(0)

    pid_file = run_dir / "loop.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped run '{run_id}' (pid {pid})", file=sys.stderr)
        except (OSError, ValueError):
            print(f"Process not found for run '{run_id}', cleaning up", file=sys.stderr)
            pid_file.unlink()
    else:
        print(f"No pid file for run '{run_id}'", file=sys.stderr)

    meta["status"] = "stopped"
    run_json.write_text(json.dumps(meta, indent=2))