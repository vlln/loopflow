"""E2E tests for scheduling — enqueue and dispatch end-to-end."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def scheduling_env():
    """Set up temporary loopflow home with loops, queue, locks."""
    home = Path(tempfile.mkdtemp())
    for sub in ["loops", "queue", "locks", "runs"]:
        (home / sub).mkdir(parents=True)

    old_home = os.environ.get("LOOPFLOW_HOME")
    old_loops = os.environ.get("LOOPFLOW_LOOPS_DIR")
    old_runs = os.environ.get("LOOPFLOW_RUNS_DIR")

    os.environ["LOOPFLOW_HOME"] = str(home)
    os.environ["LOOPFLOW_LOOPS_DIR"] = str(home / "loops")
    os.environ["LOOPFLOW_RUNS_DIR"] = str(home / "runs")

    yield home

    if old_home:
        os.environ["LOOPFLOW_HOME"] = old_home
    else:
        del os.environ["LOOPFLOW_HOME"]
    if old_loops:
        os.environ["LOOPFLOW_LOOPS_DIR"] = old_loops
    else:
        del os.environ["LOOPFLOW_LOOPS_DIR"]
    if old_runs:
        os.environ["LOOPFLOW_RUNS_DIR"] = old_runs
    else:
        del os.environ["LOOPFLOW_RUNS_DIR"]


def _create_test_loop(loops_dir: Path):
    """Create a minimal loop with loop.md."""
    loop_dir = loops_dir / "hello"
    loop_dir.mkdir(parents=True)

    (loop_dir / "loop.md").write_text("""---
name: hello
description: Test loop for scheduling e2e
triggers:
  - type: manual
---

# hello

A test loop.
""")

    (loop_dir / "workflow.py").write_text("""
meta = {"name": "hello", "description": "Test loop"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    return agent("say hello")
""")

    agents_dir = loop_dir / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "default.md").write_text("""---
name: default
description: Default agent
---
You are a helpful assistant.
""")


class TestSchedulingE2E:
    """End-to-end: enqueue → dispatch → queue empty."""

    def test_enqueue_then_dispatch(self, scheduling_env):
        """Full cycle: enqueue a task, dispatch it with mock run_func."""
        from loopflow.presentation.cli import main as cli_main
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import list_queue

        loops_dir = scheduling_env / "loops"
        _create_test_loop(loops_dir)

        # 1. Enqueue via CLI
        runner = CliRunner()
        result = runner.invoke(cli_main, ["enqueue", "hello", "--priority", "3"])
        assert result.exit_code == 0

        # 2. Verify queue has 1 entry
        entries = list_queue()
        assert len(entries) == 1
        assert entries[0]["loop"] == "hello"
        assert entries[0]["priority"] == 3

        # 3. Dispatch with mock run function
        calls = []
        def mock_run(loop_name, args):
            calls.append((loop_name, args))

        summary = dispatch(run_func=mock_run)
        assert summary["processed"] == 1
        assert summary["skipped"] == 0
        assert summary["errors"] == 0
        assert len(calls) == 1
        assert calls[0][0] == "hello"

        # 4. Queue is now empty
        assert len(list_queue()) == 0

    def test_enqueue_nonexistent_loop(self, scheduling_env):
        """AC-011-E-1: enqueue nonexistent loop fails."""
        from loopflow.presentation.cli import main as cli_main

        runner = CliRunner()
        result = runner.invoke(cli_main, ["enqueue", "nonexistent"])
        assert result.exit_code != 0

    def test_dispatch_empty_queue(self, scheduling_env):
        """AC-012-N-3: dispatch on empty queue exits cleanly."""
        from loopflow.infrastructure.dispatch import dispatch

        summary = dispatch()
        assert summary["processed"] == 0
        assert summary["skipped"] == 0
        assert summary["errors"] == 0

    def test_dispatch_resource_conflict(self, scheduling_env):
        """AC-012-B-1: a task whose resource is already locked is skipped."""
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, list_queue
        from loopflow.infrastructure.lock import acquire_resource, release_resource

        loops_dir = scheduling_env / "loops"
        _create_test_loop(loops_dir)

        enqueue("hello", resources={"repo": "/same/path"}, priority=1)

        # Simulate another process holding the resource lock
        lock = acquire_resource("repo", "/same/path")

        calls = []
        def mock_run(loop_name, args):
            calls.append(loop_name)

        summary = dispatch(run_func=mock_run)
        assert summary["skipped"] == 1
        assert summary["processed"] == 0
        assert len(calls) == 0

        # Task remains in queue
        assert len(list_queue()) == 1

        # Release the lock, then dispatch again
        release_resource(lock)
        summary2 = dispatch(run_func=mock_run)
        assert summary2["processed"] == 1
        assert summary2["skipped"] == 0
        assert len(list_queue()) == 0

    def test_dispatch_failed_task_removed(self, scheduling_env):
        """AC-012-F-1: failed task is removed from queue."""
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, list_queue

        loops_dir = scheduling_env / "loops"
        _create_test_loop(loops_dir)

        enqueue("hello", priority=1)

        def failing_run(loop_name, args):
            raise RuntimeError("simulated failure")

        summary = dispatch(run_func=failing_run)
        assert summary["errors"] == 1
        assert summary["processed"] == 0

        # Failed task is removed (not retried)
        assert len(list_queue()) == 0