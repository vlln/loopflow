from __future__ import annotations

import http.client
import json
import threading
import time

import pytest

from loopflow.application.web import WebApplication
from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
from loopflow.infrastructure.web_storage import RunRepository
from http.server import ThreadingHTTPServer

from loopflow.presentation.web.server import create_server, handler_for, is_loopback
from tests.web_support.contracts import validate_contract
from tests.web_support.factories import WebFixtureFactory
from tests.web_support.http import JsonHttpClient, parse_sse


class Probe:
    def identity(self, pid):
        return "same" if pid == 7 else None

    def group_id(self, pid):
        return 70 if pid == 7 else None

    def terminate(self, pid):
        return pid == 7

    def terminate_group(self, process_group_id, *, grace_seconds=0.2):
        return "terminated" if process_group_id == 70 else "gone"


class Executor:
    def __init__(self, factory):
        self.factory = factory
        self.count = 0

    def start(self, loop, args, options, run_id=None):
        self.count += 1
        run_id = run_id or f"created-{self.count}"
        path = self.factory.runs / run_id
        path.mkdir(exist_ok=True)
        self.factory.write_json(path / "run.json", {
            "run_id": run_id,
            "loop": loop,
            "args": args,
            "status": "running",
            "created": "2026-07-18T22:00:00Z",
            "execution_epoch": 1,
            "pid": 7,
            "process_group_id": 70,
            "process_started_at": "same",
        })
        return run_id


class DiagnosticBackend(BackendRepository):
    def list(self):
        return []

    def diagnose(self, name, timeout_ms):
        if name == "missing":
            raise KeyError(name)
        return {"name": name, "status": "available", "reason": None, "exit_code": 0, "stdout": "ok", "stderr": "", "diagnosed_at": "now"}


