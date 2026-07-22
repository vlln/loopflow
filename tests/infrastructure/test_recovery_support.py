from __future__ import annotations

import json
from threading import Thread

import pytest
from jsonschema import ValidationError

from tests.recovery_support import (
    AtomicWriterFake,
    CallCacheFactory,
    ClockFake,
    EpochWriterFake,
    InterventionFactory,
    ProcessGroupFake,
    ReplayDiverged,
    RunLockFake,
    SessionBackendFake,
    SessionCapabilities,
    WorkflowFactory,
    parallel_call_id,
    read_segments,
    select_replay_segment,
    stable_digest,
)
from tests.recovery_support.contracts import contract_examples, validate_contract
from tests.recovery_support.process_groups import (
    process_exists,
    spawn_process_group,
    terminate_process_group,
)


def test_call_cache_factory_builds_all_fixture_shapes(tmp_path):
    factory = CallCacheFactory(tmp_path)
    digest = stable_digest({"prompt": "one", "model": None})

    succeeded = factory.succeeded("0001", digest)
    failed = factory.failed("0002", digest)
    interrupted = factory.interrupted("0003", digest)
    segmented = factory.segmented("0004", digest)
    corrupt = factory.corrupt("0005", digest)
    legacy = factory.legacy(6)

    assert read_segments(succeeded)[0].done["status"] == "succeeded"
    assert read_segments(failed)[0].done["status"] == "failed"
    assert read_segments(interrupted)[0].done is None
    assert len(read_segments(segmented)) == 2
    assert read_segments(corrupt)[0].corrupt is True
    assert "call_id" not in legacy.read_text(encoding="utf-8")


def test_segment_reader_does_not_mix_failed_output_into_retry(tmp_path):
    path = CallCacheFactory(tmp_path).segmented("0001", "sha256:one")

    first, second = read_segments(path)

    assert first.messages == ["failed-output"]
    assert second.messages == ["new-output"]
    assert "failed-output" not in second.messages


def test_replay_selection_rejects_digest_drift_and_uncommitted_segments(tmp_path):
    factory = CallCacheFactory(tmp_path)
    succeeded = factory.succeeded("0001", "sha256:original")

    assert select_replay_segment(
        succeeded, call_id="0001", input_digest="sha256:original"
    ).messages == ["result"]
    with pytest.raises(ReplayDiverged):
        select_replay_segment(
            succeeded, call_id="0001", input_digest="sha256:changed"
        )

    interrupted = factory.interrupted("0002", "sha256:original")
    assert (
        select_replay_segment(
            interrupted, call_id="0002", input_digest="sha256:original"
        )
        is None
    )


def test_parallel_call_ids_are_hierarchical_and_position_stable(tmp_path):
    factory = CallCacheFactory(tmp_path)
    completion_order = (2, 0, 1)
    paths = [
        factory.succeeded(parallel_call_id(3, branch), "sha256:same")
        for branch in completion_order
    ]

    assert [path.stem for path in paths] == [
        "0003.0002.0001",
        "0003.0000.0001",
        "0003.0001.0001",
    ]


def test_backend_fake_exposes_session_timing_and_routes_resume():
    visible: list[str] = []
    backend = SessionBackendFake(session_timing="early")

    sid, exit_code = backend.create_session("first", session_handler=visible.append)
    resumed = backend.resume_session(sid, "continue")

    assert (sid, exit_code, resumed) == ("session-1", 0, 0)
    assert visible == ["session-1"]
    assert backend.calls == [
        ("create", "first", None),
        ("resume", "continue", "session-1"),
    ]


def test_backend_fake_rejects_resume_when_capability_is_absent():
    backend = SessionBackendFake(
        capabilities=SessionCapabilities(resume_session=True, durable_session_id=False)
    )

    with pytest.raises(RuntimeError, match="unsupported"):
        backend.resume_session("session-1", "continue")
    assert backend.calls == []


def test_backend_fake_injects_exception_and_controllable_block():
    exceptional = SessionBackendFake(create_behavior="exception")
    visible: list[str] = []
    with pytest.raises(RuntimeError, match="injected backend exception"):
        exceptional.create_session("prompt", session_handler=visible.append)
    assert visible == ["session-1"]

    blocked = SessionBackendFake(resume_behavior="block")
    result: list[int] = []
    worker = Thread(
        target=lambda: result.append(blocked.resume_session("session-1", "answer")),
        daemon=True,
    )
    worker.start()
    assert blocked.blocked.wait(timeout=1)
    assert worker.is_alive()
    blocked.release_block.set()
    worker.join(timeout=1)
    assert result == [0]


def test_fault_doubles_expose_write_lock_epoch_process_and_clock_failures():
    writer = AtomicWriterFake(fail_stage="replace")
    with pytest.raises(OSError, match="replace"):
        writer.write("run.json", {"status": "cancelling"})
    assert writer.published == {}

    lock = RunLockFake()
    with lock.acquire():
        assert lock.occupied is True
    assert (lock.acquisitions, lock.releases) == (1, 1)

    epoch = EpochWriterFake(current_epoch=2)
    assert epoch.write_terminal(1, "done") is False
    assert epoch.write_terminal(2, "cancelled") is True
    assert epoch.states == ["cancelled"]

    process = ProcessGroupFake(exits_on_term=False)
    assert process.terminate() == "killed"
    assert process.signals == ["TERM", "KILL"]

    clock = ClockFake()
    clock.advance(2.5)
    assert clock.monotonic() == 2.5


def test_intervention_and_workflow_factories_are_deterministic(tmp_path):
    interventions = InterventionFactory(tmp_path / "interventions")
    interventions.create("request-1", schema={"type": "boolean"})
    intervention = interventions.answer("request-1", True)
    workflows = WorkflowFactory(tmp_path / "workflows")

    value = json.loads(intervention.read_text(encoding="utf-8"))
    assert value["response"] is True
    assert value["status"] == "answered"
    assert workflows.sequential().read_text(encoding="utf-8").count("agent(") == 2
    assert "return" in workflows.early_return().read_text(encoding="utf-8")
    assert "parallel" in workflows.parallel().read_text(encoding="utf-8")
    assert "meta = {'state'" in workflows.state_loop().read_text(encoding="utf-8")
    assert "changed" in workflows.digest_path("changed").read_text(encoding="utf-8")
    assert "intervene" in workflows.intervention().read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="already answered"):
        interventions.answer("request-1", False)
    assert json.loads(intervention.read_text(encoding="utf-8"))["response"] is True


def test_v13_contract_examples_and_negative_shapes():
    examples = contract_examples()
    for name, value in examples.items():
        validate_contract(name, value)

    invalid = dict(examples["run_summary_v13"])
    invalid["allowed_actions"] = ["resume"]
    with pytest.raises(ValidationError):
        validate_contract("run_summary_v13", invalid)

    invalid_capabilities = dict(examples["backend_capabilities_v13"])
    invalid_capabilities.pop("durable_session_id")
    with pytest.raises(ValidationError):
        validate_contract("backend_capabilities_v13", invalid_capabilities)


@pytest.mark.skipif(not hasattr(__import__("os"), "killpg"), reason="POSIX process groups required")
def test_process_group_smoke_only_terminates_owned_group():
    process, child_pid = spawn_process_group()
    try:
        assert process.poll() is None
        assert process_exists(child_pid)
        terminate_process_group(process)
        assert process.poll() is not None
    finally:
        terminate_process_group(process)
