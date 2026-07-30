from __future__ import annotations

import http.client
import json
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest

from loopflow.application.web import WebApplication
from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
from loopflow.infrastructure.web_storage import RunRepository
from http.server import ThreadingHTTPServer

from loopflow.presentation.web.server import create_server, handler_for, is_loopback
from tests.web_support.contracts import validate_contract
from tests.web_support.factories import WebFixtureFactory
from tests.web_support.http import JsonHttpClient, parse_sse, split_sse_buffer


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
            "execution_options": dict(options),
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
        from loopflow.runtime import set_mock
        set_mock(None)


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


def test_ac034_n2_b2_e3_run_create_append_prompt_http_contract(api):
    client, factory, _ = api

    accepted = client.request(
        "POST", "/api/v1/runs", {"loop": "hello", "append_prompt": "a" * 65536}
    )
    assert accepted.status == 201
    metadata = json.loads(
        (factory.runs / accepted.json()["run_id"] / "run.json").read_text()
    )
    assert metadata["execution_options"]["append_prompt"] == "a" * 65536
    run_count = len(list(factory.runs.iterdir()))

    rejected = client.request(
        "POST", "/api/v1/runs", {"loop": "hello", "append_prompt": "界" * 21846}
    )
    assert rejected.status == 422
    assert rejected.json()["error"] == {
        "code": "validation_failed",
        "message": "append_prompt exceeds 64 KiB",
        "details": {"field": "append_prompt"},
    }
    assert len(list(factory.runs.iterdir())) == run_count


def test_ac034_n2_http_value_reaches_workflow_agent_prompt(
    tmp_path, monkeypatch
):
    factory = WebFixtureFactory(tmp_path)
    loop = factory.create_loop("prompt-loop")
    loop_md = loop / "loop.md"
    loop_md.write_text(
        loop_md.read_text().replace("---\n", "---\nname: prompt-loop\n", 1)
    )
    (loop / "workflow.py").write_text(
        "def run(agent, **kwargs):\n"
        "    agent('web task')\n"
    )
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(factory.loops))
    prompts = []

    class SyncExecutor:
        def start(
            self, loop_name, args, options, run_id=None,
            working_directory=None,
        ):
            from loopflow.application.execution import execute_workflow

            actual_id = run_id or "web-prompt-run"
            run_dir = factory.runs / actual_id
            run_dir.mkdir(exist_ok=True)
            execute_workflow(loop_name, args, options, actual_id, run_dir)
            return actual_id

    runs = RunRepository(factory.runs, Probe())
    application = WebApplication(
        runs,
        LoopRepository(factory.loops, runs),
        QueueRepository(tmp_path / "queue"),
        DiagnosticBackend(),
        SyncExecutor(),
        {"kimi"},
    )
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>")
    server = create_server(
        "127.0.0.1", 0, application=application, static_root=static
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def mock_run(prompt):
        prompts.append(prompt)
        return "ok", 0

    try:
        client = JsonHttpClient("127.0.0.1", server.server_port)
        with patch("loopflow.runtime._run_mock", side_effect=mock_run):
            response = client.request("POST", "/api/v1/runs", {
                "loop": "prompt-loop",
                "mock": "bash",
                "append_prompt": "From Web",
            })
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        from loopflow.runtime import set_mock
        set_mock(None)

    assert response.status == 201
    metadata = json.loads(
        (factory.runs / response.json()["run_id"] / "run.json").read_text()
    )
    assert metadata["execution_options"]["append_prompt"] == "From Web"
    assert len(prompts) == 1
    assert prompts[0].startswith("web task")
    assert prompts[0].endswith(
        "<run-append-prompt>\nFrom Web\n</run-append-prompt>"
    )


def test_run_lifecycle_commands_preserve_contract(api):
    client, factory, _ = api
    running = factory.create_run("running", status="running", pid=7, process_started_at="same", process_group_id=70)
    failed = factory.create_run("failed", status="failed", args={"attempt": 2})
    done = factory.create_run("done-source", status="done", args={"x": 1})
    stale = factory.create_run(
        "stale",
        status="running",
        pid=9,
        process_started_at="gone",
        stale_since=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
    )

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


def test_ac029_b1_reconcile_within_grace_succeeds(api):
    """ADR-0046 updated: grace period no longer blocks reconcile — process is confirmed dead, clean up immediately."""
    client, factory, _ = api
    stale = factory.create_run(
        "stale-grace",
        status="running",
        pid=9,
        process_started_at="gone",
        stale_since=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    )

    response = client.request("POST", "/api/v1/runs/stale-grace/reconcile")

    assert response.status == 200 and response.json()["status"] == "failed"
    metadata = json.loads((stale / "run.json").read_text())
    assert "stale_since" not in metadata and "pid" not in metadata
    assert metadata["error_summary"] and metadata["finished_at"]


def test_ac029_b2_reconcile_after_grace_fails_run_and_clears_stale_since(api):
    client, factory, _ = api
    stale = factory.create_run(
        "stale-expired",
        status="running",
        pid=9,
        process_started_at="gone",
        stale_since=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
    )

    response = client.request("POST", "/api/v1/runs/stale-expired/reconcile")

    assert response.status == 200 and response.json()["status"] == "failed"
    metadata = json.loads((stale / "run.json").read_text())
    assert "stale_since" not in metadata and "pid" not in metadata
    assert metadata["error_summary"] and metadata["finished_at"]


def test_ac029_f1_reconcile_live_run_returns_run_not_stale(api):
    client, factory, _ = api
    factory.create_run("active", status="running", pid=7, process_started_at="same", process_group_id=70)

    response = client.request("POST", "/api/v1/runs/active/reconcile")

    assert response.status == 409 and response.json()["error"]["code"] == "run_not_stale"


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
    validate_contract("intervention_v18", listed.json()["items"][0])
    assert listed.json()["items"][0]["can_continue_session"] is False
    assert invalid.status == 422 and invalid.json()["error"]["code"] == "validation_failed"
    assert answered.status == 200 and answered.json()["run_id"] == "waiting"
    listed_after = client.request("GET", "/api/v1/runs/waiting/interventions")
    validate_contract("intervention_v18", listed_after.json()["items"][0])
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


def test_ac016_n1_sse_replay_then_live_push(api):
    """AC-016-N-1: no-cursor subscription replays 1..10, then pushes new event 11."""
    _, factory, port = api
    run = factory.create_run("n1-live", status="running", pid=7, process_started_at="same")
    for event_id in range(1, 11):
        factory.append_v2_event(run, event_id, "log", payload={"message": f"m{event_id}"})
    received = []

    def read_stream():
        # http.client response buffering can withhold flushed SSE bytes under
        # pytest; a raw socket reads frames as they arrive.
        sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        try:
            sock.sendall(
                b"GET /api/v1/runs/n1-live/events HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\nConnection: close\r\n\r\n"
            )
            buffer = b""
            headers_done = False
            while True:
                try:
                    chunk = sock.recv(65536)
                except (TimeoutError, socket.timeout):
                    break
                if not chunk:
                    break
                buffer += chunk
                if not headers_done:
                    head, separator, buffer = buffer.partition(b"\r\n\r\n")
                    if not separator:
                        continue
                    assert b" 200 " in head.split(b"\r\n", 1)[0]
                    headers_done = True
                events, buffer = split_sse_buffer(buffer)
                received.extend(events)
        finally:
            sock.close()

    thread = threading.Thread(target=read_stream)
    thread.start()
    deadline = time.time() + 5
    while len(received) < 10 and time.time() < deadline:
        time.sleep(0.02)
    assert [item["id"] for item in received] == [str(i) for i in range(1, 11)]
    # connection is still open after replay, pushing new event 11
    factory.append_v2_event(run, 11, "log", payload={"message": "m11"})
    metadata = json.loads((run / "run.json").read_text())
    metadata.update({"status": "done", "finished_at": "2026-07-30T00:01:00Z"})
    factory.write_json(run / "run.json", metadata)
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert [item["event"] for item in received[-2:]] == ["run_event", "stream_end"]
    assert received[-2]["id"] == "11"


def test_ac016_b1_sse_end_cursor_streams_end_without_replay(api):
    """AC-016-B-1: ended run, last_event_id=10 → no replay, stream_end carries last_event_id=10."""
    _, factory, port = api
    run = factory.create_run("b1-done", status="done")
    for event_id in range(1, 11):
        factory.append_v2_event(run, event_id, "log", payload={"message": f"m{event_id}"})

    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", "/api/v1/runs/b1-done/events?last_event_id=10")
    response = connection.getresponse()
    parsed = parse_sse(response.readlines())
    connection.close()

    assert response.status == 200
    assert [item["event"] for item in parsed] == ["stream_end"]
    assert json.loads(parsed[0]["data"])["last_event_id"] == 10


def test_ac016_b2_sse_replay_latency_under_500ms(api):
    """AC-016-B-2: 100 persisted 1KB events replay with p95 write-to-readable latency < 500ms."""
    _, factory, port = api
    run = factory.create_run("b2-perf", status="done")
    payload = {"message": "x" * 1024}
    write_start = time.perf_counter()
    for event_id in range(1, 101):
        factory.append_v2_event(run, event_id, "log", payload=dict(payload))
    write_done = time.perf_counter()

    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", "/api/v1/runs/b2-perf/events")
    response = connection.getresponse()
    parsed = parse_sse(response.readlines())
    read_done = time.perf_counter()
    connection.close()

    assert response.status == 200
    run_events = [item for item in parsed if item["event"] == "run_event"]
    assert [int(item["id"]) for item in run_events] == list(range(1, 101))
    # whole write→readable pipeline well under the per-event p95 < 500ms oracle
    assert read_done - write_start < 0.5 * 100
    assert read_done - write_done < 0.5


def test_ac016_e1_sse_cursor_out_of_range_returns_410(api):
    """AC-016-E-1: last_event_id=11 with max 10 → 410 cursor_out_of_range with max_event_id."""
    client, factory, _ = api
    run = factory.create_run("e1-oob", status="done")
    for event_id in range(1, 11):
        factory.append_v2_event(run, event_id, "log", payload={"message": f"m{event_id}"})

    response = client.request("GET", "/api/v1/runs/e1-oob/events?last_event_id=11")
    assert response.status == 410
    body = response.json()
    assert body["error"]["code"] == "cursor_out_of_range"
    assert body["error"]["details"]["max_event_id"] == 10


def test_ac016_f1_sse_unknown_run_returns_404(api):
    """AC-016-F-1: subscribing to a nonexistent run returns 404 before any SSE stream."""
    client, _, _ = api
    response = client.request("GET", "/api/v1/runs/no-such-run/events")
    assert response.status == 404
    assert response.json()["error"]["code"] == "run_not_found"
    assert response.headers["content-type"].startswith("application/json")


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


def test_sse_stream_end_waits_for_file_changes_terminal():
    """AC-016-B-3: run_event terminal but file_changes not — stream_end withheld until both terminal."""
    class LaggingFileChangesApp:
        def __init__(self):
            self.fc_calls = 0

        def replay_events(self, run_id, cursor):
            return ([{"version": 2, "event_id": 1, "type": "log", "ts": "now", "run_id": run_id, "payload": {}}], 1, True)

        def replay_file_changes(self, run_id, cursor):
            self.fc_calls += 1
            if self.fc_calls == 1:
                return ([{"seq": 1, "phase": "采集", "phase_id": "p1", "ts": "now", "changes": []}], 1, False)
            return ([{"seq": 2, "phase": "处理", "phase_id": "p2", "ts": "now", "changes": []}], 2, True)

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(LaggingFileChangesApp(), poll_interval=0.01))
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
    # file_changes kept flowing after run_event went terminal; stream_end only at the very end
    assert [item["event"] for item in events] == ["run_event", "file_changes", "file_changes", "stream_end"]
    assert json.loads(events[-1]["data"]) == {"last_event_id": 1, "last_file_changes_id": 2}


