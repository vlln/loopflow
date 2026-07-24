from __future__ import annotations

import http.client
import json
import subprocess
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
        self.working_directories = []

    def start(self, loop, args, options, run_id=None, working_directory=None):
        self.count += 1
        self.working_directories.append(working_directory)
        run_id = run_id or f"created-{self.count}"
        path = self.factory.runs / run_id
        path.mkdir(exist_ok=True)
        metadata = {
            "run_id": run_id,
            "loop": loop,
            "args": args,
            "status": "running",
            "created": "2026-07-18T22:00:00Z",
            "execution_epoch": 1,
            "pid": 7,
            "process_group_id": 70,
            "process_started_at": "same",
        }
        if working_directory is not None:
            metadata["working_directory"] = working_directory
        self.factory.write_json(path / "run.json", metadata)
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


# --- Multi-topic SSE tests (ADR-0041) ---


def test_sse_multi_topic_pushes_run_event_and_file_changes(api):
    """AC-016-N-3: same connection receives run_event and file_changes with independent ids."""
    _, factory, port = api
    run = factory.create_run("multi", status="done")
    factory.append_v2_event(run, 1, "log", payload={"message": "one"})
    factory.append_v2_event(run, 2, "phase", phase="采集", phase_id="p1", payload={})
    factory.append_file_changes(run, 1, "采集", "p1", [{"path": "data.json", "action": "created", "size": 100}])
    factory.append_file_changes(run, 2, "处理", "p2", [{"path": "data.json", "action": "modified", "size": 200, "prev_size": 100}])

    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", "/api/v1/runs/multi/events")
    response = connection.getresponse()
    parsed = parse_sse(response.readlines())
    connection.close()

    assert response.status == 200
    event_types = [item["event"] for item in parsed]
    assert "run_event" in event_types
    assert "file_changes" in event_types
    assert event_types[-1] == "stream_end"

    run_events = [item for item in parsed if item["event"] == "run_event"]
    fc_events = [item for item in parsed if item["event"] == "file_changes"]
    assert [item["id"] for item in run_events] == ["1", "2"]
    assert [item["id"] for item in fc_events] == ["1", "2"]


def test_sse_multi_topic_per_topic_cursor_reconnect(api):
    """AC-016-N-4: per-topic independent cursors on reconnect."""
    _, factory, port = api
    run = factory.create_run("reconnect", status="done")
    factory.append_v2_event(run, 1, "log", payload={})
    factory.append_v2_event(run, 2, "log", payload={})
    factory.append_v2_event(run, 3, "log", payload={})
    factory.append_v2_event(run, 4, "log", payload={})
    factory.append_v2_event(run, 5, "log", payload={})
    factory.append_file_changes(run, 1, "采集", "p1", [{"path": "a", "action": "created", "size": 1}])
    factory.append_file_changes(run, 2, "处理", "p2", [{"path": "b", "action": "created", "size": 2}])
    factory.append_file_changes(run, 3, "归档", "p3", [{"path": "c", "action": "created", "size": 3}])

    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", "/api/v1/runs/reconnect/events?last_event_id=3&last_file_changes_id=1")
    response = connection.getresponse()
    parsed = parse_sse(response.readlines())
    connection.close()

    run_events = [item for item in parsed if item["event"] == "run_event"]
    fc_events = [item for item in parsed if item["event"] == "file_changes"]
    assert [item["id"] for item in run_events] == ["4", "5"]
    assert [item["id"] for item in fc_events] == ["2", "3"]


