import json

import pytest

from loopflow.application.web import ApplicationError, WebApplication
from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
from loopflow.infrastructure.web_storage import RunRepository
from tests.web_support.factories import WebFixtureFactory


class Probe:
    def __init__(self):
        self.identities = {}
        self.terminated = []

    def identity(self, pid):
        return self.identities.get(pid)

    def terminate(self, pid):
        self.terminated.append(pid)
        return True


class Executor:
    def __init__(self, factory):
        self.factory = factory
        self.calls = []

    def start(self, loop, args, options, run_id=None):
        run_id = run_id or f"new-{len(self.calls)}"
        self.calls.append((loop, args, options, run_id))
        run = self.factory.runs / run_id
        run.mkdir(exist_ok=True)
        self.factory.write_json(run / "run.json", {"run_id": run_id, "loop": loop, "args": args, "status": "running", "created": "2026-07-18T22:00:00Z", "pid": 7, "process_started_at": "same"})
        return run_id


def app(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    factory.create_loop("hello")
    probe = Probe()
    probe.identities[7] = "same"
    runs = RunRepository(factory.runs, probe)
    return WebApplication(runs, LoopRepository(factory.loops, runs), QueueRepository(tmp_path / "queue"), BackendRepository(), Executor(factory), {"kimi"}), factory, probe


def test_pagination_filters_and_bad_cursor(tmp_path):
    service, factory, _ = app(tmp_path)
    factory.create_run("a", loop="hello")
    factory.create_run("b", loop="other", status="failed")

    first = service.list_runs(limit=1)
    assert len(first["items"]) == 1 and first["next_cursor"]
    assert len(service.list_runs(limit=1, cursor=first["next_cursor"])["items"]) == 1
    assert [item["run_id"] for item in service.list_runs(statuses=["failed"])["items"]] == ["b"]
    with pytest.raises(ApplicationError, match="cursor"):
        service.list_runs(cursor="bad!")


def test_create_stop_recover_rerun_and_invalid_transition(tmp_path):
    service, factory, probe = app(tmp_path)
    created = service.create_run({"loop": "hello", "args": {}, "backend": "kimi"})
    assert created["status"] == "running"
    stopped = service.stop_run(created["run_id"])
    assert stopped["status"] == "stopped" and probe.terminated == [7]
    with pytest.raises(ApplicationError) as stopped_recovery:
        service.recover_run(created["run_id"], {"mode": "retry"})
    assert stopped_recovery.value.code == "invalid_run_transition"
    failed = factory.create_run("failed", status="failed")
    recovered = service.recover_run(failed.name, {"mode": "retry"})
    assert recovered["run_id"] == failed.name and recovered["status"] == "running"
    assert service.executor.calls[-1][2] == {"recover": True, "recovery_mode": "retry"}


def test_continue_requires_durable_session_and_concurrent_recovery_is_rejected(tmp_path):
    service, factory, _ = app(tmp_path)
    unsupported = factory.create_run("unsupported", status="failed")
    with pytest.raises(ApplicationError) as capability_error:
        service.recover_run(unsupported.name, {"mode": "continue"})
    assert capability_error.value.code == "continue_not_supported"
    assert service.executor.calls == []

    durable = factory.create_run("durable", status="failed")
    metadata = json.loads((durable / "run.json").read_text())
    metadata["can_recover_continue"] = True
    factory.write_json(durable / "run.json", metadata)
    service.executor.start = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("invalid_run_transition")
    )
    with pytest.raises(ApplicationError) as transition_error:
        service.recover_run(durable.name, {"mode": "continue"})
    assert transition_error.value.code == "invalid_run_transition"

    service.executor.start = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("replay_diverged")
    )
    with pytest.raises(ApplicationError) as replay_error:
        service.recover_run(durable.name, {"mode": "retry"})
    assert replay_error.value.code == "replay_diverged"
    with pytest.raises(ApplicationError) as error:
        service.stop_run(factory.create_run("done").name)
    assert error.value.code == "invalid_run_transition"


def test_rerun_preserves_source_and_queue_validates(tmp_path):
    service, factory, _ = app(tmp_path)
    source = factory.create_run("done", args={"x": 1})
    before = (source / "run.json").read_bytes()
    rerun = service.rerun("done")
    assert rerun["run_id"] != "done" and (source / "run.json").read_bytes() == before
    queued = service.enqueue({"loop": "hello", "resources": {"repo": "/tmp/project"}})
    assert queued["loop"] == "hello"
    with pytest.raises(ApplicationError) as error:
        service.enqueue({"loop": "missing"})
    assert error.value.code == "loop_not_found"


def test_unknown_fields_and_only_phase_conflict(tmp_path):
    service, _, _ = app(tmp_path)
    with pytest.raises(ApplicationError) as error:
        service.create_run({"loop": "hello", "surprise": True})
    assert error.value.details == {"fields": ["surprise"]}
    with pytest.raises(ApplicationError):
        service.create_run({"loop": "hello", "from_phase": "A", "only_phase": "B"})


def test_loop_queries_preview_queue_pages_and_not_found(tmp_path):
    service, _, _ = app(tmp_path)
    assert service.list_loops(q="HEL")["items"][0]["name"] == "hello"
    assert service.get_loop("hello")["files"]
    assert service.preview_loop_file("hello", "workflow.py")["media_type"] == "text/x-python"
    service.enqueue({"loop": "hello", "priority": 1})
    service.enqueue({"loop": "hello", "priority": 2})
    first = service.list_queue(limit=1)
    assert first["items"][0]["priority"] == 1
    assert service.list_queue(limit=1, cursor=first["next_cursor"])["items"][0]["priority"] == 2
    with pytest.raises(ApplicationError) as error:
        service.get_loop("missing")
    assert error.value.code == "loop_not_found"


def test_reconcile_and_validation_edges(tmp_path):
    service, factory, _ = app(tmp_path)
    factory.create_run("stale", status="running", pid=99, process_started_at="gone")
    assert service.reconcile("stale")["status"] == "failed"
    with pytest.raises(ApplicationError) as error:
        service.reconcile("stale")
    assert error.value.code == "run_not_stale"
    for body in (
        {"loop": "hello", "args": []},
        {"loop": "hello", "backend": "unknown"},
        {"loop": "hello", "model": ""},
        {"loop": "hello", "mock": "other"},
    ):
        with pytest.raises(ApplicationError) as invalid:
            service.create_run(body)
        assert invalid.value.code == "validation_failed"
    with pytest.raises(ApplicationError):
        service.enqueue({"loop": "hello", "priority": 101})