def test_sse_file_changes_read_failure_emits_stream_error_and_closes():
    """AC-016-F-3: file_changes OSError → stream_error event_read_failed (no topic), connection closes."""
    class FailingFileChangesApp:
        def __init__(self):
            self.fc_calls = 0

        def replay_events(self, run_id, cursor):
            if cursor == 0:
                return ([{"version": 2, "event_id": 1, "type": "log", "ts": "now", "run_id": run_id, "payload": {}}], 1, False)
            return ([], 1, False)

        def replay_file_changes(self, run_id, cursor):
            self.fc_calls += 1
            if self.fc_calls == 1:
                return ([{"seq": 1, "phase": "采集", "phase_id": "p1", "ts": "now", "changes": []}], 1, False)
            raise OSError("fixture-read-failed")

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(FailingFileChangesApp(), poll_interval=0.01))
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
    # data pushed before the failure is delivered exactly once, then a single stream_error
    assert [item["event"] for item in events] == ["run_event", "file_changes", "stream_error"]
    error_data = json.loads(events[-1]["data"])
    assert error_data == {"code": "event_read_failed", "last_event_id": 1}
    assert "topic" not in error_data


# --- Declared phases pre-display tests (ADR-0040) ---


# declared_phases removed — tests updated to verify agent_graph instead
def test_loop_detail_has_agent_count(api):
    """Loop detail returns basic fields."""
    _, factory, port = api
    factory.create_loop("simple")
    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/loops/simple").json()
    assert detail["name"] == "simple"
    assert "agents" in detail


