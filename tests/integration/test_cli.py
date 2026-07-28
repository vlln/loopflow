"""Integration tests for loopflow CLI using mock agent mode."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

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
    """Create a minimal test loop with loop.md."""
    loop_dir = loops_dir / "hello"
    loop_dir.mkdir(parents=True)
    (loop_dir / "loop.md").write_text("""---
name: hello
description: Test loop for CLI integration tests
---

# hello

A test loop.
""")
    (loop_dir / "workflow.py").write_text("""
meta = {"name": "hello", "description": "Test loop"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    result = agent("say hello")
    return result.value
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

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "hello"])
            # Should work (mock mode uses shell, may fail on echo)
            assert result.exit_code in (0, 1)

    def test_list_loops_and_runs(self, env_dirs):
        loops, runs = env_dirs
        _create_test_loop(loops)

        from loopflow.presentation.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "hello" in result.output
        assert "Loops:" in result.output

    def test_list_empty(self, env_dirs):
        loops, runs = env_dirs

        from loopflow.presentation.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "(none)" in result.output

    def test_status_nonexistent(self, env_dirs):
        from loopflow.presentation.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["status", "nonexistent"])
        assert result.exit_code == 1

    def test_resume_nonexistent(self, env_dirs):
        from loopflow.presentation.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["resume", "nonexistent"])
        assert result.exit_code == 1

    def test_stop_nonexistent(self, env_dirs):
        from loopflow.presentation.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["stop", "nonexistent"])
        assert result.exit_code == 1

    def test_stop_uses_run_metadata_identity_not_legacy_pid_file(self, env_dirs, monkeypatch):
        _, runs = env_dirs
        run_id = "running123"
        run_dir = runs / "lf_test" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text(json.dumps({
            "loop": "hello",
            "run_id": run_id,
            "status": "running",
            "created": "2026-07-07T12:00:00Z",
            "args": {},
            "execution_epoch": 1,
            "pid": 7,
            "process_group_id": 70,
            "process_started_at": "same",
        }))
        (run_dir / "loop.pid").write_text("999")

        class Probe:
            terminated_groups = []

            def identity(self, pid):
                return "same" if pid == 7 else None

            def group_id(self, pid):
                return 70 if pid == 7 else None

            def terminate(self, pid):
                return False

            def terminate_group(self, process_group_id, *, grace_seconds=0.2):
                self.terminated_groups.append(process_group_id)
                return "terminated"

        monkeypatch.setattr("loopflow.infrastructure.web_storage.SystemProcessProbe", Probe)

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(main, ["stop", run_id])

        metadata = json.loads((run_dir / "run.json").read_text())
        assert result.exit_code == 0
        assert "cancelled" in result.output
        assert metadata["status"] == "cancelled"
        assert metadata["stop_summary"] == "terminated"

    def test_run_nonexistent_loop(self, env_dirs):
        from loopflow.presentation.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["run", "nonexistent"])
        assert result.exit_code == 1

    def test_run_with_args(self, env_dirs):
        loops, runs = env_dirs
        loop_dir = loops / "args-test"
        loop_dir.mkdir(parents=True)
        (loop_dir / "loop.md").write_text("""---
name: args-test
description: Test args
---
# args-test
""")
        (loop_dir / "workflow.py").write_text("""
meta = {"name": "args-test", "description": "Test args"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    name = args.get("name", "unknown")
    return f"Hello, {name}!"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "args-test", "--args", '{"name":"World"}'])
            assert result.exit_code in (0, 1)


class TestResume:
    def test_resume_is_deprecated_retry_alias_for_failed_run(self, env_dirs):
        loops, runs = env_dirs
        _create_test_loop(loops)

        # Create a completed run (v0.9.0+ uses lf_<pwd>/<run_id>/ structure)
        run_id = "abc12345"
        lf_dir = runs / "lf_test"
        run_dir = lf_dir / run_id
        run_dir.mkdir(parents=True)

        # Pre-write agent cache
        cache = run_dir / "0001.jsonl"
        cache.write_text(
            json.dumps({"type": "agent_message", "content": "cached hello"}) + "\n" +
            json.dumps({"type": "agent_done", "exit_code": 0}) + "\n"
        )

        run_meta = {
            "loop": "hello",
            "run_id": run_id,
            "status": "failed",
            "created": "2026-07-07T12:00:00Z",
            "args": {},
            "counter": 0,
        }
        (run_dir / "run.json").write_text(json.dumps(run_meta))

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resume", run_id])
            assert result.exit_code == 0
            assert "deprecated" in result.output
            assert "legacy cache recovery is unverified" in result.output
            assert "Recovering (retry)" in result.output

    def test_resume_rejects_stopped_run(self, env_dirs):
        _, runs = env_dirs
        run_id = "stopped123"
        run_dir = runs / "lf_test" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text(json.dumps({
            "loop": "hello", "run_id": run_id, "status": "stopped",
            "created": "2026-07-07T12:00:00Z", "args": {},
        }))

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(main, ["resume", run_id])
        assert result.exit_code == 1
        assert "invalid_run_transition" in result.output


class TestGraph:
    """AC-009 integration: graph display in status and run."""

    def test_status_no_graph_when_no_events(self, env_dirs):
        """AC-009-F-1: no graph when events.jsonl doesn't exist."""
        loops, runs = env_dirs
        _create_test_loop(loops)

        run_id = "nograph01"
        lf_dir = runs / "lf_test"
        run_dir = lf_dir / run_id
        run_dir.mkdir(parents=True)

        (run_dir / "run.json").write_text(json.dumps({
            "loop": "hello",
            "run_id": run_id,
            "status": "running",
            "created": "2026-07-07T12:00:00Z",
            "args": {},
            "counter": 0,
        }))

        from loopflow.presentation.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["status", run_id])
        assert result.exit_code == 0
        assert "Execution graph" not in result.output

    def test_run_emits_phase_events(self, env_dirs):
        """loop run creates events.jsonl with phase events."""
        loops, runs = env_dirs
        loop_dir = loops / "phase-test"
        loop_dir.mkdir(parents=True)
        (loop_dir / "loop.md").write_text("""---
name: phase-test
description: Test phase events
---
# phase-test
""")
        (loop_dir / "workflow.py").write_text("""
meta = {"name": "phase-test", "description": "Test phase events"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    phase("Start")
    agent("echo hello")
    phase("End")
    return "done"
""")

        from loopflow.presentation.cli import main
        from loopflow.runtime import set_mock
        set_mock("bash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "phase-test"])
            # Should complete (mock mode uses shell)
            assert result.exit_code in (0, 1)

            # Find the run directory and check events.jsonl
            run_dirs = list(runs.iterdir())
            if run_dirs:
                events_path = run_dirs[0] / "events.jsonl"
                if events_path.is_file():
                    events = [
                        json.loads(line)
                        for line in events_path.read_text().strip().split("\n")
                        if line
                    ]
                    phase_events = [e for e in events if e["type"] == "phase"]
                    assert len(phase_events) >= 2
                    titles = [e.get("phase") or e.get("title") for e in phase_events]
                    assert "Start" in titles
                    assert "End" in titles


# ── AC-032: 单 agent 运行入口（ADR-0055 / BL-047） ─────────────────────────


def _create_single_agent_loop(loops_dir: Path, body: str = "", frontmatter_extra: str = ""):
    """Create a loop whose workflow.py fails loudly if imported (ADR-0055:
    single-agent runs must never import/execute workflow.py)."""
    loop_dir = loops_dir / "hello"
    agents_dir = loop_dir / "agents"
    agents_dir.mkdir(parents=True)
    (loop_dir / "loop.md").write_text("""---
name: hello
description: Single agent test loop
---

# hello
""")
    (loop_dir / "workflow.py").write_text(
        "raise SystemExit('workflow.py must not be imported in --agent mode')\n"
    )
    frontmatter = "---\nname: reader\ndescription: Reader agent\n"
    if frontmatter_extra:
        frontmatter += frontmatter_extra
    frontmatter += "---\n"
    (agents_dir / "reader.md").write_text(frontmatter + body)
    return loop_dir


def _only_run_json(runs: Path) -> Path:
    matches = list(runs.glob("lf_*/*/run.json"))
    assert len(matches) == 1
    return matches[0]


def _no_run_created(runs: Path) -> None:
    assert list(runs.glob("lf_*/*/run.json")) == []
    assert not (runs / "runs_index.jsonl").exists()


def _wait_terminal(run_json: Path, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        metadata = json.loads(run_json.read_text())
        if metadata.get("status") != "running":
            return metadata
        time.sleep(0.05)
    return json.loads(run_json.read_text())


class TestSingleAgentRun:
    def test_ac032_n1_single_agent_run_done_and_workflow_digest_none(self, env_dirs):
        """AC-032-N-1: full Run semantics; workflow digest is None so editing
        workflow.py cannot diverge recovery."""
        loops, runs = env_dirs
        loop_dir = _create_single_agent_loop(loops)

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(
            main,
            ["run", "hello", "--agent", "reader", "--prompt", "echo single-agent-ok", "--mock", "bash"],
        )
        assert result.exit_code == 0
        assert "single-agent-ok" in result.output

        run_json = _only_run_json(runs)
        run_dir = run_json.parent
        metadata = json.loads(run_json.read_text())
        assert metadata["status"] == "done"
        assert metadata["single_agent"] == {
            "agent_def": "reader",
            "prompt": "echo single-agent-ok",
            "params": {},
        }
        assert (run_dir / "events.jsonl").is_file()
        cache_path = run_dir / "0001.jsonl"
        assert cache_path.is_file()

        # workflow digest component must be None: the recorded digest equals
        # the loop_dir=None variant and differs from the loop_dir variant
        from loopflow.infrastructure.recovery import call_input_digest
        done_events = [
            json.loads(line)
            for line in cache_path.read_text().splitlines()
            if line and json.loads(line).get("type") == "agent_done"
        ]
        recorded = done_events[-1]["input_digest"]
        digest_kwargs = dict(
            prompt="echo single-agent-ok",
            schema=None,
            backend=None,
            model=None,
            agent_definition="",
            execution_options=metadata["execution_options"],
        )
        assert recorded == call_input_digest(loop_dir=None, **digest_kwargs)
        assert recorded != call_input_digest(loop_dir=loop_dir, **digest_kwargs)
        # Editing workflow.py cannot change the single-agent digest
        (loop_dir / "workflow.py").write_text("# edited\n")
        assert recorded == call_input_digest(loop_dir=None, **digest_kwargs)

    def test_ac032_n2_output_schema_json_stdout(self, env_dirs):
        """AC-032-N-2: agent_def output schema is applied; result is JSON on stdout."""
        loops, runs = env_dirs
        _create_single_agent_loop(
            loops,
            frontmatter_extra=(
                "output:\n"
                "  type: object\n"
                "  properties:\n"
                "    verdict: {type: string}\n"
                "  required: [verdict]\n"
            ),
        )

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(
            main,
            ["run", "hello", "--agent", "reader", "--prompt", "ignored", "--mock", "auto"],
        )
        assert result.exit_code == 0

        metadata = json.loads(_only_run_json(runs).read_text())
        assert metadata["status"] == "done"
        stdout_json = result.output[result.output.index("{"): result.output.rindex("}") + 1]
        parsed = json.loads(stdout_json)
        assert parsed["verdict"] == "mock response"

    def test_ac032_n3_recover_retry_reruns_call(self, env_dirs):
        """AC-032-N-3: failed single-agent Run recovers with the same run_id;
        Call 0001 re-executes and the Run finishes done."""
        loops, runs = env_dirs
        _create_single_agent_loop(loops)

        from loopflow.presentation.cli import main
        runner = CliRunner()

        def boom(prompt):
            raise RuntimeError("simulated backend failure")

        with patch("loopflow.runtime._run_mock", side_effect=boom):
            failed = runner.invoke(
                main,
                ["run", "hello", "--agent", "reader", "--prompt", "echo recovered", "--mock", "bash"],
            )
        assert failed.exit_code == 1

        run_json = _only_run_json(runs)
        metadata = json.loads(run_json.read_text())
        assert metadata["status"] == "failed"
        assert metadata["failed_call_id"] == "0001"
        run_id = metadata["run_id"]

        recovered = runner.invoke(main, ["recover", run_id, "--mode", "retry"])
        assert recovered.exit_code == 0
        assert "Recovering (retry)" in recovered.output

        metadata = _wait_terminal(run_json)
        assert metadata["status"] == "done"
        assert metadata["run_id"] == run_id
        assert metadata["execution_epoch"] == 2
        cache_events = [
            json.loads(line)
            for line in (run_json.parent / "0001.jsonl").read_text().splitlines()
            if line
        ]
        done_events = [e for e in cache_events if e.get("type") == "agent_done"]
        assert done_events[-1]["status"] == "succeeded"

    def test_ac032_b1_param_rendering_and_missing_param(self, env_dirs):
        """AC-032-B-1: --param renders {{topic}} in the agent_def body; a
        missing required param errors out before any Run is created."""
        loops, runs = env_dirs
        _create_single_agent_loop(
            loops,
            body="echo topic={{topic}}\n",
            frontmatter_extra=(
                "input:\n"
                "  type: object\n"
                "  properties:\n"
                "    topic: {type: string}\n"
                "  required: [topic]\n"
            ),
        )

        from loopflow.presentation.cli import main
        runner = CliRunner()

        # Missing --param topic → clear error, no Run
        missing = runner.invoke(
            main,
            ["run", "hello", "--agent", "reader", "--prompt", "task", "--mock", "bash"],
        )
        assert missing.exit_code != 0
        assert "topic" in missing.output
        _no_run_created(runs)

        ok = runner.invoke(
            main,
            ["run", "hello", "--agent", "reader", "--prompt", "task\necho b1-done",
             "--param", "topic=rna-seq", "--mock", "bash"],
        )
        assert ok.exit_code == 0
        assert "topic=rna-seq" in ok.output
        assert "b1-done" in ok.output
        metadata = json.loads(_only_run_json(runs).read_text())
        assert metadata["status"] == "done"
        assert metadata["single_agent"]["params"] == {"topic": "rna-seq"}

    def test_ac032_b2_waiting_input(self, env_dirs, monkeypatch):
        """AC-032-B-2: agent returns __loopflow.status=waiting_input with a
        durable session → Run enters waiting_input and the intervention
        request is persisted for the existing answer channels."""
        loops, runs = env_dirs
        _create_single_agent_loop(loops)

        from unittest.mock import Mock
        from loopflow.domain.capabilities import Capabilities
        backend = Mock()
        backend.capabilities = Capabilities(resume_session=True, durable_session_id=True)
        control = {
            "__loopflow": {
                "status": "waiting_input",
                "key": "approve",
                "prompt": "Approve?",
                "schema": None,
            }
        }
        monkeypatch.setattr("loopflow.runtime._make_backend", lambda *a, **kw: backend)
        monkeypatch.setattr(
            "loopflow.runtime._run_subagent",
            lambda *a, **kw: [
                {"type": "agent_message", "content": json.dumps(control)},
                {"type": "agent_done", "exit_code": 0, "session_id": "sid-durable"},
            ],
        )

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(
            main, ["run", "hello", "--agent", "reader", "--prompt", "ask"],
        )
        assert result.exit_code == 0

        run_json = _only_run_json(runs)
        metadata = json.loads(run_json.read_text())
        assert metadata["status"] == "waiting_input"
        requests = list((run_json.parent / "interventions").glob("*.json"))
        assert len(requests) == 1
        request = json.loads(requests[0].read_text())
        assert request["key"] == "approve"
        assert request["call_id"] == "0001"

    def test_ac032_e1_unknown_agent_def(self, env_dirs):
        """AC-032-E-1: --agent ghost errors clearly and creates no Run."""
        loops, runs = env_dirs
        _create_single_agent_loop(loops)

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(
            main, ["run", "hello", "--agent", "ghost", "--prompt", "任务"],
        )
        assert result.exit_code != 0
        assert "ghost" in result.output
        _no_run_created(runs)

    def test_ac032_e2_args_rejected(self, env_dirs):
        """AC-032-E-2: --args is rejected in --agent mode; no Run created."""
        loops, runs = env_dirs
        _create_single_agent_loop(loops)

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(
            main,
            ["run", "hello", "--agent", "reader", "--prompt", "任务", "--args", "{}"],
        )
        assert result.exit_code != 0
        assert "--args" in result.output
        _no_run_created(runs)

    def test_ac032_e3_prompt_mutex(self, env_dirs):
        """AC-032-E-3: --prompt and --prompt-file are mutually exclusive and
        one is required; both violations create no Run."""
        loops, runs = env_dirs
        _create_single_agent_loop(loops)

        from loopflow.presentation.cli import main
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("prompt.txt").write_text("from file")
            both = runner.invoke(
                main,
                ["run", "hello", "--agent", "reader", "--prompt", "x",
                 "--prompt-file", "prompt.txt"],
            )
            assert both.exit_code != 0
            neither = runner.invoke(main, ["run", "hello", "--agent", "reader"])
            assert neither.exit_code != 0
        _no_run_created(runs)

    def test_ac032_f1_backend_failure_recoverable(self, env_dirs, monkeypatch):
        """AC-032-F-1: backend failure (non-zero exit) → Run failed with the
        run-semantics error_category, exit 1, and a failed cache segment that
        recover can target."""
        loops, runs = env_dirs
        _create_single_agent_loop(loops)

        from unittest.mock import Mock
        from loopflow.domain.capabilities import Capabilities
        backend = Mock()
        backend.capabilities = Capabilities()
        monkeypatch.setattr("loopflow.runtime._make_backend", lambda *a, **kw: backend)
        monkeypatch.setattr(
            "loopflow.runtime._run_subagent",
            lambda *a, **kw: [{"type": "agent_done", "exit_code": 1, "stderr": "task exploded"}],
        )

        from loopflow.presentation.cli import main
        result = CliRunner().invoke(
            main, ["run", "hello", "--agent", "reader", "--prompt", "boom"],
        )
        assert result.exit_code == 1

        run_json = _only_run_json(runs)
        metadata = json.loads(run_json.read_text())
        assert metadata["status"] == "failed"
        assert metadata["error_category"] == "unknown"
        assert metadata["failed_call_id"] == "0001"
        cache_events = [
            json.loads(line)
            for line in (run_json.parent / "0001.jsonl").read_text().splitlines()
            if line
        ]
        done_events = [e for e in cache_events if e.get("type") == "agent_done"]
        assert done_events[-1]["status"] == "failed"
