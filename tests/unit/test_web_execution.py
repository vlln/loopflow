import json
import time
from pathlib import Path

import pytest

from loopflow.application.execution import BackgroundRunExecutor, execute_workflow


def create_loop(root):
    loop = root / "hello"
    loop.mkdir(parents=True)
    (loop / "loop.md").write_text("---\nname: hello\nstate:\n  count: 0\n---\n")
    (loop / "workflow.py").write_text(
        "def run(state, **kwargs):\n"
        "    state.count += 1\n"
    )
    return loop


def test_execute_workflow_writes_terminal_metadata_and_v2_phase(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    (loop / "workflow.py").write_text(
        "def run(state, log, **kwargs):\n"
        "    state.count += 1\n"
        "    log('done')\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()

    execute_workflow("hello", {}, {}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    event = json.loads((run / "events.jsonl").read_text())
    assert metadata["status"] == "done" and metadata["finished_at"]
    assert "pid" not in metadata and event["version"] == 2


def test_execute_workflow_terminal_guard_does_not_overwrite_cancelled(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()
    workflow = loop / "workflow.py"
    workflow.write_text(
        "import json\n"
        "def run(args, **kwargs):\n"
        "    path = args['run_json']\n"
        "    data = json.loads(open(path).read())\n"
        "    data['status'] = 'cancelled'\n"
        "    data['finished_at'] = 'stop-won'\n"
        "    open(path, 'w').write(json.dumps(data))\n"
    )

    execute_workflow("hello", {"run_json": str(run / "run.json")}, {}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    assert metadata["status"] == "cancelled"
    assert metadata["finished_at"] == "stop-won"


def test_execute_workflow_recovery_preserves_id_but_restarts_default_state(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({"run_id": "same", "loop": "hello", "status": "failed", "args": {}, "counter": 0, "created": "old"}))
    (run / "state.json").write_text('{"count": 2}')
    workflow = loops / "hello" / "workflow.py"
    workflow.write_text(
        "def run(state, **kwargs):\n"
        "    assert state.count == 0\n"
        "    state.count += 1\n"
    )

    execute_workflow("hello", {}, {"recover": True, "recovery_mode": "retry"}, "same", run)

    metadata = json.loads((run / "run.json").read_text())
    assert metadata["run_id"] == "same" and metadata["status"] == "done"
    assert metadata["execution_epoch"] == 1
    assert metadata["recovery_verification"] == "verified"


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
    # ADR-0054: default isolation — working_directory is run_dir/work, not server cwd
    expected_workdir = str(run_json.parent / "work")
    index = [json.loads(line) for line in (tmp_path / "runs" / "runs_index.jsonl").read_text().splitlines()]
    assert index == [{"working_directory": expected_workdir, "runs_directory": str(run_json.parent.parent), "run_id": run_id}]


def test_recovery_fails_when_workflow_ends_before_target(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({
        "run_id": "same",
        "loop": "hello",
        "status": "failed",
        "args": {},
        "counter": 3,
        "created": "old",
        "failed_call_id": "0003",
        "execution_epoch": 1,
        "execution_options": {},
    }))

    execute_workflow(
        "hello", {}, {"recover": True, "recovery_mode": "retry"}, "same", run
    )

    metadata = json.loads((run / "run.json").read_text())
    assert metadata["status"] == "failed"
    assert metadata["error_summary"] == "replay_diverged"


def test_workflow_intervention_waits_and_replays_answer(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    loop.joinpath("workflow.py").write_text(
        "def run(intervene, state, **kwargs):\n"
        "    state.count = intervene('approve', 'Approve?', {'type': 'boolean'})\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()

    execute_workflow("hello", {}, {}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    request = json.loads(next((run / "interventions").glob("*.json")).read_text())
    assert metadata["status"] == "waiting_input"
    assert request["status"] == "pending"
    request["status"] = "answered"
    request["response"] = True
    request["responded_at"] = "now"
    next((run / "interventions").glob("*.json")).write_text(json.dumps(request))

    execute_workflow("hello", {}, {"recover": True, "recovery_mode": "retry"}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    assert metadata["status"] == "done"
    assert json.loads((run / "state.json").read_text())["count"] is True


def test_workflow_boolean_intervention_summary_exposes_choices(tmp_path, monkeypatch):
    from loopflow.infrastructure.intervention import list_requests

    loops = tmp_path / "loops"
    loop = create_loop(loops)
    loop.joinpath("workflow.py").write_text(
        "def run(intervene, **kwargs):\n"
        "    intervene('approve', 'Approve?', {'type': 'boolean'})\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()

    execute_workflow("hello", {}, {}, "run-1", run)

    request = list_requests(run)[0]
    assert request["options"] == ["true", "false"]
    assert request["allow_custom"] is False


def test_workflow_intervention_replay_diverges_on_prompt_change(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    workflow = loop / "workflow.py"
    workflow.write_text(
        "def run(intervene, **kwargs):\n"
        "    intervene('approve', 'Approve?', {'type': 'boolean'})\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()
    execute_workflow("hello", {}, {}, "run-1", run)
    request_path = next((run / "interventions").glob("*.json"))
    request = json.loads(request_path.read_text())
    request["status"] = "answered"
    request["response"] = True
    request_path.write_text(json.dumps(request))
    workflow.write_text(
        "def run(intervene, **kwargs):\n"
        "    intervene('approve', 'Changed?', {'type': 'boolean'})\n"
    )

    execute_workflow("hello", {}, {"recover": True, "recovery_mode": "retry"}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    assert metadata["status"] == "failed"
    assert metadata["error_summary"] == "replay_diverged"


def test_background_executor_rejects_second_worker_for_same_run(tmp_path):
    run = tmp_path / "runs" / "same"
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({
        "run_id": "same",
        "loop": "hello",
        "status": "failed",
        "args": {},
        "execution_epoch": 2,
    }))
    (run / ".execution.lock").write_text("owner")

    executor = BackgroundRunExecutor(tmp_path / "runs")
    with pytest.raises(RuntimeError, match="invalid_run_transition"):
        executor.start(
            "hello", {}, {"recover": True, "recovery_mode": "retry"}, run_id="same"
        )


def test_background_executor_surfaces_replay_divergence_before_return(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    (loop / "workflow.py").write_text(
        "def run(agent, **kwargs):\n"
        "    agent('current prompt')\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "runs" / "same"
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({
        "run_id": "same",
        "loop": "hello",
        "status": "failed",
        "args": {},
        "counter": 1,
        "created": "old",
        "failed_call_id": "0001",
        "execution_epoch": 1,
        "execution_options": {"mock": "bash"},
    }))
    (run / "0001.jsonl").write_text(
        json.dumps({
            "type": "agent_start",
            "call_id": "0001",
            "input_digest": "sha256:different",
        }) + "\n"
    )

    executor = BackgroundRunExecutor(tmp_path / "runs")
    with pytest.raises(RuntimeError, match="replay_diverged"):
        executor.start(
            "hello", {}, {"recover": True, "recovery_mode": "retry"}, run_id="same"
        )


def _wait_terminal(run_json, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = json.loads(run_json.read_text()).get("status")
        if status != "running":
            return status
        time.sleep(0.01)
    return json.loads(run_json.read_text()).get("status")


def test_background_executor_honors_explicit_working_directory(tmp_path, monkeypatch):
    """AC-025-N-1: run dir lands in the lf_<B> namespace and run.json
    persists the explicit working directory."""
    loops = tmp_path / "loops"
    create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    workdir = tmp_path / "B"
    workdir.mkdir()
    executor = BackgroundRunExecutor(tmp_path / "runs")

    run_id = executor.start("hello", {}, {}, working_directory=str(workdir))

    encoded = str(workdir.resolve()).lstrip("/").replace("/", "-")
    run_json = tmp_path / "runs" / f"lf_{encoded}" / run_id / "run.json"
    assert run_json.is_file()
    assert _wait_terminal(run_json) == "done"
    metadata = json.loads(run_json.read_text())
    assert metadata["working_directory"] == str(workdir.resolve())
    index = [json.loads(line) for line in (tmp_path / "runs" / "runs_index.jsonl").read_text().splitlines()]
    assert index == [{
        "working_directory": str(workdir.resolve()),
        "runs_directory": str(run_json.parent.parent),
        "run_id": run_id,
    }]


def test_run_executes_and_observes_in_explicit_working_directory(tmp_path, monkeypatch):
    """AC-025-N-2: the workflow runs inside /B and file_changes.jsonl records
    /B changes only; pre-existing files are baseline, not created."""
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    (loop / "workflow.py").write_text(
        "from pathlib import Path\n"
        "def run(**kwargs):\n"
        "    Path('output.txt').write_text('made in working dir')\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    workdir = tmp_path / "B"
    workdir.mkdir()
    (workdir / "preexisting.txt").write_text("old")
    executor = BackgroundRunExecutor(tmp_path / "runs")

    run_id = executor.start("hello", {}, {}, working_directory=str(workdir))

    encoded = str(workdir.resolve()).lstrip("/").replace("/", "-")
    run_dir = tmp_path / "runs" / f"lf_{encoded}" / run_id
    assert _wait_terminal(run_dir / "run.json") == "done"
    assert (workdir / "output.txt").read_text() == "made in working dir"
    records = [
        json.loads(line)
        for line in (run_dir / "file_changes.jsonl").read_text().splitlines()
    ]
    changes = [change for record in records for change in record["changes"]]
    assert any(c["path"] == "output.txt" and c["action"] == "created" for c in changes)
    assert all(c["path"] != "preexisting.txt" for c in changes)


def test_recover_reuses_persisted_working_directory(tmp_path, monkeypatch):
    """AC-025-B-3: recovery re-executes in the original directory; a new
    working_directory value never overrides the persisted one."""
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    (loop / "workflow.py").write_text(
        "from pathlib import Path\n"
        "def run(**kwargs):\n"
        "    if not Path('attempt.marker').exists():\n"
        "        Path('attempt.marker').write_text('first')\n"
        "        raise RuntimeError('boom')\n"
        "    Path('recovered.txt').write_text('ok')\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    workdir = tmp_path / "B"
    workdir.mkdir()
    executor = BackgroundRunExecutor(tmp_path / "runs")

    run_id = executor.start("hello", {}, {}, working_directory=str(workdir))
    encoded = str(workdir.resolve()).lstrip("/").replace("/", "-")
    run_json = tmp_path / "runs" / f"lf_{encoded}" / run_id / "run.json"
    assert _wait_terminal(run_json) == "failed"

    executor.start(
        "hello",
        {},
        {"recover": True, "recovery_mode": "retry"},
        run_id=run_id,
        working_directory=str(tmp_path / "nonexistent-override"),
    )

    assert _wait_terminal(run_json) == "done"
    assert (workdir / "recovered.txt").read_text() == "ok"
    metadata = json.loads(run_json.read_text())
    assert metadata["working_directory"] == str(workdir.resolve())


def test_default_working_directory_creates_isolated_dir(tmp_path, monkeypatch):
    """AC-025-N-9: no working_directory → run.json records run_dir/work,
    run dir lands in lf_<server_cwd>/ namespace."""
    loops = tmp_path / "loops"
    create_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    executor = BackgroundRunExecutor(tmp_path / "runs")

    run_id = executor.start("hello", {}, {})
    run_json = next((tmp_path / "runs").glob(f"lf_*/{run_id}/run.json"))
    assert _wait_terminal(run_json) == "done"

    metadata = json.loads(run_json.read_text())
    expected_workdir = str(run_json.parent / "work")
    assert metadata["working_directory"] == expected_workdir
    assert (run_json.parent / "work").is_dir()


def test_default_working_directory_observer_scans_isolated_dir(tmp_path, monkeypatch):
    """AC-025-B-1 / F-3: workflow runs in run_dir/work; file_changes.jsonl
    records files created there, not files in the server cwd."""
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    (loop / "workflow.py").write_text(
        "from pathlib import Path\n"
        "def run(**kwargs):\n"
        "    Path('output.txt').write_text('isolated')\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    # Create a file in the server cwd that the observer should NOT see
    (tmp_path / "external-noise.txt").write_text("noise")
    executor = BackgroundRunExecutor(tmp_path / "runs")

    run_id = executor.start("hello", {}, {})
    run_json = next((tmp_path / "runs").glob(f"lf_*/{run_id}/run.json"))
    assert _wait_terminal(run_json) == "done"

    run_dir = run_json.parent
    assert (run_dir / "work" / "output.txt").read_text() == "isolated"
    records = [
        json.loads(line)
        for line in (run_dir / "file_changes.jsonl").read_text().splitlines()
    ]
    changes = [change for record in records for change in record["changes"]]
    assert any(c["path"] == "output.txt" and c["action"] == "created" for c in changes)
    assert all(c["path"] != "external-noise.txt" for c in changes)


def test_recover_uses_persisted_server_cwd_not_isolated(tmp_path, monkeypatch):
    """AC-025-B-12: old run (ADR-0054 before) with server cwd in run.json
    → recover reuses the persisted value, does not create run_dir/work."""
    loops = tmp_path / "loops"
    loop = create_loop(loops)
    (loop / "workflow.py").write_text(
        "from pathlib import Path\n"
        "def run(**kwargs):\n"
        "    Path('recovered.txt').write_text('ok')\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    executor = BackgroundRunExecutor(tmp_path / "runs")

    # Simulate an old run: create run_dir with run.json that has server cwd
    # as working_directory (pre-ADR-0054 behavior)
    encoded = str(workdir.resolve()).lstrip("/").replace("/", "-")
    run_dir = tmp_path / "runs" / f"lf_{encoded}" / "old-run-001"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "loop": "hello",
        "run_id": "old-run-001",
        "status": "failed",
        "args": {},
        "counter": 0,
        "created": "old",
        "execution_epoch": 1,
        "execution_options": {},
        "working_directory": str(workdir.resolve()),
    }))

    executor.start(
        "hello",
        {},
        {"recover": True, "recovery_mode": "retry"},
        run_id="old-run-001",
    )
    assert _wait_terminal(run_dir / "run.json") == "done"
    # Recover should use the persisted working_directory, not create run_dir/work
    assert not (run_dir / "work").is_dir()
    assert (workdir / "recovered.txt").read_text() == "ok"