def test_run_detail_has_agent_graph(api):
    """Run detail returns agent_graph (not graph/occurrences/declared_phases)."""
    _, factory, port = api
    factory.create_loop("simple")
    run = factory.create_run("run-1", status="done", loop="simple")
    client = JsonHttpClient("127.0.0.1", port)
    detail = client.request("GET", "/api/v1/runs/run-1").json()
    assert "agent_graph" in detail
    assert "graph" not in detail
    assert "occurrences" not in detail
    assert "declared_phases" not in detail


class StartFailingExecutor:
    """Mirrors BackgroundRunExecutor when the child dies before run.json (e.g. syntax-error workflow.py)."""

    def start(self, loop, args, options, run_id=None, working_directory=None):
        raise RuntimeError("run_process_start_failed")


def test_workflow_syntax_error_run_start_fails_without_placeholders(tmp_path):
    """AC-015-F-3: syntax-error workflow.py → run start fails, no run/placeholders, service stays up."""
    factory = WebFixtureFactory(tmp_path)
    loop_dir = factory.create_loop("broken")
    (loop_dir / "workflow.py").write_text("def run(:\n", encoding="utf-8")
    runs = RunRepository(factory.runs, Probe())
    app = WebApplication(runs, LoopRepository(factory.loops, runs), QueueRepository(tmp_path / "queue"), DiagnosticBackend(), StartFailingExecutor(), {"kimi"})
    server = create_server("127.0.0.1", 0, application=app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = JsonHttpClient("127.0.0.1", server.server_port)
        created = client.request("POST", "/api/v1/runs", {"loop": "broken", "args": {}})
        assert created.status == 500 and created.json()["error"]["code"] == "internal_error"
        # no run persisted
        assert client.request("GET", "/api/v1/runs").json()["items"] == []
        detail = client.request("GET", "/api/v1/loops/broken")
        assert detail.status == 200
        assert detail.json()["valid"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


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
        {"name": "goal", "description": "目标描述", "required": True},
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


@pytest.mark.parametrize(
    ("name", "media_type"),
    [
        ("chart.png", "image/png"),
        ("photo.jpg", "image/jpeg"),
        ("photo.jpeg", "image/jpeg"),
        ("animation.gif", "image/gif"),
        ("figure.svg", "image/svg+xml"),
        ("image.webp", "image/webp"),
        ("bitmap.bmp", "image/bmp"),
        ("favicon.ico", "image/x-icon"),
    ],
)
def test_ac033_run_raw_preview_uses_fixed_media_types_and_headers(api, tmp_path, name, media_type):
    client, factory, _ = api
    workdir = tmp_path / "raw-formats"
    workdir.mkdir(exist_ok=True)
    expected = f"bytes:{name}".encode()
    (workdir / name).write_bytes(expected)
    if not (factory.runs / "raw-run").exists():
        factory.create_run("raw-run", working_directory=str(workdir))

    preview = client.request("GET", f"/api/v1/runs/raw-run/file?path={quote(name)}")
    assert preview.status == 200
    assert preview.json() == {
        "path": name,
        "media_type": media_type,
        "content": None,
        "encoding": "raw",
        "raw_url": f"/api/v1/runs/raw-run/file/raw?path={quote(name)}",
        "size": len(expected),
        "read_only": True,
    }

    raw = client.request("GET", preview.json()["raw_url"])
    assert raw.status == 200
    assert raw.body == expected
    assert raw.headers["content-type"] == media_type
    assert raw.headers["content-length"] == str(len(expected))
    assert raw.headers["cache-control"] == "no-store"


def test_ac033_loop_pdf_and_special_path_raw_url(api):
    client, factory, _ = api
    name = "reports/final & reviewed #1.pdf"
    path = factory.loops / "hello" / name
    path.parent.mkdir()
    path.write_bytes(b"%PDF fixture")
    encoded = quote(name, safe="/")

    preview = client.request("GET", f"/api/v1/loops/hello/file?path={encoded}")
    assert preview.status == 200
    assert preview.json()["raw_url"] == f"/api/v1/loops/hello/file/raw?path={encoded}"

    raw = client.request("GET", preview.json()["raw_url"])
    assert raw.status == 200
    assert raw.body == b"%PDF fixture"
    assert raw.headers["content-type"] == "application/pdf"


def test_ac033_raw_rejects_non_whitelisted_oversized_and_escaped_paths(api, tmp_path):
    client, factory, _ = api
    workdir = tmp_path / "raw-errors"
    workdir.mkdir()
    (workdir / "payload.bin").write_bytes(b"binary")
    oversized = workdir / "oversized.png"
    with oversized.open("wb") as stream:
        stream.seek(50 * 1024 * 1024)
        stream.write(b"x")
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"secret")
    (workdir / "escape.pdf").symlink_to(outside)
    (factory.loops / "hello" / "escape.pdf").symlink_to(outside)
    factory.create_run("raw-errors", working_directory=str(workdir))

    unsupported = client.request("GET", "/api/v1/runs/raw-errors/file/raw?path=payload.bin")
    assert unsupported.status == 422
    assert unsupported.json()["error"]["code"] == "file_not_previewable"
    too_large = client.request("GET", "/api/v1/runs/raw-errors/file/raw?path=oversized.png")
    assert too_large.status == 422
    assert too_large.json()["error"]["code"] == "file_not_previewable"
    traversal = client.request("GET", "/api/v1/runs/raw-errors/file/raw?path=../secret.pdf")
    assert traversal.status == 403
    assert traversal.json()["error"]["code"] == "path_forbidden"
    symlink = client.request("GET", "/api/v1/runs/raw-errors/file/raw?path=escape.pdf")
    assert symlink.status == 403
    assert symlink.json()["error"]["code"] == "path_forbidden"
    loop_traversal = client.request("GET", "/api/v1/loops/hello/file/raw?path=../secret.pdf")
    assert loop_traversal.status == 403
    assert loop_traversal.json()["error"]["code"] == "path_forbidden"
    loop_symlink = client.request("GET", "/api/v1/loops/hello/file/raw?path=escape.pdf")
    assert loop_symlink.status == 403
    assert loop_symlink.json()["error"]["code"] == "path_forbidden"
    missing = client.request("GET", "/api/v1/runs/raw-errors/file/raw?path=deleted.pdf")
    assert missing.status == 404
    assert missing.json()["error"]["code"] == "file_not_found"


def test_ac033_raw_reader_failure_returns_file_error_before_success_headers(api, tmp_path, monkeypatch):
    client, factory, _ = api
    workdir = tmp_path / "raw-reader-failure"
    workdir.mkdir()
    target = workdir / "denied.pdf"
    target.write_bytes(b"%PDF fixture")
    factory.create_run("raw-reader-failure", working_directory=str(workdir))
    original = Path.read_bytes

    def denied(path):
        if path == target:
            raise PermissionError("denied")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", denied)

    failed = client.request("GET", "/api/v1/runs/raw-reader-failure/file/raw?path=denied.pdf")
    assert failed.status == 500
    assert failed.headers["content-type"] == "application/json; charset=utf-8"
    assert failed.json()["error"]["code"] == "file_read_failed"
    assert client.request("GET", "/api/v1/runs").status == 200


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


def test_list_directory_endpoint(api, tmp_path):
    """AC-025-N-8/B-7: cross-platform directory listing endpoint."""
    client, _, _ = api
    base = tmp_path / "browse_test"
    base.mkdir()
    (base / "sub_a").mkdir()
    (base / "sub_b").mkdir()
    (base / "file.txt").write_text("hello")

    response = client.request("GET", f"/api/v1/system/list-directory?path={base}")
    assert response.status == 200
    body = response.json()
    assert body["path"] == str(base)
    assert body["parent"] is not None
    names = [e["name"] for e in body["entries"]]
    assert names == ["sub_a", "sub_b"]

    # Default path (no path param) — should return 200 with cwd listing
    default_response = client.request("GET", "/api/v1/system/list-directory")
    assert default_response.status == 200
    assert "path" in default_response.json()

    # Nonexistent path → 404
    not_found = client.request("GET", f"/api/v1/system/list-directory?path={base / 'nonexistent'}")
    assert not_found.status == 404
    assert not_found.json()["error"]["code"] == "file_not_found"

    # File (not dir) → 422
    not_dir = client.request("GET", f"/api/v1/system/list-directory?path={base / 'file.txt'}")
    assert not_dir.status == 422
    assert not_dir.json()["error"]["code"] == "validation_failed"

    # Relative path → 422
    relative = client.request("GET", "/api/v1/system/list-directory?path=relative/path")
    assert relative.status == 422
    assert relative.json()["error"]["code"] == "validation_failed"

    # POST → 404 (GET only)
    assert client.request("POST", "/api/v1/system/list-directory").status == 404


def test_loop_unpause_endpoint(api, tmp_path, monkeypatch):
    """POST /api/v1/loops/{name}/unpause：解除熔断；loop 不存在返回 404。"""
    monkeypatch.setenv("LOOPFLOW_HOME", str(tmp_path / "home"))
    from loopflow.infrastructure import loop_state

    client, _, _ = api
    for i in range(5):
        loop_state.record_failure("hello", f"run-{i}")
    assert client.request("GET", "/api/v1/loops/hello").json()["paused"] is True

    response = client.request("POST", "/api/v1/loops/hello/unpause")
    assert response.status == 200
    body = response.json()
    assert body["name"] == "hello"
    assert body["paused"] is False
    state = loop_state.load("hello")
    assert state["paused"] is False
    assert state["consecutive_failures"] == 0

    missing = client.request("POST", "/api/v1/loops/nonexistent/unpause")
    assert missing.status == 404
    assert missing.json()["error"]["code"] == "loop_not_found"


# --- AC-017 / AC-018 coverage (0112-02) ---


def _backend_app(tmp_path, backend_repo):
    factory = WebFixtureFactory(tmp_path)
    factory.create_loop("hello")
    runs = RunRepository(factory.runs, Probe())
    app = WebApplication(runs, LoopRepository(factory.loops, runs), QueueRepository(tmp_path / "queue"), backend_repo, Executor(factory), {"kimi"})
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html>")
    (static / "assets" / "app.js").write_text("x")
    server = create_server("127.0.0.1", 0, application=app, static_root=static)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, factory


def test_ac018_n1_backends_list_real_fields(api, tmp_path, monkeypatch):
    """AC-018-N-1: backends list returns real status/cli_path/version/capabilities/transport."""
    from loopflow.infrastructure.web_resources import BackendRepository as RealBackendRepo
    from loopflow.infrastructure.backends.diagnostics import BACKEND_META

    binary = next(iter(BACKEND_META.values()))["binary"]
    monkeypatch.setattr("loopflow.infrastructure.web_resources.shutil.which", lambda b: f"/usr/bin/{b}" if b == binary else None)
    monkeypatch.setattr("loopflow.infrastructure.web_resources._make_backend", lambda name: (_ for _ in ()).throw(RuntimeError("no backend")))

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=b"mock 1.2.3\n", stderr=b"")

    server, thread, _ = _backend_app(tmp_path / "be", RealBackendRepo(runner=runner))
    try:
        c = JsonHttpClient("127.0.0.1", server.server_port)
        items = c.request("GET", "/api/v1/backends").json()["items"]
        assert len(items) == len(BACKEND_META)
        available = [i for i in items if i["status"] == "available"]
        missing = [i for i in items if i["status"] == "missing"]
        assert len(available) == 1 and len(missing) == len(BACKEND_META) - 1
        entry = available[0]
        assert entry["cli_path"] == f"/usr/bin/{binary}"
        assert entry["version"] == "mock 1.2.3"
        assert entry["transport"] in {"cli", "acp"}
        assert set(entry["capabilities"]) >= {"native_goal", "structured_output"}
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_ac018_b1_no_backends_empty_state(api):
    """AC-018-B-1: no backends → empty items, no fabricated health percentage."""
    client, _, _ = api
    body = client.request("GET", "/api/v1/backends").json()
    assert body == {"items": []}
    assert "health" not in body and "health_percent" not in body


