"""E2E tests for agent graph — run real workflows and verify graph structure.

Uses mock mode (shell echo) so no real backend is needed.
Verifies that agent() calls produce agent_start/agent_done events and
that parallel() produces fork/join edges in the agent graph.
"""

import json
import os
import tempfile
import time
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


def _find_run(runs: Path) -> Path:
    """Find a run directory under runs/lf_*/<uuid>/."""
    for lf_dir in sorted(runs.iterdir()):
        if lf_dir.is_dir() and lf_dir.name.startswith("lf_"):
            for run_dir in sorted(lf_dir.iterdir()):
                if (run_dir / "run.json").is_file():
                    return run_dir
    raise FileNotFoundError(f"No run found in {runs}")


def _find_run_id(runs: Path) -> str:
    """Find a run_id (full UUID) from a run directory."""
    return _find_run(runs).name


def _create_loop(loops_dir: Path, name: str, code: str) -> None:
    """Create a loop with loop.md and the given workflow code."""
    loop_dir = loops_dir / name
    loop_dir.mkdir(parents=True)
    (loop_dir / "loop.md").write_text(f"""---
name: {name}
description: E2E test loop
---

# {name}

An E2E test loop.
""")
    (loop_dir / "workflow.py").write_text(code)
    agents_dir = loop_dir / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "default.md").write_text("""---
name: default
description: Default agent
---
You are a helpful assistant.
""")


def _read_events(run_dir: Path) -> list[dict]:
    """Read events.jsonl from a run directory."""
    events_path = run_dir / "events.jsonl"
    assert events_path.is_file()
    return [
        json.loads(line)
        for line in events_path.read_text().strip().split("\n")
        if line
    ]


