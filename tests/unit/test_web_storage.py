import json
from pathlib import Path

import pytest

from loopflow.infrastructure.web_storage import RunRepository, append_run_index, atomic_write_json, read_run_index
from tests.web_support.factories import WebFixtureFactory


class Probe:
    def __init__(self, identities=None):
        self.identities = identities or {}
        self.terminated = []

    def identity(self, pid):
        return self.identities.get(pid)

    def terminate(self, pid):
        self.terminated.append(pid)
        return True


def test_unreadable_run_does_not_hide_valid_siblings(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    factory.create_run("valid")
    factory.create_unreadable_run("broken")
    repository = RunRepository(factory.runs, Probe())

    summaries = {path.name: repository.read_summary(path) for path in repository.list_dirs()}

    assert summaries["valid"]["status"] == "done"
    assert summaries["broken"]["status"] == "unreadable"
    assert summaries["broken"]["parse_error"].startswith("line 1, column")
    assert summaries["valid"]["working_directory"] == factory.runs.name
    assert summaries["broken"]["working_directory"] == factory.runs.name


def test_stale_is_derived_without_modifying_run_json(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    run = factory.create_run("stale", status="running", pid=123, process_started_at="old")
    before = (run / "run.json").read_bytes()

    summary = RunRepository(factory.runs, Probe()).read_summary(run)

    assert summary["status"] == "stale"
    assert summary["allowed_actions"] == ["reconcile"]
    assert (run / "run.json").read_bytes() == before


def test_matching_pid_and_identity_remains_running(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    run = factory.create_run("active", status="running", pid=123, process_started_at="same")

    summary = RunRepository(factory.runs, Probe({123: "same"})).read_summary(run)

    assert summary["status"] == "running"
    assert summary["allowed_actions"] == ["stop"]


def test_reconcile_atomically_fails_stale_run_and_clears_identity(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    run = factory.create_run("stale", status="running", pid=123, process_started_at="old")

    summary = RunRepository(factory.runs, Probe()).reconcile(run)
    metadata = json.loads((run / "run.json").read_text())

    assert summary["status"] == "failed"
    assert "pid" not in metadata and "process_started_at" not in metadata
    assert metadata["finished_at"] and metadata["updated_at"]
    assert not list(run.glob("*.tmp"))


def test_reconcile_rechecks_live_process_and_preserves_bytes(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    run = factory.create_run("active", status="running", pid=123, process_started_at="same")
    before = (run / "run.json").read_bytes()

    with pytest.raises(RuntimeError, match="process_alive"):
        RunRepository(factory.runs, Probe({123: "same"})).reconcile(run)

    assert (run / "run.json").read_bytes() == before


def test_atomic_write_failure_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "run.json"
    atomic_write_json(path, {"status": "done"})
    before = path.read_bytes()

    def fail_replace(source, target):
        raise OSError("fixture replace failed")

    monkeypatch.setattr("loopflow.infrastructure.web_storage.os.replace", fail_replace)
    with pytest.raises(OSError, match="fixture replace failed"):
        atomic_write_json(path, {"status": "failed"})
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_run_detail_missing_events_and_state_and_find_nested(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    nested = factory.runs / "lf-project" / "nested"
    nested.mkdir(parents=True)
    factory.write_json(nested / "run.json", {"run_id": "nested", "loop": "hello", "status": "done"})
    repository = RunRepository(factory.runs, Probe())

    detail = repository.read_detail(repository.find("nested"))

    assert detail["working_directory"] == "lf-project"
    assert detail["state"] is None
    assert detail["events"] == [] and detail["graph"]["nodes"] == []
    assert detail["allowed_actions"] == ["rerun"]


def test_run_index_preserves_real_working_directory(tmp_path):
    runs = tmp_path / "runs"
    run = runs / "lf_Users-vlln-agent-space" / "indexed"
    run.mkdir(parents=True)
    (run / "run.json").write_text('{"run_id":"indexed","status":"done"}')
    repository = RunRepository(runs, Probe())
    assert repository.read_summary(run)["working_directory"] == "lf_Users-vlln-agent-space"

    append_run_index(runs, Path("/Users/vlln/agent-space"), run.parent, "indexed")

    record = read_run_index(runs)["indexed"]
    assert record == {
        "working_directory": "/Users/vlln/agent-space",
        "runs_directory": str(run.parent.resolve()),
        "run_id": "indexed",
    }
    assert repository.find("indexed") == run
    assert repository.read_summary(run)["working_directory"] == "/Users/vlln/agent-space"


def test_run_index_ignores_malformed_and_outside_records(tmp_path):
    runs = tmp_path / "runs"
    run = runs / "lf-project" / "safe"
    run.mkdir(parents=True)
    (run / "run.json").write_text('{"run_id":"safe","status":"done"}')
    outside = tmp_path / "outside"
    (outside / "safe").mkdir(parents=True)
    (outside / "safe" / "run.json").write_text('{"run_id":"safe"}')
    (runs / "runs_index.jsonl").write_text(
        '{broken\n'
        + json.dumps({"working_directory": "/outside", "runs_directory": str(outside), "run_id": "safe"})
        + "\n"
    )

    repository = RunRepository(runs, Probe())
    assert repository.find("safe") == run
    assert repository.read_summary(run)["working_directory"] == "lf-project"