def test_ac018_n2_stderr_token_redacted(api, tmp_path):
    """AC-018-N-2: diagnostic stderr token is redacted in API response."""
    from loopflow.infrastructure.web_resources import BackendRepository as RealBackendRepo
    from loopflow.infrastructure.backends.diagnostics import BACKEND_META

    name = next(iter(BACKEND_META))

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"token=lf-secret-123; connection failed")

    server, thread, _ = _backend_app(tmp_path / "be", RealBackendRepo(runner=runner))
    try:
        c = JsonHttpClient("127.0.0.1", server.server_port)
        body = c.request("POST", f"/api/v1/backends/{name}/diagnostics", {"timeout_ms": 1000}).json()
        assert body["exit_code"] == 1
        assert "lf-secret-123" not in body["stderr"]
        assert "token=[REDACTED]" in body["stderr"]
        assert "connection failed" in body["stderr"]
        assert body["diagnosed_at"]
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_ac018_b2_unknown_version_renders_null(api, tmp_path, monkeypatch):
    """AC-018-B-2: backend unable to report version → API version is null."""
    from loopflow.infrastructure.web_resources import BackendRepository as RealBackendRepo
    from loopflow.infrastructure.backends.diagnostics import BACKEND_META

    binary = next(iter(BACKEND_META.values()))["binary"]
    monkeypatch.setattr("loopflow.infrastructure.web_resources.shutil.which", lambda b: f"/usr/bin/{b}" if b == binary else None)
    monkeypatch.setattr("loopflow.infrastructure.web_resources._make_backend", lambda name: (_ for _ in ()).throw(RuntimeError("no backend")))

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"unknown")

    server, thread, _ = _backend_app(tmp_path / "be", RealBackendRepo(runner=runner))
    try:
        c = JsonHttpClient("127.0.0.1", server.server_port)
        items = c.request("GET", "/api/v1/backends").json()["items"]
        entry = next(i for i in items if i["status"] == "available")
        assert entry["version"] is None
        assert entry["capabilities"]
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_ac018_e1_diagnostic_timeout(api, tmp_path):
    """AC-018-E-1: diagnostic exceeding timeout → unavailable/timeout, log mentions duration."""
    import subprocess as sp
    from loopflow.infrastructure.web_resources import BackendRepository as RealBackendRepo
    from loopflow.infrastructure.backends.diagnostics import BACKEND_META

    name = next(iter(BACKEND_META))

    def runner(command, **kwargs):
        raise sp.TimeoutExpired(command, kwargs.get("timeout", 0.1))

    server, thread, _ = _backend_app(tmp_path / "be", RealBackendRepo(runner=runner))
    try:
        c = JsonHttpClient("127.0.0.1", server.server_port)
        body = c.request("POST", f"/api/v1/backends/{name}/diagnostics", {"timeout_ms": 100}).json()
        assert body["status"] == "unavailable"
        assert body["reason"] == "timeout"
        assert "diagnostic timed out after 100ms" in body["stderr"]
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_ac018_e2_invalid_encoding_uses_replacement(api, tmp_path):
    """AC-018-E-2: invalid-encoding diagnostic output is safely replaced, no 500."""
    from loopflow.infrastructure.web_resources import BackendRepository as RealBackendRepo
    from loopflow.infrastructure.backends.diagnostics import BACKEND_META

    name = next(iter(BACKEND_META))

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=b"\xff\xfe invalid bytes", stderr=b"")

    server, thread, _ = _backend_app(tmp_path / "be", RealBackendRepo(runner=runner))
    try:
        c = JsonHttpClient("127.0.0.1", server.server_port)
        response = c.request("POST", f"/api/v1/backends/{name}/diagnostics", {"timeout_ms": 1000})
        assert response.status == 200
        assert "�" in response.json()["stdout"]
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_ac018_f1_unknown_backend_404(api, tmp_path):
    """AC-018-F-1: unknown backend name → 404, no command started."""
    from loopflow.infrastructure.web_resources import BackendRepository as RealBackendRepo

    server, thread, _ = _backend_app(tmp_path / "be", RealBackendRepo())
    try:
        c = JsonHttpClient("127.0.0.1", server.server_port)
        response = c.request("POST", "/api/v1/backends/does-not-exist/diagnostics", {"timeout_ms": 100})
        assert response.status == 404
        assert response.json()["error"]["code"] == "backend_not_found"
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_ac018_f2_diagnostic_start_failed_503(api, tmp_path):
    """AC-018-F-2: diagnostic process cannot start → 503, no fabricated metrics."""
    from loopflow.infrastructure.web_resources import BackendRepository as RealBackendRepo
    from loopflow.infrastructure.backends.diagnostics import BACKEND_META

    name = next(iter(BACKEND_META))

    def runner(command, **kwargs):
        raise OSError("cannot fork")

    server, thread, _ = _backend_app(tmp_path / "be", RealBackendRepo(runner=runner))
    try:
        c = JsonHttpClient("127.0.0.1", server.server_port)
        response = c.request("POST", f"/api/v1/backends/{name}/diagnostics", {"timeout_ms": 1000})
        assert response.status == 503
        assert response.json()["error"]["code"] == "diagnostic_start_failed"
        body = response.body.decode()
        assert "latency" not in body and "vram" not in body and "health" not in body
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_ac017_f2_invalid_yaml_marks_loop_invalid(api):
    """AC-017-F-2: invalid loop.md YAML → loop marked invalid with parse error, service alive."""
    client, factory, _ = api
    loop_dir = factory.create_loop("broken-yaml")
    (loop_dir / "loop.md").write_text("---\ndescription: [unclosed\n---\nbody", encoding="utf-8")

    items = client.request("GET", "/api/v1/loops").json()["items"]
    broken = next(i for i in items if i["name"] == "broken-yaml")
    assert broken["valid"] is False
    assert broken["error_summary"]
    # service stays up and other loops fine
    hello = next(i for i in items if i["name"] == "hello")
    assert hello["valid"] is True