def test_sse_file_changes_cursor_out_of_range_does_not_affect_run_event(api):
    """AC-016-E-3: file_changes cursor out of range sends stream_error, run_event continues."""
    _, factory, port = api
    run = factory.create_run("fc-oob", status="done")
    factory.append_v2_event(run, 1, "log", payload={"message": "ok"})
    factory.append_file_changes(run, 1, "采集", "p1", [{"path": "a", "action": "created", "size": 1}])
    factory.append_file_changes(run, 2, "处理", "p2", [{"path": "b", "action": "created", "size": 2}])

    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", "/api/v1/runs/fc-oob/events?last_file_changes_id=99")
    response = connection.getresponse()
    parsed = parse_sse(response.readlines())
    connection.close()

    assert response.status == 200
    event_types = [item["event"] for item in parsed]
    assert "run_event" in event_types
    errors = [item for item in parsed if item["event"] == "stream_error"]
    assert len(errors) == 1
    error_data = json.loads(errors[0]["data"])
    assert error_data["topic"] == "file_changes"
    assert error_data["code"] == "cursor_out_of_range"
    # run_event was still pushed
    run_events = [item for item in parsed if item["event"] == "run_event"]
    assert len(run_events) == 1
    # stream_end was still sent
    assert event_types[-1] == "stream_end"


def test_sse_no_file_changes_jsonl_silently_empty(api):
    """Legacy run without file_changes.jsonl: file_changes topic is silent, run_event works."""
    _, factory, port = api
    run = factory.create_run("no-fc", status="done")
    factory.append_v2_event(run, 1, "log", payload={"message": "hello"})

    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", "/api/v1/runs/no-fc/events")
    response = connection.getresponse()
    parsed = parse_sse(response.readlines())
    connection.close()

    assert response.status == 200
    event_types = [item["event"] for item in parsed]
    assert "file_changes" not in event_types
    assert "run_event" in event_types
    assert event_types[-1] == "stream_end"


# --- Declared phases pre-display tests (ADR-0040) ---


def test_loop_summary_includes_declared_phases(api):
    """Loop detail returns declared_phases from meta.phases frontmatter."""
    _, factory, port = api
    factory.create_loop("phased", phases=[
        {"title": "采集", "detail": "数据采集阶段"},
        {"title": "处理", "detail": "数据处理阶段"},
        {"title": "归档", "detail": ""},
    ])

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/loops/phased").json()
    assert detail["declared_phases"] == [
        {"title": "采集", "detail": "数据采集阶段"},
        {"title": "处理", "detail": "数据处理阶段"},
        {"title": "归档", "detail": ""},
    ]


def test_loop_summary_without_phases_returns_empty_list(api):
    """Loop without meta.phases returns empty declared_phases list."""
    _, factory, port = api
    factory.create_loop("simple")

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/loops/simple").json()
    assert detail["declared_phases"] == []


def test_loop_summary_skips_invalid_phase_entries(api):
    """Invalid phase entries (missing/empty title) are silently skipped."""
    _, factory, port = api
    factory.create_loop("mixed", phases=[
        {"title": "有效", "detail": "ok"},
        {"detail": "missing title"},
        {"title": "", "detail": "empty title"},
        {"title": 123, "detail": "non-string title"},
        "not-a-dict",
    ])

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/loops/mixed").json()
    assert detail["declared_phases"] == [{"title": "有效", "detail": "ok"}]


def test_run_detail_includes_declared_phases_from_run_json(api):
    """Run detail returns declared_phases persisted in run.json at execution start."""
    _, factory, port = api
    factory.create_loop("phased", phases=[
        {"title": "采集", "detail": "数据采集"},
        {"title": "归档", "detail": ""},
    ])
    run = factory.create_run("run-1", status="running", loop="phased")
    # Simulate execution.py writing declared_phases to run.json
    metadata = json.loads((run / "run.json").read_text())
    metadata["declared_phases"] = [
        {"title": "采集", "detail": "数据采集"},
        {"title": "归档", "detail": ""},
    ]
    factory.write_json(run / "run.json", metadata)

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/runs/run-1").json()
    assert detail["declared_phases"] == [
        {"title": "采集", "detail": "数据采集"},
        {"title": "归档", "detail": ""},
    ]


def test_run_detail_without_declared_phases_returns_none(api):
    """Legacy run without declared_phases returns None (not empty list)."""
    _, factory, port = api
    factory.create_run("legacy-run", status="done")

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/runs/legacy-run").json()
    assert detail.get("declared_phases") is None


