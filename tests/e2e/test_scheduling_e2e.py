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
        assert summary["deferred"] == 1
        assert summary["skipped"] == 0
        assert summary["processed"] == 0
        assert len(calls) == 0

        # Task remains in queue, marked deferred with a reason
        entries = list_queue()
        assert len(entries) == 1
        assert entries[0]["status"] == "deferred"
        assert entries[0]["status_reason"]

        # Release the lock, then dispatch again
        release_resource(lock)
        summary2 = dispatch(run_func=mock_run)
        assert summary2["processed"] == 1
        assert summary2["deferred"] == 0
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

class TestQueueTaskStatus:
    """AC-028: 队列任务显式状态（pending/deferred/superseded）。"""

    def test_enqueue_writes_pending_status(self, scheduling_env):
        """AC-028-N-1: enqueue 后任务 JSON 含 status=pending。"""
        from loopflow.presentation.cli import main as cli_main

        _create_test_loop(scheduling_env / "loops")

        runner = CliRunner()
        result = runner.invoke(cli_main, ["enqueue", "hello"])
        assert result.exit_code == 0

        files = list((scheduling_env / "queue").glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["status"] == "pending"

    def test_dispatch_defers_task_when_resource_locked(self, scheduling_env):
        """AC-028-N-2: 资源锁被持有 → deferred + status_reason 留队；锁释放后正常执行。"""
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, list_queue
        from loopflow.infrastructure.lock import acquire_resource, release_resource

        _create_test_loop(scheduling_env / "loops")
        enqueue("hello", resources={"repo": "/same/path"}, priority=1)

        lock = acquire_resource("repo", "/same/path")

        calls = []
        summary = dispatch(run_func=lambda loop, args: calls.append(loop))
        assert summary["deferred"] == 1
        assert summary["processed"] == 0
        assert summary["errors"] == 0
        assert calls == []

        entries = list_queue()
        assert len(entries) == 1
        assert entries[0]["status"] == "deferred"
        assert entries[0]["status_reason"]

        release_resource(lock)
        summary2 = dispatch(run_func=lambda loop, args: calls.append(loop))
        assert summary2["processed"] == 1
        assert summary2["deferred"] == 0
        assert calls == ["hello"]
        assert list_queue() == []

    def test_enqueue_supersede_marks_existing_task(self, scheduling_env):
        """AC-028-N-3: --supersede 将同 loop pending 任务 A 标记 superseded，B 为 pending。"""
        from loopflow.presentation.cli import main as cli_main
        from loopflow.infrastructure.queue import enqueue

        _create_test_loop(scheduling_env / "loops")
        path_a = enqueue("hello", priority=1)

        runner = CliRunner()
        result = runner.invoke(cli_main, ["enqueue", "hello", "--supersede"])
        assert result.exit_code == 0

        files = list((scheduling_env / "queue").glob("*.json"))
        assert len(files) == 2
        path_b = next(f for f in files if f != path_a)

        data_a = json.loads(path_a.read_text())
        data_b = json.loads(path_b.read_text())
        assert data_a["status"] == "superseded"
        assert data_a["superseded_by"] == path_b.stem
        assert data_b["status"] == "pending"

    def test_dispatch_skips_and_cleans_superseded(self, scheduling_env):
        """AC-028-N-4: superseded 任务被跳过并清理，仅 pending 执行；superseded 不计 errors。"""
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, mark_status, list_queue

        _create_test_loop(scheduling_env / "loops")
        path_a = enqueue("hello", priority=1)
        path_b = enqueue("hello", priority=2)
        mark_status(path_a, "superseded", superseded_by=path_b.stem)

        calls = []
        summary = dispatch(run_func=lambda loop, args: calls.append(loop))
        assert summary["superseded"] == 1
        assert summary["processed"] == 1
        assert summary["errors"] == 0
        assert calls == ["hello"]

        assert not path_a.exists()
        entries = list_queue()
        assert entries == []

    def test_enqueue_supersede_without_existing_task(self, scheduling_env):
        """AC-028-B-1: 队列中无同 loop 任务时 --supersede 与正常入队一致。"""
        from loopflow.presentation.cli import main as cli_main

        _create_test_loop(scheduling_env / "loops")

        runner = CliRunner()
        result = runner.invoke(cli_main, ["enqueue", "hello", "--supersede"])
        assert result.exit_code == 0

        files = list((scheduling_env / "queue").glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["status"] == "pending"
        assert "superseded_by" not in data

    def test_dispatch_treats_unknown_or_missing_status_as_pending(self, scheduling_env):
        """AC-028-E-1: 未知/缺失 status 按 pending 处理，正常消费不阻塞。"""
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import list_queue

        _create_test_loop(scheduling_env / "loops")
        base = {"loop": "hello", "args": {}, "resources": {},
                "priority": 5, "created": "2026-07-25T00:00:00Z"}
        (scheduling_env / "queue" / "unknown.json").write_text(
            json.dumps({**base, "status": "unknown_state"}))
        (scheduling_env / "queue" / "legacy.json").write_text(json.dumps(base))

        calls = []
        summary = dispatch(run_func=lambda loop, args: calls.append(loop))
        assert summary["processed"] == 2
        assert summary["errors"] == 0
        assert len(calls) == 2
        assert list_queue() == []

    def test_dispatch_deferred_and_superseded_not_counted_as_errors(self, scheduling_env):
        """AC-028-F-1: deferred 与 superseded 分别计数，均不计入 errors。"""
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, mark_status, list_queue
        from loopflow.infrastructure.lock import acquire_resource, release_resource

        _create_test_loop(scheduling_env / "loops")
        path_deferred = enqueue("hello", resources={"repo": "/locked/path"}, priority=1)
        path_superseded = enqueue("hello", priority=2)
        mark_status(path_superseded, "superseded", superseded_by=path_deferred.stem)

        lock = acquire_resource("repo", "/locked/path")
        try:
            summary = dispatch(run_func=lambda loop, args: None)
        finally:
            release_resource(lock)

        assert summary["errors"] == 0
        assert summary["deferred"] == 1
        assert summary["superseded"] == 1

        assert not path_superseded.exists()
        entries = list_queue()
        assert len(entries) == 1
        assert entries[0]["status"] == "deferred"


class TestLoopCircuitBreaker:
    """AC-027 调度链路场景：paused loop 的 dispatch 语义与手动 run 不拦截。"""

    def test_ac027_n4_paused_loop_task_deferred_not_error(self, scheduling_env):
        """paused loop 的队列任务 mark deferred 留队，status_reason 含暂停原因，不计 errors。"""
        from loopflow.infrastructure import loop_state
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, list_queue

        _create_test_loop(scheduling_env / "loops")
        for i in range(5):
            loop_state.record_failure("hello", f"run-{i}")
        assert loop_state.load("hello")["paused"] is True

        enqueue("hello", priority=1)

        calls = []
        summary = dispatch(run_func=lambda loop, args: calls.append(loop))
        assert summary["processed"] == 0
        assert summary["errors"] == 0
        assert summary["deferred"] == 1
        assert calls == []

        entries = list_queue()
        assert len(entries) == 1
        assert entries[0]["status"] == "deferred"
        assert "failure_streak:5" in entries[0]["status_reason"]

    def test_ac027_e1_corrupted_loop_state_treated_as_initial(self, scheduling_env):
        """loop_state 损坏或缺失按初始状态处理，dispatch 正常执行不报错。"""
        from loopflow.infrastructure.dispatch import dispatch
        from loopflow.infrastructure.queue import enqueue, list_queue

        _create_test_loop(scheduling_env / "loops")
        state_dir = scheduling_env / "loop_state"
        state_dir.mkdir(exist_ok=True)
        (state_dir / "hello.json").write_text("{corrupted", encoding="utf-8")

        enqueue("hello", priority=1)

        calls = []
        summary = dispatch(run_func=lambda loop, args: calls.append(loop))
        assert summary["processed"] == 1
        assert summary["errors"] == 0
        assert calls == ["hello"]
        assert list_queue() == []

    def test_ac027_b3_manual_run_not_blocked_by_pause(self, scheduling_env):
        """paused 时手动 `loopflow run hello` 正常执行，不被熔断拦截。"""
        from loopflow.infrastructure import loop_state
        from loopflow.presentation.cli import main as cli_main

        loops_dir = scheduling_env / "loops"
        loop_dir = loops_dir / "hello"
        loop_dir.mkdir(parents=True)
        (loop_dir / "loop.md").write_text("""---
name: hello
description: Manual run while paused
---

# hello
""")
        (loop_dir / "workflow.py").write_text(
            "def run(**kwargs):\n"
            "    return 'ok'\n"
        )
        for i in range(5):
            loop_state.record_failure("hello", f"run-{i}")
        assert loop_state.load("hello")["paused"] is True

        result = CliRunner().invoke(cli_main, ["run", "hello"])
        assert result.exit_code == 0
        # 手动 done 归零 streak 但不自动解除 paused（ADR-0045 §4）
        state = loop_state.load("hello")
        assert state["consecutive_failures"] == 0
        assert state["paused"] is True