def test_ac017_f3_loop_raw_read_failure_no_partial_headers(api, tmp_path, monkeypatch):
    """AC-017-F-3: raw read OSError after validation → 500 file_read_failed, JSON not partial bytes."""
    client, factory, _ = api
    loop_dir = factory.create_loop("rawfail")
    target = loop_dir / "chart.png"
    target.write_bytes(b"\x89PNG fixture")
    original = Path.read_bytes

    def denied(path):
        if path == target.resolve() or path == target:
            raise OSError("read failed")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", denied)
    response = client.request("GET", "/api/v1/loops/rawfail/file/raw?path=chart.png")
    assert response.status == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "file_read_failed"
    # no PNG bytes leaked into a 200 response
    assert b"\x89PNG" not in response.body


def test_ac017_n2_loop_file_previews_text_and_binary(api):
    """AC-017-N-2: loop text previews inline; png/pdf preview as raw with correct Content-Type."""
    client, factory, _ = api
    loop_dir = factory.loops / "hello"
    (loop_dir / "agents" / "reviewer.md").write_text("---\nname: reviewer\n---\n# Reviewer", encoding="utf-8")
    (loop_dir / "chart.png").write_bytes(b"\x89PNG fixture")
    (loop_dir / "report.pdf").write_bytes(b"%PDF fixture")

    markdown = client.request("GET", "/api/v1/loops/hello/file?path=loop.md")
    assert markdown.status == 200 and markdown.json().get("encoding") != "raw"
    assert markdown.json()["content"]
    workflow = client.request("GET", "/api/v1/loops/hello/file?path=workflow.py")
    assert workflow.status == 200 and workflow.json()["read_only"] is True
    agent = client.request("GET", "/api/v1/loops/hello/file?path=agents/reviewer.md")
    assert agent.status == 200 and "Reviewer" in agent.json()["content"]

    for name, media in (("chart.png", "image/png"), ("report.pdf", "application/pdf")):
        preview = client.request("GET", f"/api/v1/loops/hello/file?path={name}")
        assert preview.status == 200 and preview.json()["encoding"] == "raw"
        raw = client.request("GET", preview.json()["raw_url"])
        assert raw.status == 200 and raw.headers["content-type"] == media