# --- Declared args pre-fill tests (BR-047) ---


def test_system_meta_returns_version(api):
    """GET /system/meta returns the running loopflow.__version__."""
    import loopflow

    _, _, port = api
    client = JsonHttpClient("127.0.0.1", port)
    response = client.request("GET", "/api/v1/system/meta")
    assert response.status == 200
    assert response.json() == {"version": loopflow.__version__}


def test_loop_summary_and_detail_include_declared_args(api):
    """declared_args from meta.args frontmatter appears on summary and detail."""
    _, factory, port = api
    factory.create_loop("argful", args=[
        {"name": "goal", "description": "目标描述", "required": True},
        {"name": "count", "default": 3},
        {"name": "mode", "default": "fast", "description": "运行模式", "required": False},
    ])

    client = JsonHttpClient("127.0.0.1", port)
    expected = [
        {"name": "goal", "default": None, "description": "目标描述", "required": True},
        {"name": "count", "default": 3, "description": "", "required": False},
        {"name": "mode", "default": "fast", "description": "运行模式", "required": False},
    ]
    detail = client.request("GET", "/api/v1/loops/argful").json()
    assert detail["declared_args"] == expected
    summaries = client.request("GET", "/api/v1/loops").json()["items"]
    summary = next(item for item in summaries if item["name"] == "argful")
    assert summary["declared_args"] == expected


def test_loop_without_args_returns_empty_declared_args(api):
    """Loop without meta.args returns empty declared_args list (like declared_phases)."""
    _, factory, port = api
    factory.create_loop("simple")

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/loops/simple").json()
    assert detail["declared_args"] == []


def test_loop_skips_invalid_arg_entries(api):
    """Invalid arg entries (missing/non-string name, non-dict) are silently skipped."""
    _, factory, port = api
    factory.create_loop("mixed-args", args=[
        {"name": "valid", "default": "ok"},
        {"default": "missing name"},
        {"name": 123},
        {"name": ""},
        "not-a-dict",
    ])

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/loops/mixed-args").json()
    assert detail["valid"] is True
    assert detail["declared_args"] == [
        {"name": "valid", "default": "ok", "description": "", "required": False}
    ]


def test_loop_non_list_args_returns_empty_declared_args(api):
    """A non-list meta.args is treated as no declaration; loop still loads."""
    _, factory, port = api
    loop_dir = factory.create_loop("scalar-args")
    loop_md = loop_dir / "loop.md"
    text = loop_md.read_text(encoding="utf-8")
    loop_md.write_text(text.replace("---\n", "---\nargs: not-a-list\n", 1), encoding="utf-8")

    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/loops/scalar-args").json()
    assert detail["valid"] is True
    assert detail["declared_args"] == []


# --- File change observation REST tests (ADR-0039) ---


def test_file_changes_rest_endpoint_returns_records(api):
    """GET /runs/{id}/file-changes returns all file_changes.jsonl records."""
    _, factory, port = api
    run = factory.create_run("fc-rest", status="done")
    factory.append_file_changes(run, 1, "采集", "phase-1", [{"path": "a.txt", "action": "created", "size": 10}])
    factory.append_file_changes(run, 2, "处理", "phase-2", [{"path": "a.txt", "action": "modified", "size": 20, "prev_size": 10}])

    client = JsonHttpClient("127.0.0.1", port)
    result = client.request("GET", "/api/v1/runs/fc-rest/file-changes").json()
    assert result["count"] == 2
    assert result["items"][0]["seq"] == 1
    assert result["items"][1]["seq"] == 2
    assert result["items"][0]["changes"][0]["action"] == "created"
    assert result["items"][1]["changes"][0]["action"] == "modified"


def test_file_changes_rest_endpoint_empty_for_no_file(api):
    """GET /runs/{id}/file-changes returns empty list when file_changes.jsonl doesn't exist."""
    _, factory, port = api
    factory.create_run("no-fc-rest", status="done")

    client = JsonHttpClient("127.0.0.1", port)
    result = client.request("GET", "/api/v1/runs/no-fc-rest/file-changes").json()
    assert result == {"items": [], "count": 0}


