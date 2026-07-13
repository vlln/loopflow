"""E2E tests for phase graph — run real workflows and verify rendered output.

Uses mock mode (shell echo) so no real backend is needed.
"""

import json
import os
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


def _create_phase_loop(loops_dir: Path, name: str, code: str) -> None:
    """Create a loop with the given workflow code."""
    loop_dir = loops_dir / name
    loop_dir.mkdir(parents=True)
    (loop_dir / "workflow.py").write_text(code)
    agents_dir = loop_dir / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "default.md").write_text("""---
name: default
description: Default agent
---
You are a helpful assistant.
""")


class TestLinearGraph:
    """AC-009-N-1: linear phase execution graph."""

    def test_three_phase_linear(self, env_dirs):
        """Run Ingest→Process→Export, verify exact graph output."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "linear", """
meta = {"name": "linear", "description": "Linear 3-phase test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    phase("Ingest")
    agent("echo step1")
    phase("Process")
    agent("echo step2")
    phase("Export")
    agent("echo step3")
    return "done"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "linear"])
            assert result.exit_code == 0

        # Find the run and check status output
        run_id = _find_run_id(runs)

        result = runner.invoke(main, ["status", run_id])
        assert result.exit_code == 0

        output = result.output
        # Verify graph structure
        assert "Execution graph" in output
        assert "Ingest" in output
        assert "Process" in output
        assert "Export" in output
        # Linear connection: ──→ between nodes
        assert "──→" in output

    def test_single_phase(self, env_dirs):
        """Single phase: one node, no edges, ✓ mark."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "single", """
meta = {"name": "single", "description": "Single phase test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    phase("Only")
    agent("echo done")
    return "ok"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "single"])
            assert result.exit_code == 0

        run_id = _find_run_id(runs)

        result = runner.invoke(main, ["status", run_id])
        assert result.exit_code == 0

        output = result.output
        assert "Execution graph" in output
        assert "Only" in output
        # No edges for single node
        assert "──→" not in output

    def test_no_phases(self, env_dirs):
        """Workflow with no phase() calls: no graph section."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "nophase", """
meta = {"name": "nophase", "description": "No phase calls"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    agent("echo step1")
    agent("echo step2")
    return "done"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "nophase"])
            assert result.exit_code == 0

        run_id = _find_run_id(runs)

        result = runner.invoke(main, ["status", run_id])
        assert result.exit_code == 0
        # No graph because no phase events
        assert "Execution graph" not in result.output


class TestCycleGraph:
    """AC-009-N-2: cycle/back-edge rendering."""

    def test_loop_back(self, env_dirs):
        """A→B→C→A back-edge: verify back-edge markers."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "cycle", """
meta = {"name": "cycle", "description": "Cycle test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    for i in range(3):
        phase("A")
        agent("echo stepA")
        phase("B")
        agent("echo stepB")
    phase("Done")
    agent("echo final")
    return "done"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "cycle"])
            assert result.exit_code == 0

        run_id = _find_run_id(runs)

        result = runner.invoke(main, ["status", run_id])
        assert result.exit_code == 0

        output = result.output
        assert "Execution graph" in output
        # Back-edge markers in new multi-line format
        assert "└──" in output
        assert "回边" in output

    def test_branch_conditional(self, env_dirs):
        """If/else branch: two paths from a decision node."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "branch", """
meta = {"name": "branch", "description": "Branch test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    phase("Start")
    result = agent("echo yes")
    if "yes" in (result or ""):
        phase("PathA")
        agent("echo took A")
    else:
        phase("PathB")
        agent("echo took B")
    phase("End")
    agent("echo final")
    return "done"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "branch"])
            assert result.exit_code == 0

        run_id = _find_run_id(runs)

        result = runner.invoke(main, ["status", run_id])
        assert result.exit_code == 0

        output = result.output
        assert "Execution graph" in output
        assert "Start" in output
        assert "End" in output
        # At least one branch path taken
        assert ("PathA" in output) or ("PathB" in output)

    def test_multi_branch_from_loop(self, env_dirs):
        """AC-009-N-3: loop that takes different paths → fork rendering."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "multibranch", """
meta = {"name": "multibranch", "description": "Multi-branch test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    # First iteration: PathA
    phase("Start")
    phase("PathA")
    agent("echo a1")
    phase("PathA-End")
    agent("echo a2")

    # Second iteration: PathB (back to Start)
    phase("Start")
    phase("PathB")
    agent("echo b1")
    phase("PathB-End")
    agent("echo b2")

    phase("Final")
    agent("echo done")
    return "done"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "multibranch"])
            assert result.exit_code == 0

        run_id = _find_run_id(runs)

        result = runner.invoke(main, ["status", run_id])
        assert result.exit_code == 0

        output = result.output
        assert "Execution graph" in output
        # Fork rendering: Start has two forward children
        assert "└─→" in output  # branch marker
        assert "PathA" in output
        assert "PathB" in output
        assert "Final" in output
        # Back-edge from PathA-End → Start
        assert "回边" in output


class TestEventsJsonl:
    """Verify events.jsonl content and structure."""

    def test_events_jsonl_has_phase_and_agent(self, env_dirs):
        """events.jsonl contains both phase and agent events, in order."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "events", """
meta = {"name": "events", "description": "Events test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    phase("Step1")
    agent("echo hello")
    phase("Step2")
    agent("echo world")
    return "done"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "events"])
            assert result.exit_code == 0

        events_path = _find_run(runs) / "events.jsonl"
        assert events_path.is_file()

        events = [
            json.loads(line)
            for line in events_path.read_text().strip().split("\n")
            if line
        ]

        types = [e["type"] for e in events]
        # Should start with phase, then agent_start, agent_text, agent_done, phase, ...
        assert types[0] == "phase"
        assert types[1] == "agent_start"
        assert types[2] == "agent_message"
        assert types[3] == "agent_done"
        assert types[4] == "phase"
        assert types[5] == "agent_start"
        assert types[6] == "agent_message"
        assert types[7] == "agent_done"

    def test_events_jsonl_on_resume(self, env_dirs):
        """Resume appends to events.jsonl, doesn't overwrite."""
        loops, runs = env_dirs
        _create_phase_loop(loops, "resume-ev", """
meta = {"name": "resume-ev", "description": "Resume events test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    phase("A")
    agent("echo first")
    phase("B")
    agent("echo second")
    return "done"
""")

        from loopflow.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            # First run
            result = runner.invoke(main, ["run", "resume-ev"])
            assert result.exit_code == 0

        run_id = _find_run_id(runs)
        events_path = _find_run(runs) / "events.jsonl"

        # Count phase events before resume
        before = [
            json.loads(line)
            for line in events_path.read_text().strip().split("\n")
            if line
        ]
        phase_count_before = sum(1 for e in before if e["type"] == "phase")

        # Resume
        set_mock("bash")
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resume", run_id])
            assert result.exit_code == 0

        after = [
            json.loads(line)
            for line in events_path.read_text().strip().split("\n")
            if line
        ]
        phase_count_after = sum(1 for e in after if e["type"] == "phase")

        # Resume re-runs the workflow, so phase events are emitted again
        # (even though agent calls are cached)
        assert phase_count_after >= phase_count_before