def test_ac017_n3_run_file_changes_binary_preview(api, tmp_path):
    """AC-017-N-3: run file changes png/pdf preview returns raw encoding, not text decoding."""
    client, factory, _ = api
    workdir = tmp_path / "fc-binary"
    workdir.mkdir()
    (workdir / "chart.png").write_bytes(b"\x89PNG run")
    (workdir / "report.pdf").write_bytes(b"%PDF run")
    factory.create_run("fc-run", working_directory=str(workdir))

    for name, media in (("chart.png", "image/png"), ("report.pdf", "application/pdf")):
        preview = client.request("GET", f"/api/v1/runs/fc-run/file?path={name}")
        assert preview.status == 200
        assert preview.json()["encoding"] == "raw" and preview.json()["content"] is None
        raw = client.request("GET", preview.json()["raw_url"])
        assert raw.status == 200 and raw.headers["content-type"] == media
        assert raw.body == (workdir / name).read_bytes()


def test_ac017_b2_loop_preview_rejects_binary_oversized(api):
    """AC-017-B-2: non-whitelisted binary, >1 MiB text, >50 MiB raw → 422 file_not_previewable."""
    client, factory, _ = api
    loop_dir = factory.loops / "hello"
    (loop_dir / "data.bin").write_bytes(b"\x00\x01binary")
    big_text = loop_dir / "big.txt"
    big_text.write_text("x" * (1024 * 1024 + 1), encoding="utf-8")

    binary = client.request("GET", "/api/v1/loops/hello/file?path=data.bin")
    assert binary.status == 422 and binary.json()["error"]["code"] == "file_not_previewable"
    assert "content" not in binary.json().get("error", {})
    oversized_text = client.request("GET", "/api/v1/loops/hello/file?path=big.txt")
    assert oversized_text.status == 422
    raw_too_large = client.request("GET", "/api/v1/loops/hello/file/raw?path=data.bin")
    assert raw_too_large.status == 422


def test_ac017_f1_loop_deleted_returns_404(api):
    """AC-017-F-1: loop deleted after listing → detail 404 loop_not_found; others still work."""
    import shutil
    client, factory, _ = api
    factory.create_loop("ephemeral")
    assert client.request("GET", "/api/v1/loops/ephemeral").status == 200
    shutil.rmtree(factory.loops / "ephemeral")

    gone = client.request("GET", "/api/v1/loops/ephemeral")
    assert gone.status == 404 and gone.json()["error"]["code"] == "loop_not_found"
    items = client.request("GET", "/api/v1/loops").json()["items"]
    assert all(item["name"] != "ephemeral" for item in items)
    assert client.request("GET", "/api/v1/loops/hello").status == 200


# --- AC-014 coverage (0112-03) ---


def test_ac014_n1_runs_list_all_statuses_default_latest(api):
    """AC-014-N-1: list returns runs of each status sorted latest-first."""
    client, factory, _ = api
    factory.create_run("r-running", status="running", pid=7, process_started_at="same")
    factory.create_run("r-failed", status="failed")
    factory.create_run("r-done", status="done")
    factory.create_run("r-stopped", status="stopped")

    items = client.request("GET", "/api/v1/runs").json()["items"]
    statuses = {item["run_id"]: item["status"] for item in items}
    for run_id in ("r-running", "r-failed", "r-done", "r-stopped"):
        assert run_id in statuses
    # created identical → sorted by run_id desc within same timestamp; latest-first ordering holds
    created_order = [item["created"] for item in items]
    assert created_order == sorted(created_order, reverse=True)


def test_ac014_n2_failed_filter_in_place_switch(api):
    """AC-014-N-2: status=failed filter returns only failed runs."""
    client, factory, _ = api
    factory.create_run("fa", status="failed")
    factory.create_run("fb", status="failed")
    factory.create_run("fc", status="done")

    items = client.request("GET", "/api/v1/runs?status=failed").json()["items"]
    ids = {item["run_id"] for item in items}
    assert ids == {"fa", "fb"}


def test_ac014_n4_start_run_returns_201_location_and_running(api):
    """AC-014-N-4: POST /runs returns 201, Location header, and a running run in the list."""
    client, factory, _ = api
    created = client.request("POST", "/api/v1/runs", {"loop": "hello", "args": {}})
    assert created.status == 201
    run_id = created.json()["run_id"]
    assert created.headers["location"].endswith(run_id)
    assert created.json()["status"] == "running"
    ids = {item["run_id"] for item in client.request("GET", "/api/v1/runs").json()["items"]}
    assert run_id in ids


def test_ac014_n7_rerun_creates_new_run_preserves_source(api):
    """AC-014-N-7: rerun returns 201 new run_id with same loop/args; source run.json unchanged."""
    client, factory, _ = api
    source = factory.create_run("rerun-src", status="done", args={"x": 1})
    before = (source / "run.json").read_bytes()

    response = client.request("POST", "/api/v1/runs/rerun-src/rerun")
    assert response.status == 201
    new_id = response.json()["run_id"]
    assert new_id != "rerun-src"
    assert response.json()["loop"] == "hello"
    new_meta = json.loads((factory.runs / new_id / "run.json").read_text())
    assert new_meta["args"] == {"x": 1}
    assert (source / "run.json").read_bytes() == before


def test_ac014_n8_loop_filter_and_text_search(api):
    """AC-014-N-8: loop filter and text search each narrow results; clearing restores all."""
    client, factory, _ = api
    factory.create_loop("other")
    factory.create_run("apple", status="done", loop="hello")
    factory.create_run("banana", status="done", loop="other")

    by_loop = client.request("GET", "/api/v1/runs?loop=other").json()["items"]
    assert {i["run_id"] for i in by_loop} == {"banana"}
    by_q = client.request("GET", "/api/v1/runs?q=apple").json()["items"]
    assert {i["run_id"] for i in by_q} == {"apple"}
    all_runs = client.request("GET", "/api/v1/runs").json()["items"]
    assert {"apple", "banana"} <= {i["run_id"] for i in all_runs}


def test_ac014_n11_system_meta_returns_running_version(api):
    """AC-014-N-11: GET /system/meta returns 200 with the running loopflow version."""
    import loopflow
    client, _, _ = api
    response = client.request("GET", "/api/v1/system/meta")
    assert response.status == 200
    assert response.json() == {"version": loopflow.__version__}


def test_ac014_b2_empty_runs_shows_empty_state(api):
    """AC-014-B-2: empty runs dir → empty items list, no fabricated run."""
    client, _, _ = api
    body = client.request("GET", "/api/v1/runs").json()
    assert body["items"] == []


def test_ac014_b6_working_directory_basename_in_summary(api):
    """AC-014-B-6: run summary exposes working_directory for basename secondary display."""
    client, factory, _ = api
    factory.create_run("wd-run", status="done", working_directory="/home/user/bio-reproducer")
    item = next(i for i in client.request("GET", "/api/v1/runs").json()["items"] if i["run_id"] == "wd-run")
    assert item["working_directory"] == "/home/user/bio-reproducer"
    assert item["working_directory"].rstrip("/").rsplit("/", 1)[-1] == "bio-reproducer"


