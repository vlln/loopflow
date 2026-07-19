from __future__ import annotations

from jsonschema import ValidationError
import pytest

from tests.web_support.contracts import contract_examples, validate_contract
from tests.web_support.factories import BackendManagerStub, ProcessProbeStub, WebFixtureFactory
from tests.web_support.http import parse_sse


def test_contract_examples_match_interface_shapes():
    for name, example in contract_examples().items():
        validate_contract(name, example)


def test_contract_validator_rejects_shape_drift():
    invalid = contract_examples()["backend"]
    invalid["health_score"] = 99

    with pytest.raises(ValidationError):
        validate_contract("backend", invalid)


def test_filesystem_factory_creates_v2_legacy_and_unreadable_runs(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    run = factory.create_run("run-v2", status="running", state={"attempt": 2})
    event = factory.append_v2_event(
        run,
        1,
        "agent_start",
        phase="Review",
        phase_id="phase-1",
        call_id="call-1",
    )
    legacy = factory.create_run("run-legacy")
    factory.append_legacy_event(legacy, {"type": "message", "session": "session-1"})
    unreadable = factory.create_unreadable_run("run-broken")

    validate_contract("v2_event", event)
    assert (run / "state.json").read_text() == '{"attempt": 2}'
    assert '"session": "session-1"' in (legacy / "events.jsonl").read_text()
    assert (unreadable / "run.json").read_text() == '{"run_id":'


def test_backend_and_process_stubs_are_deterministic():
    backend = BackendManagerStub([contract_examples()["backend"]])
    backend.set_diagnostic("mock", contract_examples()["diagnostic"])
    process = ProcessProbeStub({123: "fixture-start"})

    assert backend.list_backends()[0]["name"] == "mock"
    assert backend.diagnose("mock", 100)["reason"] == "timeout"
    assert backend.calls == [("mock", 100)]
    assert process.started_at(123) == "fixture-start"
    assert process.started_at(999) is None


def test_sse_parser_supports_multiline_data_and_comments():
    events = parse_sse(
        [
            b": heartbeat\n",
            b"id: 12\n",
            b"event: run_event\n",
            b"data: {\"line\":1}\n",
            b"data: {\"line\":2}\n",
            b"\n",
        ]
    )

    assert events == [
        {"id": "12", "event": "run_event", "data": '{"line":1}\n{"line":2}'}
    ]
