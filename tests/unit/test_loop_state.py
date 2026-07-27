"""AC-027 Loop 失败熔断：loop_state 读写 / 阈值 / 损坏回退 / unpause。"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from loopflow.application.execution import execute_workflow
from loopflow.infrastructure import loop_state


@pytest.fixture
def lf_home(tmp_path, monkeypatch):
    """Isolated loopflow home with LOOPFLOW_HOME / loops dir env."""
    home = tmp_path / "home"
    for sub in ["loops", "queue", "locks", "runs", "loop_state"]:
        (home / sub).mkdir(parents=True)
    monkeypatch.setenv("LOOPFLOW_HOME", str(home))
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(home / "loops"))
    monkeypatch.setenv("LOOPFLOW_RUNS_DIR", str(home / "runs"))
    return home


def _create_loop(loops: Path, name: str = "hello", *, fails: bool = False, frontmatter_extra: str = "") -> Path:
    loop = loops / name
    loop.mkdir(parents=True, exist_ok=True)
    extra = f"\n{frontmatter_extra}" if frontmatter_extra else ""
    (loop / "loop.md").write_text(f"---\nname: {name}{extra}\n---\n\n# {name}\n")
    if fails:
        (loop / "workflow.py").write_text(
            "def run(**kwargs):\n"
            "    raise RuntimeError('boom')\n"
        )
    else:
        (loop / "workflow.py").write_text(
            "def run(**kwargs):\n"
            "    return 'ok'\n"
        )
    return loop


def _read_state(home: Path, loop: str = "hello") -> dict:
    return json.loads((home / "loop_state" / f"{loop}.json").read_text())


class TestLoopStateStore:
    def test_load_missing_returns_initial(self, lf_home):
        state = loop_state.load("hello")
        assert state["consecutive_failures"] == 0
        assert state["paused"] is False
        assert state["paused_reason"] is None
        assert state["paused_at"] is None
        assert state["last_run_id"] is None

    def test_load_corrupted_returns_initial(self, lf_home):
        (lf_home / "loop_state" / "hello.json").write_text("{not json", encoding="utf-8")
        state = loop_state.load("hello")
        assert state["consecutive_failures"] == 0
        assert state["paused"] is False

    def test_record_failure_increments_and_records_run(self, lf_home):
        state = loop_state.record_failure("hello", "run-1")
        assert state["consecutive_failures"] == 1
        assert state["paused"] is False
        assert state["last_run_id"] == "run-1"
        state = loop_state.record_failure("hello", "run-2")
        assert state["consecutive_failures"] == 2
        assert state["last_run_id"] == "run-2"

    def test_record_success_resets_streak_but_keeps_paused(self, lf_home):
        loop_state.record_failure("hello", "run-1")
        state = loop_state.record_success("hello")
        assert state["consecutive_failures"] == 0
        # 解除仅手动（ADR-0045 §4）：done 归零 streak 但不自动清除 paused
        for _ in range(5):
            loop_state.record_failure("hello", "run-x")
        state = loop_state.record_success("hello")
        assert state["consecutive_failures"] == 0
        assert state["paused"] is True

    def test_pause_at_default_threshold(self, lf_home):
        for i in range(4):
            state = loop_state.record_failure("hello", f"run-{i}")
            assert state["paused"] is False
        state = loop_state.record_failure("hello", "run-5")
        assert state["paused"] is True
        assert "failure_streak:5" in state["paused_reason"]
        assert state["paused_at"]

    def test_failure_threshold_meta_override(self, lf_home):
        assert loop_state.failure_threshold({"failure_threshold": 2}) == 2
        state = loop_state.record_failure("hello", "run-1", threshold=2)
        assert state["paused"] is False
        state = loop_state.record_failure("hello", "run-2", threshold=2)
        assert state["paused"] is True
        assert "failure_streak:2" in state["paused_reason"]

    def test_failure_threshold_invalid_falls_back_to_default(self, lf_home):
        for invalid in ("two", 0, -1, 2.5, True, None):
            assert loop_state.failure_threshold({"failure_threshold": invalid}) == 5
        assert loop_state.failure_threshold({}) == 5

    def test_unpause_clears_paused_and_streak(self, lf_home):
        for i in range(5):
            loop_state.record_failure("hello", f"run-{i}")
        state = loop_state.unpause("hello")
        assert state["paused"] is False
        assert state["paused_reason"] is None
        assert state["paused_at"] is None
        assert state["consecutive_failures"] == 0


class TestCircuitBreakerScenarios:
    """AC-027 run 终态计数场景（unit:loop-state）。"""

    def test_ac027_n1_failed_run_increments_streak(self, lf_home, tmp_path):
        _create_loop(lf_home / "loops", fails=True)
        run = tmp_path / "run-1"
        run.mkdir()
        execute_workflow("hello", {}, {}, "run-1", run)
        assert json.loads((run / "run.json").read_text())["status"] == "failed"
        state = _read_state(lf_home)
        assert state["consecutive_failures"] == 1
        assert state["paused"] is False
        assert state["last_run_id"] == "run-1"

    def test_ac027_n2_done_run_resets_streak(self, lf_home, tmp_path):
        loops = lf_home / "loops"
        _create_loop(loops, fails=True)
        run1 = tmp_path / "run-1"
        run1.mkdir()
        execute_workflow("hello", {}, {}, "run-1", run1)
        assert _read_state(lf_home)["consecutive_failures"] == 1
        _create_loop(loops, fails=False)
        run2 = tmp_path / "run-2"
        run2.mkdir()
        execute_workflow("hello", {}, {}, "run-2", run2)
        assert json.loads((run2 / "run.json").read_text())["status"] == "done"
        state = _read_state(lf_home)
        assert state["consecutive_failures"] == 0
        assert state["paused"] is False

    def test_ac027_n3_five_failures_pause_loop(self, lf_home, tmp_path):
        _create_loop(lf_home / "loops", fails=True)
        for i in range(5):
            run = tmp_path / f"run-{i}"
            run.mkdir()
            execute_workflow("hello", {}, {}, f"run-{i}", run)
        state = _read_state(lf_home)
        assert state["paused"] is True
        assert "failure_streak:5" in state["paused_reason"]
        assert state["paused_at"]

    def test_ac027_b1_threshold_frontmatter_override(self, lf_home, tmp_path):
        _create_loop(lf_home / "loops", fails=True, frontmatter_extra="failure_threshold: 2")
        for i in range(2):
            run = tmp_path / f"run-{i}"
            run.mkdir()
            execute_workflow("hello", {}, {}, f"run-{i}", run)
        state = _read_state(lf_home)
        assert state["paused"] is True
        assert "failure_streak:2" in state["paused_reason"]

    def test_ac027_f1_manual_run_failure_counts(self, lf_home):
        """手动 `loopflow run` 触发的失败同样计入 streak。"""
        from loopflow.presentation.cli import main as cli_main

        _create_loop(lf_home / "loops", fails=True)
        result = CliRunner().invoke(cli_main, ["run", "hello"])
        assert result.exit_code == 1
        state = _read_state(lf_home)
        assert state["consecutive_failures"] == 1
        assert state["paused"] is False


class TestUnpauseCli:
    def test_ac027_b2_unpause_clears_and_dispatch_resumes(self, lf_home):
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, list_queue
        from loopflow.presentation.cli import main as cli_main

        _create_loop(lf_home / "loops")
        for i in range(5):
            loop_state.record_failure("hello", f"run-{i}")
        assert loop_state.load("hello")["paused"] is True

        result = CliRunner().invoke(cli_main, ["unpause", "hello"])
        assert result.exit_code == 0
        state = _read_state(lf_home)
        assert state["paused"] is False
        assert state["consecutive_failures"] == 0

        # dispatch 恢复消费该 loop 任务
        enqueue("hello")
        calls = []
        summary = dispatch(run_func=lambda loop, args: calls.append(loop))
        assert summary["processed"] == 1
        assert summary["deferred"] == 0
        assert calls == ["hello"]
        assert list_queue() == []

    def test_unpause_nonexistent_loop_errors(self, lf_home):
        from loopflow.presentation.cli import main as cli_main

        result = CliRunner().invoke(cli_main, ["unpause", "nonexistent"])
        assert result.exit_code != 0
        assert "loop_not_found" in result.output or "not found" in result.output