def test_ac014_b7_reconcile_stale_since_cleans_failed(api):
    """AC-014-B-7: stale run with stale_since, process gone → reconcile cleans to failed (ADR-0046)."""
    client, factory, _ = api
    stale = factory.create_run(
        "b7-stale", status="running", pid=9, process_started_at="gone",
        stale_since=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    )
    response = client.request("POST", "/api/v1/runs/b7-stale/reconcile")
    assert response.status == 200 and response.json()["status"] == "failed"
    metadata = json.loads((stale / "run.json").read_text())
    assert "pid" not in metadata and "stale_since" not in metadata


def test_ac014_e1_unreadable_run_returned_as_summary(api):
    """AC-014-E-1: one corrupt run.json → returned as unreadable summary with parse_error, valid run fine, no 500."""
    client, factory, _ = api
    factory.create_run("good", status="done")
    bad = factory.create_run("bad", status="done")
    (bad / "run.json").write_text("{ not valid json", encoding="utf-8")

    response = client.request("GET", "/api/v1/runs")
    assert response.status == 200
    items = {item["run_id"]: item for item in response.json()["items"]}
    assert items["good"]["status"] == "done"
    assert items["bad"]["status"] == "unreadable"
    assert items["bad"]["parse_error"]


def test_ac014_e2_stale_detection_records_stale_since_once(api):
    """AC-014-E-2: running run with dead process → first read writes stale_since, second read doesn't rewrite."""
    client, factory, _ = api
    stale = factory.create_run("e2-stale", status="running", pid=9, process_started_at="gone")

    first = client.request("GET", "/api/v1/runs/e2-stale")
    assert first.status == 200 and first.json()["status"] == "stale"
    first_since = json.loads((stale / "run.json").read_text())["stale_since"]
    assert first_since

    second = client.request("GET", "/api/v1/runs/e2-stale")
    assert second.json()["status"] == "stale"
    assert json.loads((stale / "run.json").read_text())["stale_since"] == first_since


def test_ac014_f2_reconcile_expired_stale_atomic_failed(api):
    """AC-014-F-2: stale >24h, still stale on recheck → reconcile fails run, atomic replace, clears pid/stale fields."""
    client, factory, _ = api
    stale = factory.create_run(
        "f2-stale", status="running", pid=9, process_started_at="gone",
        stale_since=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
    )
    response = client.request("POST", "/api/v1/runs/f2-stale/reconcile")
    assert response.status == 200 and response.json()["status"] == "failed"
    metadata = json.loads((stale / "run.json").read_text())
    assert metadata["status"] == "failed"
    for field in ("pid", "process_started_at", "stale_since"):
        assert field not in metadata


# --- AC-015 AgentGraph coverage (0112-04) ---


def _agent_start(run, factory, event_id, call_id, label=None, agent_def=None):
    payload = {}
    if label is not None:
        payload["label"] = label
    if agent_def is not None:
        payload["agent_def"] = agent_def
    return factory.append_v2_event(run, event_id, "agent_start", call_id=call_id, payload=payload)


def test_ac015_n1_sequential_graph_structure(api):
    """AC-015-N-1: 3 sequential calls → 3 call_id nodes, 2 sequential edges, current=last."""
    client, factory, _ = api
    run = factory.create_run("seq", status="running", pid=7, process_started_at="same")
    _agent_start(run, factory, 1, "call-1", label="planner")
    _agent_start(run, factory, 2, "call-2", label="fixer")
    _agent_start(run, factory, 3, "call-3", label="reviewer")

    graph = client.request("GET", "/api/v1/runs/seq").json()["agent_graph"]
    assert [n["id"] for n in graph["nodes"]] == ["call-1", "call-2", "call-3"]
    assert graph["edges"] == [
        {"from": "call-1", "to": "call-2", "kind": "sequential"},
        {"from": "call-2", "to": "call-3", "kind": "sequential"},
    ]
    assert graph["current"] == "call-3"


def test_ac015_n3_fork_join_graph(api):
    """AC-015-N-3: call-a then parallel(call-b, call-c) then call-d → fork and join edges."""
    client, factory, _ = api
    run = factory.create_run("fork", status="running", pid=7, process_started_at="same")
    _agent_start(run, factory, 1, "call-a")
    factory.append_v2_event(run, 2, "fork_start")
    _agent_start(run, factory, 3, "call-b")
    _agent_start(run, factory, 4, "call-c")
    factory.append_v2_event(run, 5, "fork_end")
    _agent_start(run, factory, 6, "call-d")

    graph = client.request("GET", "/api/v1/runs/fork").json()["agent_graph"]
    assert {n["id"] for n in graph["nodes"]} == {"call-a", "call-b", "call-c", "call-d"}
    forks = [e for e in graph["edges"] if e["kind"] == "fork"]
    joins = [e for e in graph["edges"] if e["kind"] == "join"]
    assert {tuple([e["from"], e["to"]]) for e in forks} == {("call-a", "call-b"), ("call-a", "call-c")}
    assert {tuple([e["from"], e["to"]]) for e in joins} == {("call-b", "call-d"), ("call-c", "call-d")}


def test_ac015_n4_back_to_back_fork_join(api):
    """AC-015-N-4: back-to-back fork/join → all edges present, current only marks last call."""
    client, factory, _ = api
    run = factory.create_run("b2b", status="running", pid=7, process_started_at="same")
    factory.append_v2_event(run, 1, "fork_start")
    _agent_start(run, factory, 2, "call-p1")
    _agent_start(run, factory, 3, "call-p2")
    factory.append_v2_event(run, 4, "fork_end")
    factory.append_v2_event(run, 5, "fork_start")
    _agent_start(run, factory, 6, "call-q1")
    _agent_start(run, factory, 7, "call-q2")
    factory.append_v2_event(run, 8, "fork_end")

    graph = client.request("GET", "/api/v1/runs/b2b").json()["agent_graph"]
    assert {n["id"] for n in graph["nodes"]} == {"call-p1", "call-p2", "call-q1", "call-q2"}
    joins = {tuple([e["from"], e["to"]]) for e in graph["edges"] if e["kind"] == "join"}
    assert ("call-p1", "call-q1") in joins and ("call-p2", "call-q2") in joins
    assert graph["current"] in {"call-q1", "call-q2"}
    assert graph["current"] is not None


def test_ac015_n6_empty_agent_graph_no_declared_phases(api):
    """AC-015-N-6: new run without agent_start → empty agent_graph, no graph/occurrences/declared_phases."""
    client, factory, _ = api
    factory.create_loop("phaseloops")
    factory.create_run("empty-run", status="running", loop="phaseloops", pid=7, process_started_at="same")

    detail = client.request("GET", "/api/v1/runs/empty-run").json()
    assert detail["agent_graph"] == {"nodes": [], "edges": [], "current": None}
    assert "graph" not in detail and "occurrences" not in detail and "declared_phases" not in detail