def test_file_changes_rest_404_for_nonexistent_run(api):
    """GET /runs/{id}/file-changes returns 404 for nonexistent run."""
    _, factory, port = api
    client = JsonHttpClient("127.0.0.1", port)
    response = client.request("GET", "/api/v1/runs/nonexistent/file-changes")
    assert response.status == 404


def test_create_run_with_explicit_working_directory(api, tmp_path):
    """AC-025-N-1: 201 and run.json persists the explicit working directory."""
    client, factory, _ = api
    workdir = tmp_path / "B"
    workdir.mkdir()

    created = client.request("POST", "/api/v1/runs", {"loop": "hello", "working_directory": str(workdir)})

    assert created.status == 201
    run_id = created.json()["run_id"]
    metadata = json.loads((factory.runs / run_id / "run.json").read_text())
    assert metadata["working_directory"] == str(workdir)


def test_create_run_without_working_directory_keeps_default(api):
    """AC-025-B-1: omitting working_directory keeps the process-cwd default."""
    client, factory, _ = api

    created = client.request("POST", "/api/v1/runs", {"loop": "hello"})

    assert created.status == 201
    run_id = created.json()["run_id"]
    metadata = json.loads((factory.runs / run_id / "run.json").read_text())
    assert "working_directory" not in metadata


def test_create_run_rejects_relative_working_directory(api):
    """AC-025-B-2: a relative working_directory is 422 not_absolute."""
    client, factory, _ = api
    before = {path.name for path in factory.runs.iterdir()}

    response = client.request("POST", "/api/v1/runs", {"loop": "hello", "working_directory": "B"})

    assert response.status == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"]["reason"] == "not_absolute"
    assert {path.name for path in factory.runs.iterdir()} == before


def test_create_run_rejects_nonexistent_working_directory(api, tmp_path):
    """AC-025-E-1: a missing working_directory is 422 not_found, no run dir."""
    client, factory, _ = api
    before = {path.name for path in factory.runs.iterdir()}

    response = client.request(
        "POST", "/api/v1/runs", {"loop": "hello", "working_directory": str(tmp_path / "nonexistent")}
    )

    assert response.status == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"]["reason"] == "not_found"
    assert {path.name for path in factory.runs.iterdir()} == before


def test_create_run_rejects_file_as_working_directory(api, tmp_path):
    """AC-025-E-2: a non-directory working_directory is 422 not_a_directory."""
    client, factory, _ = api
    a_file = tmp_path / "a-file"
    a_file.write_text("not a directory")
    before = {path.name for path in factory.runs.iterdir()}

    response = client.request("POST", "/api/v1/runs", {"loop": "hello", "working_directory": str(a_file)})

    assert response.status == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"]["reason"] == "not_a_directory"
    assert {path.name for path in factory.runs.iterdir()} == before


def test_recover_rejects_working_directory_override(api, tmp_path):
    """AC-025-B-3: recover reuses the original directory and rejects an
    override field in the request body."""
    client, factory, _ = api
    workdir = tmp_path / "B"
    workdir.mkdir()
    factory.create_run("failed-wd", status="failed", working_directory=str(workdir))

    override = client.request(
        "POST",
        "/api/v1/runs/failed-wd/recover",
        {"mode": "retry", "working_directory": str(tmp_path)},
    )
    assert override.status == 422
    assert override.json()["error"]["code"] == "validation_failed"

    recovered = client.request("POST", "/api/v1/runs/failed-wd/recover", {"mode": "retry"})
    assert recovered.status == 200
    assert recovered.json()["run_id"] == "failed-wd"


