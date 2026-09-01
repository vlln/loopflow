"""BL-062/ADR-0058: rerun_demo_loop real-link black-box coverage.

Runs tests/agent_support/rerun_demo_loop under ``--mock bash`` through the
real CLI, then verifies the validation-driven rerun actually happened:

* Stage "make" runs the probe script — first run fails (exit 1, clears the
  fail-flag), validate() sees make_exit.txt != 0 and returns route_key "make",
  rerun_loop rolls back to "make", the second run succeeds, validate returns
  None, loop completes.
* The rerun trail (status/reruns/stages_run) is persisted via framework State
  into state.json.

No paid backend involved (mock bash only), runs in CI. 与 bio-reproducer 无关。
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

RERUN_LOOP_SRC = Path(__file__).resolve().parent.parent / "agent_support" / "rerun_demo_loop"


@pytest.fixture(autouse=True)
def _reset_mock():
    from loopflow.runtime import set_mock

    set_mock(None)
    yield
    set_mock(None)


@pytest.fixture
def rerun_env(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    runs = tmp_path / "runs"
    loops.mkdir(parents=True)
    runs.mkdir(parents=True)
    shutil.copytree(RERUN_LOOP_SRC, loops / "rerun-demo")
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    monkeypatch.setenv("LOOPFLOW_RUNS_DIR", str(runs))
    return loops, runs


def test_rerun_demo_loop_state_persisted_via_execution(rerun_env):
    """执行路径（execution.py，web/headless 用）下，workflow 级 State 被持久化
    到 state.json——ADR-0058 承诺的「路由事件经框架 State 持久化」落盘验证。

    CLI 路径只做 agent 级 persist（见 presentation/cli.py，无 workflow 级
    state.json 写入）；execution.py 路径在 workflow 返回后强制 persist
    （第 182/384 行），故 rerun 轨迹在此路径可落盘。
    """
    from loopflow.application.execution import execute_workflow

    loops, runs = rerun_env
    run_dir = runs / "exec-run"
    run_dir.mkdir(parents=True)

    old = os.getcwd()
    try:
        os.chdir(run_dir)
        execute_workflow("rerun-demo", {}, {"mock": "bash"}, "exec-run", run_dir)
    finally:
        os.chdir(old)

    metadata = json.loads((run_dir / "run.json").read_text())
    assert metadata["status"] == "done", metadata.get("status")

    state = json.loads((run_dir / "state.json").read_text())
    trail = state["rerun_result"]
    assert trail["status"] == "complete"
    assert trail["reruns"] == 1, f"demo is deterministic (exactly 1 rerun), got {trail}"
    assert trail["stages_run"] == 4, f"demo is deterministic (4 stage runs), got {trail}"

    # execution 路径下工作目录 = run_dir（ADR-0042 working_directory=cwd）
    assert (run_dir / "make_exit.txt").is_file()
    assert (run_dir / "make_exit.txt").read_text().strip() == "0"
    assert not (run_dir / "fail-flag.txt").exists()


def _find_run_dir(runs: Path) -> Path:
    candidates = [p for p in runs.rglob("run.json") if p.parent.name != "work"]
    assert candidates, f"no run.json under {runs}"
    return candidates[0].parent


def test_rerun_demo_loop_blackbox(rerun_env):
    """End-to-end: CLI run (mock bash) → stage A fails → validate routes back
    → stage A succeeds on rerun → done, with State-persisted rerun trail."""
    from loopflow.presentation.cli import main

    loops, runs = rerun_env
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["run", "rerun-demo", "--mock", "bash", "--work-dir", ""])
        assert result.exit_code == 0, result.output

    run_dir = _find_run_dir(runs)
    metadata = json.loads((run_dir / "run.json").read_text())
    assert metadata["status"] == "done", metadata.get("status")

    # 工作目录里应存在退出码文件（最终为 0）与探针产物
    work = run_dir / "work"
    assert (work / "make_exit.txt").is_file(), "make_exit.txt missing"
    assert (work / "make_exit.txt").read_text().strip() == "0"
    # 失败标记在首次运行后被清除（探针自清），不残留
    assert not (work / "fail-flag.txt").exists(), "fail-flag should be consumed"

    # 结构化事件断言（P1-3 修复）：agent_done 退出码序列应如实反映
    # 首轮 make 失败(1) → check(0) → 回退 make 成功(0) → check(0)；
    # 这是 P0-1 修复后的事件语义（此前倒置为 [0,0,127,127]）。
    dones = []
    for line in (run_dir / "events.jsonl").read_text().splitlines():
        ev = json.loads(line)
        if ev.get("type") == "agent_done":
            dones.append(ev.get("payload", {}).get("exit_code"))
    assert dones == [1, 0, 0, 0], f"exit code sequence wrong: {dones}"
    # 4 次 agent 调用 = 2 阶段 × (首轮 + 回退轮)——回退确实发生
    assert len(dones) == 4, f"expected 4 agent calls, got {len(dones)}"