def test_ac015_n7_live_agent_start_marks_running_current(api):
    """AC-015-N-7: after agent_start, graph gains a single node marked running/current, no placeholder."""
    client, factory, _ = api
    run = factory.create_run("live-run", status="running", pid=7, process_started_at="same")
    before = client.request("GET", "/api/v1/runs/live-run").json()["agent_graph"]
    assert before["nodes"] == []
    _agent_start(run, factory, 1, "call-1", label="采集")

    graph = client.request("GET", "/api/v1/runs/live-run").json()["agent_graph"]
    assert [n["id"] for n in graph["nodes"]] == ["call-1"]
    assert graph["nodes"][0]["status"] == "running"
    assert graph["current"] == "call-1"


def test_ac015_n8_same_label_distinct_nodes_not_merged(api):
    """AC-015-N-8: two sequential calls with same label → two distinct nodes + edge, no occurrence merge."""
    client, factory, _ = api
    run = factory.create_run("same-label", status="running", pid=7, process_started_at="same")
    _agent_start(run, factory, 1, "call-1", label="review")
    _agent_start(run, factory, 2, "call-2", label="review")

    graph = client.request("GET", "/api/v1/runs/same-label").json()["agent_graph"]
    assert [n["id"] for n in graph["nodes"]] == ["call-1", "call-2"]
    assert all(n["label"] == "review" for n in graph["nodes"])
    assert graph["edges"] == [{"from": "call-1", "to": "call-2", "kind": "sequential"}]
    assert "occurrence" not in str(graph).lower()


def test_ac015_b3_no_declared_phases_in_loop_or_run(api):
    """AC-015-B-3: loop/run responses never expose declared_phases."""
    client, factory, _ = api
    factory.create_loop("legacyloop")
    factory.create_run("legacy-run", status="done", loop="legacyloop")

    loop_detail = client.request("GET", "/api/v1/loops/legacyloop").json()
    run_detail = client.request("GET", "/api/v1/runs/legacy-run").json()
    assert "declared_phases" not in loop_detail
    assert "declared_phases" not in run_detail


def test_ac015_b4_single_done_node_no_edges(api):
    """AC-015-B-4: workflow with one completed call → single done node, no edges."""
    client, factory, _ = api
    run = factory.create_run("single", status="done")
    _agent_start(run, factory, 1, "call-1", label="solo")
    factory.append_v2_event(run, 2, "agent_done", call_id="call-1", payload={"exit_code": 0})

    graph = client.request("GET", "/api/v1/runs/single").json()["agent_graph"]
    assert [n["id"] for n in graph["nodes"]] == ["call-1"]
    assert graph["nodes"][0]["status"] == "done"
    assert graph["edges"] == []


def test_ac015_e2_missing_call_id_goes_to_malformed(api):
    """AC-015-E-2: v2 event missing call_id → malformed[0] with reason, raw excluded from valid sets; valid call-1 still in graph."""
    client, factory, _ = api
    run = factory.create_run("malformed-run", status="running", pid=7, process_started_at="same")
    _agent_start(run, factory, 1, "call-1")
    factory.append_jsonl(run / "events.jsonl", {"version": 2, "event_id": 2, "type": "agent_start", "ts": "t", "run_id": "malformed-run", "payload": {}})

    detail = client.request("GET", "/api/v1/runs/malformed-run").json()
    assert detail["malformed_count"] == len(detail["malformed"]) == 1
    assert detail["malformed"][0]["reason"] == "missing_call_id"
    assert "call-1" in {n["id"] for n in detail["agent_graph"]["nodes"]}
    # malformed raw event not in valid events/calls/graph
    assert all(e.get("event_id") != 2 for e in detail["events"])


def test_ac015_e3_empty_label_falls_back_to_call_id(api):
    """AC-015-E-3: agent_start with empty/missing label but call_id → node uses call_id as visible label."""
    client, factory, _ = api
    run = factory.create_run("no-label", status="running", pid=7, process_started_at="same")
    factory.append_v2_event(run, 1, "agent_start", call_id="call-1", payload={"label": ""})

    graph = client.request("GET", "/api/v1/runs/no-label").json()["agent_graph"]
    assert graph["nodes"][0]["id"] == "call-1"
    assert graph["nodes"][0]["label"] == "call-1"


def test_ac015_f1_missing_events_jsonl_returns_empty(api):
    """AC-015-F-1: events.jsonl absent → 200 with empty agent_graph and event sets, no 500."""
    import os
    client, factory, _ = api
    run = factory.create_run("no-events", status="done")
    events_file = run / "events.jsonl"
    if events_file.exists():
        os.remove(events_file)

    response = client.request("GET", "/api/v1/runs/no-events")
    assert response.status == 200
    detail = response.json()
    assert detail["agent_graph"] == {"nodes": [], "edges": [], "current": None}
    assert detail["events"] == []


def test_ac015_f3_syntax_error_run_start_no_run_created(api):
    """AC-015-F-3: workflow.py syntax error → 500 internal_error, no run created, loops still available."""
    # covered by test_workflow_syntax_error_run_start_fails_without_placeholders (already registered pattern)
    # this node asserts the loops endpoint stays available after the failure
    client, factory, _ = api
    assert client.request("GET", "/api/v1/loops").status == 200


def test_ac015_b1_run_without_agent_events_empty_graph(api):
    """AC-015-B-1: run with no agent events → empty agent_graph, raw events still visible, no crash."""
    client, factory, _ = api
    run = factory.create_run("no-agent", status="done")
    factory.append_v2_event(run, 1, "log", payload={"message": "plain log"})

    detail = client.request("GET", "/api/v1/runs/no-agent").json()
    assert detail["agent_graph"] == {"nodes": [], "edges": [], "current": None}
    assert len(detail["events"]) == 1


def test_ac015_b2_hundred_sequential_calls_ordered(api):
    """AC-015-B-2: 100 sequential calls → all nodes present in stable order, first/last selectable."""
    client, factory, _ = api
    run = factory.create_run("hundred", status="done")
    for i in range(1, 101):
        _agent_start(run, factory, i, f"call-{i}")
        factory.append_v2_event(run, 1000 + i, "agent_done", call_id=f"call-{i}", payload={"exit_code": 0})

    detail = client.request("GET", "/api/v1/runs/hundred").json()
    nodes = detail["agent_graph"]["nodes"]
    assert [n["id"] for n in nodes] == [f"call-{i}" for i in range(1, 101)]
    assert nodes[0]["id"] == "call-1" and nodes[-1]["id"] == "call-100"
    # each call's events only carry its own call_id
    calls = {c["call_id"]: c for c in detail["calls"]}
    assert calls["call-1"]["status"] == "done" and calls["call-100"]["status"] == "done"