def test_run_file_preview_returns_text_content(api, tmp_path):
    """AC-025-N-4: preview a text file inside the run's working directory."""
    client, factory, _ = api
    workdir = tmp_path / "B"
    (workdir / "src").mkdir(parents=True)
    (workdir / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    factory.create_run("wd-run", working_directory=str(workdir))

    response = client.request("GET", "/api/v1/runs/wd-run/file?path=src/main.py")

    assert response.status == 200
    body = response.json()
    assert body["path"] == "src/main.py"
    assert body["media_type"] == "text/x-python"
    assert body["content"] == "print('hi')\n"
    assert body["size"] == len("print('hi')\n")
    assert body["read_only"] is True


def test_run_file_preview_rejects_path_escape(api, tmp_path):
    """AC-025-B-4: paths resolving outside the working directory are 403."""
    client, factory, _ = api
    workdir = tmp_path / "B"
    workdir.mkdir()
    outside = tmp_path / "A"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret", encoding="utf-8")
    factory.create_run("wd-run", working_directory=str(workdir))

    relative_escape = client.request("GET", "/api/v1/runs/wd-run/file?path=../A/secret.txt")
    assert relative_escape.status == 403
    assert relative_escape.json()["error"]["code"] == "path_forbidden"
    assert "content" not in relative_escape.json()["error"]

    absolute = client.request("GET", "/api/v1/runs/wd-run/file?path=/etc/hostname")
    assert absolute.status == 403
    assert absolute.json()["error"]["code"] == "path_forbidden"


def test_run_file_preview_rejects_binary_and_oversized(api, tmp_path):
    """AC-025-B-5: binary or >1 MiB files are 422 file_not_previewable."""
    client, factory, _ = api
    workdir = tmp_path / "B"
    workdir.mkdir()
    (workdir / "blob.bin").write_bytes(b"\x00\x01\x02binary")
    (workdir / "huge.txt").write_bytes(b"x" * (1024 * 1024 + 1))
    factory.create_run("wd-run", working_directory=str(workdir))

    binary = client.request("GET", "/api/v1/runs/wd-run/file?path=blob.bin")
    assert binary.status == 422
    assert binary.json()["error"]["code"] == "file_not_previewable"

    oversized = client.request("GET", "/api/v1/runs/wd-run/file?path=huge.txt")
    assert oversized.status == 422
    assert oversized.json()["error"]["code"] == "file_not_previewable"


def test_run_file_preview_missing_file_and_unknown_run(api, tmp_path):
    """AC-025-E-3: a missing preview file is 404 file_not_found; an unknown
    run is 404 run_not_found."""
    client, factory, _ = api
    workdir = tmp_path / "B"
    workdir.mkdir()
    factory.create_run("wd-run", working_directory=str(workdir))

    missing = client.request("GET", "/api/v1/runs/wd-run/file?path=missing.txt")
    assert missing.status == 404
    assert missing.json()["error"]["code"] == "file_not_found"

    unknown = client.request("GET", "/api/v1/runs/no-such-run/file?path=missing.txt")
    assert unknown.status == 404
    assert unknown.json()["error"]["code"] == "run_not_found"


def test_pick_directory_endpoint(api, monkeypatch):
    """AC-025-N-6/B-6/B-7: native picker endpoint contract over HTTP."""
    client, _, _ = api
    monkeypatch.setattr("sys.platform", "darwin")

    def selected(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="/tmp/B/\n", stderr="")

    monkeypatch.setattr("loopflow.application.web.subprocess.run", selected)
    picked = client.request("POST", "/api/v1/system/pick-directory")
    assert picked.status == 200
    assert picked.json() == {"path": "/tmp/B", "cancelled": False}

    def cancelled(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="User cancelled.")

    monkeypatch.setattr("loopflow.application.web.subprocess.run", cancelled)
    cancelled_response = client.request("POST", "/api/v1/system/pick-directory")
    assert cancelled_response.status == 200
    assert cancelled_response.json() == {"path": None, "cancelled": True}

    monkeypatch.setattr("sys.platform", "linux")
    unsupported = client.request("POST", "/api/v1/system/pick-directory")
    assert unsupported.status == 501
    assert unsupported.json()["error"]["code"] == "not_supported"

    assert client.request("GET", "/api/v1/system/pick-directory").status == 404
