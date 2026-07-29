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

    invalid_intervention = dict(contract_examples()["intervention"])
    invalid_intervention["answered_at"] = None
    with pytest.raises(ValidationError):
        validate_contract("intervention", invalid_intervention)


def test_v18_file_preview_union_and_declared_args_contracts():
    examples = contract_examples()
    validate_contract("file_preview", examples["file_preview"])
    validate_contract(
        "file_preview",
        {
            "path": "notes.txt",
            "media_type": "text/plain",
            "content": "hello",
            "size": 5,
            "read_only": True,
        },
    )
    validate_contract("declared_arg", examples["declared_arg"])

    invalid_raw = dict(examples["file_preview"])
    invalid_raw["content"] = "base64 bytes"
    with pytest.raises(ValidationError):
        validate_contract("file_preview", invalid_raw)

    invalid_arg = {"name": "topic", "unknown": True}
    with pytest.raises(ValidationError):
        validate_contract("declared_arg", invalid_arg)
    with pytest.raises(ValidationError):
        validate_contract("declared_arg", {"name": "   "})


def test_run_create_append_prompt_uses_utf8_byte_limit():
    create = contract_examples()["run_create"]
    validate_contract("run_create", create)
    validate_contract("run_create", {"loop": "hello", "append_prompt": "界" * 21845})

    with pytest.raises(ValidationError, match="65536 UTF-8 bytes"):
        validate_contract("run_create", {"loop": "hello", "append_prompt": "界" * 21846})


def test_normalized_intervention_requires_group_and_answer_provenance():
    intervention = contract_examples()["intervention_v18"]
    validate_contract("intervention_v18", intervention)

    agent_request = dict(intervention)
    agent_request.update(
        {
            "source": "agent",
            "request_group_id": "group-1",
            "call_id": "call-1",
            "session_id": "session-1",
            "resume_mode": "continue",
            "can_continue_session": True,
        }
    )
    validate_contract("intervention_v18", agent_request)

    answered = dict(intervention)
    answered.update({"status": "answered", "response": False})
    with pytest.raises(ValidationError):
        validate_contract("intervention_v18", answered)


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
