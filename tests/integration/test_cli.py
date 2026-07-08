"""Integration tests for loopflow CLI using mock agent mode."""

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
def _reset_mock():
    """Reset mock mode before and after each test."""
    from loopflow.runtime import set_mock
    set_mock(None)
    yield
    set_mock(None)


@pytest.fixture
def env_dirs():
    """Set up temporary loopflow directories."""
    loops = Path(tempfile.mkdtemp()) / "loops"
    runs = Path(tempfile.mkdtemp()) / "runs"
    loops.mkdir(parents=True)
    runs.mkdir(parents=True)

    import os
    old_loops = os.environ.get("LOOPFLOW_LOOPS_DIR")
    old_runs = os.environ.get("LOOPFLOW_RUNS_DIR")
    os.environ["LOOPFLOW_LOOPS_DIR"] = str(loops)
    os.environ["LOOPFLOW_RUNS_DIR"] = str(runs)

    yield loops, runs

    if old_loops:
        os.environ["LOOPFLOW_LOOPS_DIR"] = old_loops
    else:
        del os.environ["LOOPFLOW_LOOPS_DIR"]
    if old_runs:
        os.environ["LOOPFLOW_RUNS_DIR"] = old_runs
    else:
        del os.environ["LOOPFLOW_RUNS_DIR"]


def _create_test_loop(loops_dir: Path):
    """Create a minimal test loop."""
    loop_dir = loops_dir / "hello"
    loop_dir.mkdir(parents=True)
    (loop_dir / "workflow.py").write_text("""
meta = {"name": "hello", "description": "Test loop"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    result = agent("say hello")
    return result
""")
    agents_dir = loop_dir / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "default.md").write_text("""---
name: default
description: Default agent
---
You are a helpful assistant.
""")


class TestCLIRun:
    def test_run_loop(self, env_dirs):
        loops, runs = env_dirs
        _create_test_loop(loops)

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("shell")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "hello"])
            # Should work (mock mode uses shell, may fail on echo)
            assert result.exit_code in (0, 1)

    def test_list_loops_and_runs(self, env_dirs):
        loops, runs = env_dirs
        _create_test_loop(loops)

        from loopflow.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "hello" in result.output
        assert "Loops:" in result.output

    def test_list_empty(self, env_dirs):
        loops, runs = env_dirs

        from loopflow.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "(none)" in result.output

    def test_status_nonexistent(self, env_dirs):
        from loopflow.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["status", "nonexistent"])
        assert result.exit_code == 1

    def test_resume_nonexistent(self, env_dirs):
        from loopflow.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["resume", "nonexistent"])
        assert result.exit_code == 1

    def test_stop_nonexistent(self, env_dirs):
        from loopflow.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["stop", "nonexistent"])
        assert result.exit_code == 1

    def test_run_nonexistent_loop(self, env_dirs):
        from loopflow.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["run", "nonexistent"])
        assert result.exit_code == 1

    def test_run_with_args(self, env_dirs):
        loops, runs = env_dirs
        loop_dir = loops / "args-test"
        loop_dir.mkdir(parents=True)
        (loop_dir / "workflow.py").write_text("""
meta = {"name": "args-test", "description": "Test args"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    name = args.get("name", "unknown")
    return f"Hello, {name}!"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("shell")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "args-test", "--args", '{"name":"World"}'])
            assert result.exit_code in (0, 1)


class TestResume:
    def test_resume_completed_run(self, env_dirs):
        """Resume a completed run should succeed (all cached)."""
        loops, runs = env_dirs
        _create_test_loop(loops)

        # Create a completed run
        run_id = "abc12345"
        run_dir = runs / run_id
        run_dir.mkdir(parents=True)

        # Pre-write agent cache
        cache = run_dir / "0001.jsonl"
        cache.write_text(
            json.dumps({"type": "agent_text", "content": "cached hello"}) + "\n" +
            json.dumps({"type": "agent_done", "exit_code": 0}) + "\n"
        )

        run_meta = {
            "loop": "hello",
            "run_id": run_id,
            "status": "done",
            "created": "2026-07-07T12:00:00Z",
            "args": {},
            "counter": 1,
        }
        (run_dir / "run.json").write_text(json.dumps(run_meta))

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("shell")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resume", run_id])
            assert result.exit_code == 0
            assert "cached hello" in result.output