@pytest.fixture
def api(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    factory.create_loop("hello")
    runs = RunRepository(factory.runs, Probe())
    app = WebApplication(runs, LoopRepository(factory.loops, runs), QueueRepository(tmp_path / "queue"), DiagnosticBackend(), Executor(factory), {"kimi"})
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>loopflow</title>")
    (static / "assets" / "app.js").write_text("window.loopflow = true")
    server = create_server("127.0.0.1", 0, application=app, static_root=static)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield JsonHttpClient("127.0.0.1", server.server_port), factory, server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_run_rest_location_filters_and_errors(api):
    client, factory, _ = api
    factory.create_run("done")

    created = client.request("POST", "/api/v1/runs", {"loop": "hello", "args": {}})
    assert created.status == 201
    assert created.headers["location"].endswith(created.json()["run_id"])
    assert client.request("GET", "/api/v1/runs?status=done").json()["items"][0]["run_id"] == "done"
    invalid = client.request("POST", "/api/v1/runs", {"loop": "hello", "unknown": True})
    assert invalid.status == 422 and invalid.json()["error"]["code"] == "validation_failed"
    missing = client.request("GET", "/api/v1/runs/missing")
    assert missing.status == 404 and missing.headers["content-type"] == "application/json; charset=utf-8"


def test_run_lifecycle_commands_preserve_contract(api):
    client, factory, _ = api
    running = factory.create_run("running", status="running", pid=7, process_started_at="same", process_group_id=70)
    failed = factory.create_run("failed", status="failed", args={"attempt": 2})
    done = factory.create_run("done-source", status="done", args={"x": 1})
    stale = factory.create_run("stale", status="running", pid=9, process_started_at="gone")

    stopped = client.request("POST", "/api/v1/runs/running/stop")
    assert stopped.status == 200 and stopped.json()["status"] == "cancelled"
    metadata = json.loads((running / "run.json").read_text())
    assert metadata["finished_at"] and "pid" not in metadata
    metadata["cancel_point"] = "worker_running"
    metadata["active_call_id"] = "0001"
    factory.write_json(running / "run.json", metadata)
    cancelled_recovered = client.request("POST", "/api/v1/runs/running/recover", {"mode": "retry"})
    assert cancelled_recovered.status == 200 and cancelled_recovered.json()["run_id"] == "running"
    recovered = client.request("POST", "/api/v1/runs/failed/recover", {"mode": "retry"})
    assert recovered.status == 200 and recovered.json()["run_id"] == "failed"
    assert client.request("POST", "/api/v1/runs/failed/resume", {}).status == 404
    unsupported = factory.create_run("no-session", status="failed")
    unavailable = client.request("POST", f"/api/v1/runs/{unsupported.name}/recover", {"mode": "continue"})
    assert unavailable.status == 409
    assert unavailable.json()["error"]["code"] == "continue_not_supported"
    rerun = client.request("POST", "/api/v1/runs/done-source/rerun")
    assert rerun.status == 201 and rerun.json()["run_id"] != "done-source"
    reconciled = client.request("POST", "/api/v1/runs/stale/reconcile")
    assert reconciled.status == 200 and reconciled.json()["status"] == "failed"
    conflict = client.request("POST", "/api/v1/runs/done-source/stop")
    assert conflict.status == 409 and conflict.json()["error"]["code"] == "invalid_run_transition"


def test_intervention_endpoints_list_validate_and_respond(api):
    client, factory, _ = api
    waiting = factory.create_run("waiting", status="waiting_input")
    interventions = waiting / "interventions"
    interventions.mkdir()
    factory.write_json(interventions / "approve-1.json", {
        "request_id": "approve-1",
        "key": "approve",
        "prompt": "Approve?",
        "schema": {"type": "boolean"},
        "status": "pending",
        "resume_mode": "replay",
        "call_id": None,
        "created_at": "2026-07-18T22:00:00Z",
        "responded_at": None,
    })

    listed = client.request("GET", "/api/v1/runs/waiting/interventions")
    invalid = client.request(
        "POST",
        "/api/v1/runs/waiting/interventions/approve-1/response",
        {"response": "yes"},
    )
    answered = client.request(
        "POST",
        "/api/v1/runs/waiting/interventions/approve-1/response",
        {"response": True},
    )
    duplicate = client.request(
        "POST",
        "/api/v1/runs/waiting/interventions/approve-1/response",
        {"response": False},
    )
    cancelled = factory.create_run("cancelled-waiting", status="waiting_input")
    cancelled_interventions = cancelled / "interventions"
    cancelled_interventions.mkdir()
    factory.write_json(cancelled_interventions / "approve-2.json", {
        "request_id": "approve-2",
        "key": "approve",
        "prompt": "Approve later?",
        "schema": {"type": "boolean"},
        "status": "pending",
        "resume_mode": "replay",
        "call_id": None,
        "created_at": "2026-07-18T22:00:00Z",
        "responded_at": None,
    })
    stopped = client.request("POST", "/api/v1/runs/cancelled-waiting/stop")
    cancelled_answered = client.request(
        "POST",
        "/api/v1/runs/cancelled-waiting/interventions/approve-2/response",
        {"response": True},
    )

    assert listed.status == 200 and listed.json()["items"][0]["prompt"] == "Approve?"
    validate_contract("intervention", listed.json()["items"][0])
    assert listed.json()["items"][0]["can_continue_session"] is False
    assert invalid.status == 422 and invalid.json()["error"]["code"] == "validation_failed"
    assert answered.status == 200 and answered.json()["run_id"] == "waiting"
    listed_after = client.request("GET", "/api/v1/runs/waiting/interventions")
    validate_contract("intervention", listed_after.json()["items"][0])
    assert listed_after.json()["items"][0]["response"] == "true"
    assert listed_after.json()["items"][0]["responded_at"]
    assert duplicate.status == 409
    assert duplicate.json()["error"]["code"] == "intervention_already_answered"
    assert stopped.status == 200 and stopped.json()["allowed_actions"] == ["recover_retry", "respond", "rerun"]
    assert cancelled_answered.status == 200


def test_batch_intervention_endpoint_is_all_or_nothing(api):
    client, factory, _ = api
    waiting = factory.create_run("batch-waiting", status="waiting_input")
    interventions = waiting / "interventions"
    interventions.mkdir()
    for request_id in ("first", "second"):
        factory.write_json(interventions / f"{request_id}.json", {
            "request_id": request_id,
            "source": "agent",
            "key": request_id,
            "prompt": f"{request_id}?",
            "options": ["yes", "no"],
            "allow_custom": False,
            "schema": None,
            "status": "pending",
            "resume_mode": "continue",
            "call_id": "0001",
            "session_id": "sid-1",
            "created_at": "2026-07-18T22:00:00Z",
            "responded_at": None,
        })
    before = {path.name: path.read_bytes() for path in interventions.glob("*.json")}

    invalid = client.request("POST", "/api/v1/runs/batch-waiting/interventions/responses", {
        "responses": [
            {"request_id": "first", "response": "yes"},
            {"request_id": "second", "response": "other"},
        ]
    })
    assert invalid.status == 422
    assert {path.name: path.read_bytes() for path in interventions.glob("*.json")} == before

    answered = client.request("POST", "/api/v1/runs/batch-waiting/interventions/responses", {
        "responses": [
            {"request_id": "first", "response": "yes"},
            {"request_id": "second", "response": "no"},
        ]
    })
    assert answered.status == 200 and answered.json()["run_id"] == "batch-waiting"


def test_queue_loops_and_backend_endpoints(api):
    client, _, _ = api
    loops = client.request("GET", "/api/v1/loops")
    assert loops.status == 200 and loops.json()["items"][0]["name"] == "hello"
    assert client.request("GET", "/api/v1/loops/hello").status == 200
    queued = client.request("POST", "/api/v1/queue", {"loop": "hello", "priority": 4, "resources": {"repo": "/tmp/project"}})
    assert queued.status == 201 and queued.headers["location"].endswith(queued.json()["task_id"])
    assert client.request("GET", "/api/v1/queue").json()["items"][0]["priority"] == 4
    assert client.request("GET", "/api/v1/backends").json() == {"items": []}
    diagnosed = client.request("POST", "/api/v1/backends/kimi/diagnostics", {"timeout_ms": 100})
    assert diagnosed.status == 200 and diagnosed.json()["exit_code"] == 0


def test_invalid_json_and_request_too_large(api):
    _, _, port = api
    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("POST", "/api/v1/queue", body=b"{", headers={"Content-Type": "application/json", "Content-Length": "1"})
    response = connection.getresponse()
    assert response.status == 400 and json.loads(response.read())["error"]["code"] == "invalid_json"
    connection.close()

    connection = http.client.HTTPConnection("127.0.0.1", port)
    body = b"x" * (1024 * 1024 + 1)
    connection.request("POST", "/api/v1/queue", body=body, headers={"Content-Length": str(len(body))})
    response = connection.getresponse()
    assert response.status == 413 and json.loads(response.read())["error"]["code"] == "request_too_large"
    connection.close()


def test_loop_preview_security_backend_and_static(api, tmp_path):
    client, factory, _ = api
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    factory.create_symlink_escape(factory.loops / "hello", outside)

    assert client.request("GET", "/api/v1/loops/hello/file?path=workflow.py").status == 200
    forbidden = client.request("GET", "/api/v1/loops/hello/file?path=../../outside.txt")
    assert forbidden.status == 403 and b"secret" not in forbidden.body
    assert client.request("GET", "/api/v1/loops/hello/file?path=outside-link").status == 403
    assert client.request("POST", "/api/v1/backends/missing/diagnostics", {"timeout_ms": 100}).status == 404
    assert client.request("GET", "/").status == 200
    assert client.request("GET", "/assets/not-found.js").status == 404


def test_sse_replay_end_cursor_and_legacy(api):
    _, factory, port = api
    run = factory.create_run("events", status="done")
    factory.append_v2_event(run, 1, "log", payload={"message": "one"})
    factory.append_v2_event(run, 2, "log", payload={"message": "two"})

    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", "/api/v1/runs/events/events?last_event_id=1")
    response = connection.getresponse()
    parsed = parse_sse(response.readlines())
    connection.close()
    assert response.status == 200 and [item["event"] for item in parsed] == ["run_event", "stream_end"]
    assert parsed[0]["id"] == "2"

    client = JsonHttpClient("127.0.0.1", port)
    cursor = client.request("GET", "/api/v1/runs/events/events?last_event_id=3")
    assert cursor.status == 410 and cursor.json()["error"]["details"] == {"max_event_id": 2}
    legacy = factory.create_run("legacy")
    factory.append_legacy_event(legacy, {"type": "log", "message": "old"})
    conflict = client.request("GET", "/api/v1/runs/legacy/events")
    assert conflict.status == 409 and conflict.json()["error"]["details"]["legacy_endpoint"].endswith("legacy-events")
    assert client.request("GET", "/api/v1/runs/legacy/legacy-events").status == 200


def test_sse_tails_new_persisted_event_then_ends(api):
    _, factory, port = api
    run = factory.create_run("live", status="running", pid=7, process_started_at="same")
    received = []

    def read_stream():
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        connection.request("GET", "/api/v1/runs/live/events")
        response = connection.getresponse()
        received.extend(parse_sse(response.readlines()))
        connection.close()

    thread = threading.Thread(target=read_stream)
    thread.start()
    time.sleep(0.15)
    factory.append_v2_event(run, 1, "log", payload={"message": "live"})
    metadata = json.loads((run / "run.json").read_text())
    metadata.update({"status": "done", "finished_at": "2026-07-18T22:01:00Z"})
    factory.write_json(run / "run.json", metadata)
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert [item["event"] for item in received] == ["run_event", "stream_end"]


def test_sse_reader_failure_after_headers_emits_stream_error():
    class FailingApplication:
        calls = 0

        def replay_events(self, run_id, cursor):
            self.calls += 1
            if self.calls == 1:
                return [{"version": 2, "event_id": 5, "type": "log", "ts": "now", "run_id": run_id, "payload": {}}], 5, False
            raise OSError("fixture read failure")

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(FailingApplication(), poll_interval=0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/api/v1/runs/run-1/events")
        response = connection.getresponse()
        events = parse_sse(response.readlines())
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert response.status == 200
    assert events[-1] == {"event": "stream_error", "data": '{"code":"event_read_failed","last_event_id":5}'}
    assert [event.get("id") for event in events] == ["5", None]


def test_bind_safety_is_checked_before_socket_creation(monkeypatch):
    assert is_loopback("127.0.0.1") and is_loopback("::1") and is_loopback("localhost")
    assert not is_loopback("0.0.0.0")
    called = []
    monkeypatch.setattr("loopflow.presentation.web.server.ThreadingHTTPServer", lambda *args, **kwargs: called.append(args))
    with pytest.raises(ValueError, match="allow_remote"):
        create_server("0.0.0.0", 8765)
    assert called == []
