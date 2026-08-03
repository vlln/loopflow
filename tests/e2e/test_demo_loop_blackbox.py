"""BL-057/058: demo loop real-link black-box coverage.

Runs the real demo loop (tests/agent_support/demo_loop) under ``--mock bash``
through the real CLI, then verifies the two end-to-end links that were
previously only fixture/mock-covered:

* AC-033 binary preview — the assets agent really generates chart.png and
  report.pdf into the run working directory, and the web preview/raw APIs
  serve them with the correct media types.
* AC-023 intervention — the workflow really blocks on ``intervene()``, the
  run enters waiting_input, the web respond API answers it, and the run
  replays to done.

No paid backend is involved (mock bash only), so this runs in CI.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from tests.web_support.http import JsonHttpClient

DEMO_LOOP_SRC = Path(__file__).resolve().parent.parent / "agent_support" / "demo_loop"


@pytest.fixture(autouse=True)
def _reset_mock():
    """Reset mock mode before and after each test."""
    from loopflow.runtime import set_mock

    set_mock(None)
    yield
    set_mock(None)


@pytest.fixture
def demo_env(tmp_path, monkeypatch):
    """Copy the demo loop into a temp loops dir; wire LOOPFLOW_* env vars."""
    loops = tmp_path / "loops"
    runs = tmp_path / "runs"
    loops.mkdir(parents=True)
    runs.mkdir(parents=True)
    shutil.copytree(DEMO_LOOP_SRC, loops / "demo")

    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    monkeypatch.setenv("LOOPFLOW_RUNS_DIR", str(runs))
    return loops, runs


class RecoverableExecutor:
    """Executor that runs workflows in-process and chdirs into the run's
    working directory (CLI already chdir'd; respond recovery must re-chdir)."""

    def __init__(self, runs: Path) -> None:
        self.runs = runs

    def start(self, loop_name, args, options, run_id=None, working_directory=None):
        from loopflow.application.execution import execute_workflow
        from loopflow.infrastructure.web_storage import RunRepository

        actual_id = run_id or "demo-run"
        run_dir = RunRepository(self.runs).find(actual_id)
        if run_dir is None:
            run_dir = self.runs / actual_id
            run_dir.mkdir(parents=True, exist_ok=True)

        cwd = None
        if working_directory is not None:
            cwd = Path(working_directory)
            cwd.mkdir(parents=True, exist_ok=True)
        elif (run_dir / "run.json").is_file():
            meta = json.loads((run_dir / "run.json").read_text())
            wd = meta.get("working_directory")
            if wd:
                cwd = Path(wd)
        old = os.getcwd()
        try:
            if cwd is not None:
                os.chdir(cwd)
            execute_workflow(loop_name, args, options, actual_id, run_dir)
        finally:
            os.chdir(old)
        return actual_id


def _wait_for(predicate, timeout: float = 20.0, interval: float = 0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _find_run_dir(runs: Path) -> Path:
    """Locate the single run dir created by the CLI under runs/."""
    candidates = [
        p
        for p in runs.rglob("run.json")
        if p.parent.name != "work"
    ]
    assert candidates, f"no run.json under {runs}"
    return candidates[0].parent


def _make_web_server(tmp_path, runs: Path):
    """Start a real web server over the shared runs/loops dirs."""
    from loopflow.application.web import WebApplication
    from loopflow.infrastructure.web_resources import (
        LoopRepository,
        QueueRepository,
    )
    from loopflow.infrastructure.web_storage import (
        RunRepository,
        SystemProcessProbe,
    )
    from loopflow.presentation.web.server import create_server

    loops = tmp_path / "loops"
    app = WebApplication(
        RunRepository(runs, SystemProcessProbe()),
        LoopRepository(loops, runs),
        QueueRepository(tmp_path / "queue"),
        None,
        RecoverableExecutor(runs),
        {"kimi"},
    )
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True, exist_ok=True)
    (static / "index.html").write_text("<!doctype html><title>loopflow</title>")
    server = create_server("127.0.0.1", 0, application=app, static_root=static)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, JsonHttpClient("127.0.0.1", server.server_port)


def test_demo_loop_blackbox_ac033_ac023(demo_env):
    """End-to-end: CLI run (mock bash) → waiting_input → web preview (AC-033)
    → web respond (AC-023) → done."""
    from loopflow.presentation.cli import main

    loops, runs = demo_env
    runner = CliRunner()

    # 1. Start the demo loop via the real CLI in a temp cwd (non-tty →
    #    intervene() raises InterventionPending → run stays waiting_input).
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["run", "demo", "--mock", "bash", "--work-dir", ""])
        assert result.exit_code == 0, result.output

    run_dir = _find_run_dir(runs)
    metadata = json.loads((run_dir / "run.json").read_text())
    assert metadata["status"] == "waiting_input"

    # 2. Assets agent really generated binaries into the run working directory.
    work = run_dir / "work"
    assert (work / "chart.png").is_file(), "chart.png missing"
    assert (work / "report.pdf").is_file(), "report.pdf missing"
    assert (work / "chart.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert (work / "report.pdf").read_bytes()[:8] == b"%PDF-1.4"

    # 3. Web server over the same dirs: AC-033 preview + raw.
    server, thread, client = _make_web_server(demo_env[0].parent, runs)
    try:
        preview = client.request("GET", f"/api/v1/runs/{run_dir.name}/file?path=chart.png")
        assert preview.status == 200, preview.body
        preview_json = preview.json()
        assert preview_json["encoding"] == "raw"
        assert preview_json["raw_url"].endswith(
            f"/api/v1/runs/{run_dir.name}/file/raw?path=chart.png"
        )

        raw = client.request("GET", f"/api/v1/runs/{run_dir.name}/file/raw?path=chart.png")
        assert raw.status == 200
        assert raw.headers["content-type"] == "image/png"
        assert raw.body == (work / "chart.png").read_bytes()

        pdf_raw = client.request("GET", f"/api/v1/runs/{run_dir.name}/file/raw?path=report.pdf")
        assert pdf_raw.status == 200
        assert pdf_raw.headers["content-type"] == "application/pdf"
        assert pdf_raw.body == (work / "report.pdf").read_bytes()

        # 4. AC-023: intervention pending, answer via the web API, run recovers.
        interventions = client.request("GET", f"/api/v1/runs/{run_dir.name}/interventions")
        assert interventions.status == 200
        items = interventions.json()["items"]
        assert len(items) == 1, items
        request_id = items[0]["request_id"]
        assert items[0]["prompt"].startswith("批准发布")

        answered = client.request(
            "POST",
            f"/api/v1/runs/{run_dir.name}/interventions/{request_id}/response",
            {"response": "批准"},
        )
        assert answered.status == 200, answered.body

        ok = _wait_for(
            lambda: json.loads((run_dir / "run.json").read_text()).get("status")
            == "done"
        )
        assert ok, "run did not reach done after respond"
        state = json.loads((run_dir / "state.json").read_text())
        assert state["answer"] == "批准"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        from loopflow.runtime import set_mock
        set_mock(None)