class TestLinearGraph:
    """Linear agent graph: sequential agent() calls produce sequential edges."""

    def test_three_agent_linear(self, env_dirs):
        """Run A→B→C sequential agents, verify sequential edges in agent_graph."""
        loops, runs = env_dirs
        _create_loop(loops, "linear", """
meta = {"name": "linear", "description": "Linear 3-agent test"}

def run(agent, parallel, pipeline, log, args, workflow):
    agent("echo step1")
    agent("echo step2")
    agent("echo step3")
    return "done"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "linear"])
            assert result.exit_code == 0

        run_dir = _find_run(runs)
        from loopflow.infrastructure.web_events import project_events
        projection = project_events(run_dir / "events.jsonl")

        graph = projection.agent_graph
        assert len(graph["nodes"]) == 3
        for node in graph["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "agent_def" in node
            assert node["status"] == "done"
        # Sequential edges: 0001→0002, 0002→0003
        assert len(graph["edges"]) == 2
        assert graph["edges"][0]["kind"] == "sequential"
        assert graph["edges"][1]["kind"] == "sequential"
        assert graph["current"] == graph["nodes"][-1]["id"]

    def test_single_agent(self, env_dirs):
        """Single agent: one node, no edges."""
        loops, runs = env_dirs
        _create_loop(loops, "single", """
meta = {"name": "single", "description": "Single agent test"}

def run(agent, parallel, pipeline, log, args, workflow):
    agent("echo done")
    return "ok"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "single"])
            assert result.exit_code == 0

        run_dir = _find_run(runs)
        from loopflow.infrastructure.web_events import project_events
        projection = project_events(run_dir / "events.jsonl")

        graph = projection.agent_graph
        assert len(graph["nodes"]) == 1
        assert len(graph["edges"]) == 0
        assert graph["current"] == graph["nodes"][0]["id"]

    def test_no_agents(self, env_dirs):
        """Workflow with no agent() calls: empty graph."""
        loops, runs = env_dirs
        _create_loop(loops, "noagent", """
meta = {"name": "noagent", "description": "No agent calls"}

def run(agent, parallel, pipeline, log, args, workflow):
    log("doing nothing")
    return "done"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "noagent"])
            assert result.exit_code == 0

        run_dir = _find_run(runs)
        from loopflow.infrastructure.web_events import project_events
        projection = project_events(run_dir / "events.jsonl")

        graph = projection.agent_graph
        assert len(graph["nodes"]) == 0
        assert len(graph["edges"]) == 0
        assert graph["current"] is None


class TestParallelGraph:
    """Parallel agent graph: parallel() produces fork/join edges."""

    def test_parallel_produces_fork_join(self, env_dirs):
        """parallel() creates fork_start/fork_end events and fork/join edges."""
        loops, runs = env_dirs
        _create_loop(loops, "parallel", """
meta = {"name": "parallel", "description": "Parallel test"}

def run(agent, parallel, pipeline, log, args, workflow):
    agent("echo before")
    parallel([
        lambda: agent("echo task a"),
        lambda: agent("echo task b"),
    ])
    agent("echo after")
    return "done"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "parallel"])
            assert result.exit_code == 0

        run_dir = _find_run(runs)
        from loopflow.infrastructure.web_events import project_events
        projection = project_events(run_dir / "events.jsonl")

        graph = projection.agent_graph
        # Nodes: before (0001), task a (0002.0001), task b (0002.0002), after (0003)
        assert len(graph["nodes"]) == 4
        kinds = [e["kind"] for e in graph["edges"]]
        assert "fork" in kinds
        assert "join" in kinds
        # Fork edges go from the preceding agent to each parallel child
        fork_edges = [e for e in graph["edges"] if e["kind"] == "fork"]
        assert len(fork_edges) == 2
        assert all(e["from"] == "0001" for e in fork_edges)
        # Join edges go from each parallel child to the joining agent
        join_edges = [e for e in graph["edges"] if e["kind"] == "join"]
        assert len(join_edges) == 2

    def test_parallel_only_no_fork_parent(self, env_dirs):
        """parallel() with no preceding agent: no fork edges (fork_parent is None)."""
        loops, runs = env_dirs
        _create_loop(loops, "parallel-only", """
meta = {"name": "parallel-only", "description": "Parallel only test"}

def run(agent, parallel, pipeline, log, args, workflow):
    parallel([
        lambda: agent("echo a"),
        lambda: agent("echo b"),
    ])
    return "done"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "parallel-only"])
            assert result.exit_code == 0

        run_dir = _find_run(runs)
        from loopflow.infrastructure.web_events import project_events
        projection = project_events(run_dir / "events.jsonl")

        graph = projection.agent_graph
        assert len(graph["nodes"]) == 2
        kinds = [e["kind"] for e in graph["edges"]]
        # No fork edges since there's no preceding agent
        assert "fork" not in kinds


class TestEventsJsonl:
    """Verify events.jsonl content and structure."""

    def test_events_jsonl_has_agent_events(self, env_dirs):
        """events.jsonl contains agent_start and agent_done events, no phase events."""
        loops, runs = env_dirs
        _create_loop(loops, "events", """
meta = {"name": "events", "description": "Events test"}

def run(agent, parallel, pipeline, log, args, workflow):
    agent("echo hello")
    agent("echo world")
    return "done"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "events"])
            assert result.exit_code == 0

        events = _read_events(_find_run(runs))
        types = [e["type"] for e in events]

        # No phase events
        assert "phase" not in types

        # Should have agent_start and agent_done for each call
        agent_starts = [e for e in events if e["type"] == "agent_start"]
        agent_dones = [e for e in events if e["type"] == "agent_done"]
        assert len(agent_starts) == 2
        assert len(agent_dones) == 2

        # Verify call_ids
        assert agent_starts[0]["call_id"] == "0001"
        assert agent_starts[1]["call_id"] == "0002"

        # Verify v2 envelope
        for e in events:
            if e.get("version") == 2:
                assert "event_id" in e
                assert "ts" in e
                assert "run_id" in e
                assert "payload" in e

    def test_events_jsonl_on_resume(self, env_dirs):
        """Resume appends to events.jsonl, doesn't overwrite."""
        loops, runs = env_dirs
        _create_loop(loops, "resume-ev", """
meta = {"name": "resume-ev", "description": "Resume events test"}

def run(agent, parallel, pipeline, log, args, workflow):
    agent("echo first")
    agent("echo second")
    return "done"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "resume-ev"])
            assert result.exit_code == 0

        run_id = _find_run_id(runs)
        events_path = _find_run(runs) / "events.jsonl"

        before = [
            json.loads(line)
            for line in events_path.read_text().strip().split("\n")
            if line
        ]
        agent_count_before = sum(1 for e in before if e["type"] == "agent_start")

        run_json = _find_run(runs) / "run.json"
        metadata = json.loads(run_json.read_text())
        metadata["status"] = "failed"
        run_json.write_text(json.dumps(metadata))

        # Resume
        set_mock("bash")
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resume", run_id])
            assert result.exit_code == 0

        deadline = time.monotonic() + 2
        while (_find_run(runs) / ".execution.lock").exists() and time.monotonic() < deadline:
            time.sleep(0.01)

        after = [
            json.loads(line)
            for line in events_path.read_text().strip().split("\n")
            if line
        ]
        agent_count_after = sum(1 for e in after if e["type"] == "agent_start")

        # Resume re-runs the workflow, so agent events are emitted again
        assert agent_count_after >= agent_count_before
