import json
import time
from pathlib import Path

from loopflow.application.execution import BackgroundRunExecutor, execute_workflow


def create_loop(root):
    loop = root / "hello"
    loop.mkdir(parents=True)
    (loop / "loop.md").write_text("---\nname: hello\nstate:\n  count: 0\n---\n")
    (loop / "workflow.py").write_text(
        "def run(phase, state, **kwargs):\n"
        "    phase('Work')\n"
        "    state.count += 1\n"
    )
    return loop


def test_execute_workflow_writes_terminal_metadata_and_v2_phase(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()

    execute_workflow("hello", {}, {}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    event = json.loads((run / "events.jsonl").read_text())
    assert metadata["status"] == "done" and metadata["finished_at"]
    assert "pid" not in metadata and event["version"] == 2 and event["phase_id"] == "phase-1"


def test_execute_workflow_resume_preserves_id_and_state(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({"run_id": "same", "loop": "hello", "status": "failed", "args": {}, "counter": 0, "created": "old"}))
    (run / "state.json").write_text('{"count": 2}')

    execute_workflow("hello", {}, {"resume": True}, "same", run)

    assert json.loads((run / "run.json").read_text())["run_id"] == "same"


def test_background_executor_uses_shared_target(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    executor = BackgroundRunExecutor(tmp_path / "runs")

    run_id = executor.start("hello", {}, {})
    run_json = next((tmp_path / "runs").glob(f"lf_*/{run_id}/run.json"))
    deadline = time.monotonic() + 2
    while json.loads(run_json.read_text())["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert json.loads(run_json.read_text())["status"] == "done"
    index = [json.loads(line) for line in (tmp_path / "runs" / "runs_index.jsonl").read_text().splitlines()]
    assert index == [{"working_directory": str(Path.cwd()), "runs_directory": str(run_json.parent.parent), "run_id": run_id}]
