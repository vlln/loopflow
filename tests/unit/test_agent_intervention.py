import json
from unittest.mock import MagicMock, patch

import pytest

from loopflow.domain.capabilities import Capabilities
from loopflow.infrastructure.intervention import answered_for_call


def _backend(*, resumable=True):
    backend = MagicMock()
    backend.capabilities = Capabilities(
        resume_session=resumable,
        durable_session_id=resumable,
    )
    backend.prepare_capabilities.return_value = backend.capabilities
    return backend


def _events(content, session_id="sid-1"):
    return [
        {"type": "agent_message", "content": content},
        {"type": "agent_done", "exit_code": 0, "session_id": session_id},
    ]


def _control(requests):
    return {"__loopflow": {"status": "waiting_input", "requests": requests}}


def test_agent_intervention_prompt_is_capability_gated(tmp_path):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend()
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", return_value=_events("completed")
    ) as invoke:
        assert agent("work").value == "completed"
    prompt = invoke.call_args.args[0]
    assert "<loopflow-intervention>" in prompt
    assert '"status":"waiting_input"' in prompt
    assert "necessary human input" in prompt
    assert not (tmp_path / "interventions").exists()


def test_control_branch_bypasses_required_business_schema(tmp_path):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend()
    output = _control([{
        "key": "scope", "prompt": "Scope?", "options": ["small", "large"],
        "allow_custom": False,
    }])
    schema = {
        "type": "object",
        "properties": {"result": {"type": "string"}},
        "required": ["result"],
    }
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", return_value=_events(json.dumps(output))
    ):
        with pytest.raises(RuntimeError, match="intervention_pending"):
            agent("work", schema=schema)
    assert len(list((tmp_path / "interventions").glob("*.json"))) == 1


def test_goal_mode_control_branch_is_prioritized_over_goal_schema(tmp_path):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend()
    output = _control([{
        "key": "scope", "prompt": "Scope?", "options": [], "allow_custom": True,
    }])
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", return_value=_events(json.dumps(output))
    ), pytest.raises(RuntimeError, match="intervention_pending"):
        agent("work", goal="finish")


def test_reserved_business_field_fails_before_backend_call(tmp_path):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend()
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent"
    ) as invoke, pytest.raises(RuntimeError, match="reserved"):
        agent("work", schema={"type": "object", "properties": {"__loopflow": {}}})
    invoke.assert_not_called()


@pytest.mark.parametrize("schema", [
    {"type": "object", "required": ["__loopflow"]},
    {"allOf": [{"type": "object", "properties": {"__loopflow": {}}}]},
    {"$defs": {"control": {"properties": {"__loopflow": {}}}}, "$ref": "#/$defs/control"},
    {"patternProperties": {"^__loopflow$": {"type": "string"}}},
    {"patternProperties": {"^__loop": {"type": "string"}}},
    {"patternProperties": {"loopflow$": {"type": "string"}}},
    {"propertyNames": {"const": "__loopflow"}},
    {"dependentRequired": {"result": ["__loopflow"]}},
])
def test_reserved_business_field_is_rejected_in_nested_schema_forms(tmp_path, schema):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend()
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent"
    ) as invoke, pytest.raises(RuntimeError, match="reserved"):
        agent("work", schema=schema)
    invoke.assert_not_called()


@pytest.mark.parametrize(("schema", "output"), [
    ({"type": "object", "description": "__loopflow"}, {}),
    ({"type": "string", "enum": ["__loopflow"]}, "__loopflow"),
    (
        {"type": "object", "properties": {"note": {"const": "__loopflow"}}},
        {"note": "__loopflow"},
    ),
])
def test_reserved_control_name_is_allowed_as_schema_annotation_or_value(
    tmp_path, schema, output
):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend()
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", return_value=_events(json.dumps(output))
    ) as invoke:
        assert agent("work", schema=schema).value == output
    invoke.assert_called_once()


@pytest.mark.parametrize(
    "requests",
    [
        None,
        "not-an-array",
        [],
        [{"key": "x", "prompt": "X?", "options": [], "allow_custom": True, "default": "x"}],
        [{"key": "x", "prompt": "X?", "options": [], "allow_custom": True, "timeout": 1}],
        [{"key": "x", "prompt": "X?", "options": [], "allow_custom": True, "default": "x", "timeout": 1}],
        [
            {"key": "x", "prompt": "X?", "options": [], "allow_custom": True},
            {"key": "x", "prompt": "Again?", "options": [], "allow_custom": True},
        ],
        ["not-an-object"],
        [{"key": "", "prompt": "X?", "options": [], "allow_custom": True}],
        [{"key": 1, "prompt": "X?", "options": [], "allow_custom": True}],
        [{"key": "x", "prompt": "", "options": [], "allow_custom": True}],
        [{"key": "x", "prompt": "X?", "options": "bad", "allow_custom": True}],
        [{"key": "x", "prompt": "X?", "options": [1], "allow_custom": True}],
        [{"key": "x", "prompt": "X?", "options": [], "allow_custom": "yes"}],
    ],
)
def test_invalid_control_is_rejected_before_any_request_is_written(tmp_path, requests):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend()
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", return_value=_events(json.dumps(_control(requests)))
    ), pytest.raises(RuntimeError, match="validation_failed"):
        agent("work")
    assert not list((tmp_path / "interventions").glob("*.json"))


def test_unsupported_backend_does_not_advertise_or_persist_control(tmp_path):
    from loopflow.runtime import RunContext, agent, set_context

    set_context(RunContext(run_dir=tmp_path))
    backend = _backend(resumable=False)
    output = _control([{
        "key": "x", "prompt": "X?", "options": [], "allow_custom": True,
    }])
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", return_value=_events(json.dumps(output))
    ) as invoke, pytest.raises(RuntimeError, match="agent_intervention_not_supported"):
        agent("work")
    assert "<loopflow-intervention>" not in invoke.call_args.args[0]
    assert not list((tmp_path / "interventions").glob("*.json"))


def test_answer_envelope_preserves_group_order_and_hides_internal_fields(tmp_path):
    root = tmp_path / "interventions"
    root.mkdir()
    for request_id, key, index in (("second", "b", 1), ("first", "a", 0)):
        (root / f"{request_id}.json").write_text(json.dumps({
            "request_id": request_id,
            "source": "agent",
            "key": key,
            "prompt": f"{key}?",
            "status": "answered",
            "response": key.upper(),
            "call_id": "0001",
            "session_id": "sid-1",
            "request_group_id": "group-1",
            "request_index": index,
        }))
    assert answered_for_call(tmp_path, "0001") == {
        "__loopflow": {
            "status": "input_received",
            "responses": [
                {"key": "a", "response": "A"},
                {"key": "b", "response": "B"},
            ],
        },
        "_legacy": False,
    }


def test_answer_envelope_selects_only_the_continue_target_group(tmp_path):
    root = tmp_path / "interventions"
    root.mkdir()
    for group_id, key in (("old-group", "old"), ("current-group", "current")):
        (root / f"{group_id}.json").write_text(json.dumps({
            "request_id": group_id,
            "source": "agent",
            "key": key,
            "prompt": f"{key}?",
            "status": "answered",
            "response": key.upper(),
            "call_id": "0001",
            "session_id": "sid-1",
            "request_group_id": group_id,
            "request_index": 0,
        }))

    assert answered_for_call(tmp_path, "0001", "current-group") == {
        "__loopflow": {
            "status": "input_received",
            "responses": [{"key": "current", "response": "CURRENT"}],
        },
        "_legacy": False,
    }


def test_second_agent_group_with_same_key_creates_a_new_request(tmp_path):
    from loopflow.infrastructure.intervention import (
        InterventionIdentity,
        InterventionPending,
        answer_requests,
        request_or_answer,
    )

    def identity(group_id):
        return InterventionIdentity(
            key="scope",
            prompt="Scope?",
            source="agent",
            options=("small", "large"),
            allow_custom=False,
            resume_mode="continue",
            call_id="0001",
            session_id="sid-1",
            request_group_id=group_id,
        )

    with pytest.raises(InterventionPending) as first:
        request_or_answer(tmp_path, "run", identity("group-1"))
    answer_requests(tmp_path, "run", [{
        "request_id": first.value.request["request_id"],
        "response": "small",
    }])
    with pytest.raises(InterventionPending) as second:
        request_or_answer(tmp_path, "run", identity("group-2"))

    assert second.value.request["request_id"] != first.value.request["request_id"]
    assert len(list((tmp_path / "interventions").glob("*.json"))) == 2


def test_batch_write_reports_when_compensating_rollback_also_fails(tmp_path):
    from loopflow.infrastructure.intervention import (
        InterventionPersistenceError,
        answer_requests,
    )

    root = tmp_path / "interventions"
    root.mkdir()
    for request_id in ("first", "second"):
        (root / f"{request_id}.json").write_text(json.dumps({
            "request_id": request_id, "source": "agent", "key": request_id,
            "prompt": "?", "options": [], "allow_custom": True,
            "status": "pending", "resume_mode": "continue",
        }))

    writes = 0

    def fail_commit_and_rollback(*args, **kwargs):
        nonlocal writes
        writes += 1
        if writes >= 2:
            raise OSError("persistent disk failure")

    with patch(
        "loopflow.infrastructure.intervention.atomic_write_json",
        side_effect=fail_commit_and_rollback,
    ), pytest.raises(InterventionPersistenceError, match="rollback failed"):
        answer_requests(tmp_path, "run", [
            {"request_id": "first", "response": "yes"},
            {"request_id": "second", "response": "yes"},
        ])


def test_runner_assigns_a_new_group_to_second_same_key_control(tmp_path):
    from loopflow.application.runner import AgentRunner
    from loopflow.infrastructure.context import RunContext
    from loopflow.infrastructure.intervention import (
        InterventionPending,
        answer_requests,
        list_requests,
    )

    ctx = RunContext(run_id="run", run_dir=tmp_path)
    runner = AgentRunner(None, _backend(), ctx, lambda *args, **kwargs: [])
    control = _control([{
        "key": "scope", "prompt": "Scope?", "options": [],
        "allow_custom": True,
    }])

    with pytest.raises(InterventionPending):
        runner._handle_control_result(control, "sid-1", "0001")
    first = list_requests(tmp_path)[0]
    answer_requests(tmp_path, "run", [{
        "request_id": first["request_id"], "response": "first",
    }])
    with pytest.raises(InterventionPending):
        runner._handle_control_result(control, "sid-1", "0001")

    items = list_requests(tmp_path)
    assert len(items) == 2
    assert len({item["request_group_id"] for item in items}) == 2


def test_legacy_agent_requests_derive_stable_group_without_rewrite(tmp_path):
    root = tmp_path / "interventions"
    root.mkdir()
    paths = []
    for request_id, key, created in (("b", "b", "2026-01-02T00:00:00Z"), ("a", "a", "2026-01-01T00:00:00Z")):
        path = root / f"{request_id}.json"
        path.write_text(json.dumps({
            "request_id": request_id, "source": "agent", "key": key,
            "prompt": f"{key}?", "status": "answered", "response": key,
            "call_id": "0001", "session_id": "sid-1", "created_at": created,
        }))
        paths.append(path)
    before = [path.read_bytes() for path in paths]
    envelope = answered_for_call(tmp_path, "0001")
    assert envelope["_legacy"] is True
    assert [item["key"] for item in envelope["__loopflow"]["responses"]] == ["a", "b"]
    assert [path.read_bytes() for path in paths] == before


def test_recovery_reaches_multiple_continue_targets_with_isolated_envelopes(tmp_path):
    from loopflow.application.runner import AgentRunner
    from loopflow.domain.marshalling import build_intervention_prompt
    from loopflow.infrastructure.context import RunContext
    from loopflow.infrastructure.recovery import append_cache_event, call_input_digest

    targets = [
        {"request_group_id": "g1", "call_id": "0001", "session_id": "sid-1"},
        {"request_group_id": "g2", "call_id": "0002", "session_id": "sid-2"},
    ]
    ctx = RunContext(
        run_id="run", run_dir=tmp_path, resume=True, recovery_mode="continue",
        recovery_target_call_id="0001", continue_targets=targets,
    )
    backend = _backend()
    for call_id, user_prompt, session_id, group_id in (
        ("0001", "first", "sid-1", "g1"),
        ("0002", "second", "sid-2", "g2"),
    ):
        prompt = f"{user_prompt}\n\n{build_intervention_prompt()}"
        digest = call_input_digest(
            loop_dir=None, prompt=prompt, schema=None, backend=None, model=None,
            agent_definition=None, execution_options={},
        )
        path = tmp_path / f"{call_id}.jsonl"
        append_cache_event(path, {"type": "agent_start", "call_id": call_id, "input_digest": digest})
        append_cache_event(path, {"type": "agent_done", "call_id": call_id, "input_digest": digest, "status": "failed", "session_id": session_id, "exit_code": 1})
        root = tmp_path / "interventions"
        root.mkdir(exist_ok=True)
        (root / f"{group_id}.json").write_text(json.dumps({
            "request_id": group_id, "source": "agent", "key": group_id,
            "prompt": "?", "status": "answered", "response": group_id,
            "call_id": call_id, "session_id": session_id,
            "request_group_id": group_id, "request_index": 0,
        }))

    calls = []

    def invoke(prompt, session, **kwargs):
        calls.append((json.loads(prompt), kwargs["resume_session_id"]))
        return _events("done", kwargs["resume_session_id"])

    runner = AgentRunner(None, backend, ctx, invoke)
    assert runner.run("first").value == "done"
    assert runner.run("second").value == "done"
    assert ctx.all_continue_targets_reached()
    assert calls == [
        ({"__loopflow": {"status": "input_received", "responses": [{"key": "g1", "response": "g1"}]}}, "sid-1"),
        ({"__loopflow": {"status": "input_received", "responses": [{"key": "g2", "response": "g2"}]}}, "sid-2"),
    ]


def test_continue_answer_envelope_precedes_single_final_append_prompt(tmp_path):
    from loopflow.application.runner import AgentRunner
    from loopflow.domain.marshalling import build_intervention_prompt
    from loopflow.infrastructure.context import RunContext
    from loopflow.infrastructure.recovery import append_cache_event, call_input_digest

    ctx = RunContext(
        run_id="run", run_dir=tmp_path, resume=True, recovery_mode="continue",
        recovery_target_call_id="0001",
        continue_targets=[{
            "request_group_id": "g1", "call_id": "0001",
            "session_id": "sid-1",
        }],
        execution_options={"append_prompt": "final instruction"},
    )
    original_prompt = f"task\n\n{build_intervention_prompt()}"
    digest = call_input_digest(
        loop_dir=None, prompt=original_prompt, schema=None, backend=None,
        model=None, agent_definition=None,
        execution_options={"append_prompt": "final instruction"},
    )
    append_cache_event(tmp_path / "0001.jsonl", {
        "type": "agent_start", "call_id": "0001", "input_digest": digest,
    })
    append_cache_event(tmp_path / "0001.jsonl", {
        "type": "agent_done", "call_id": "0001", "input_digest": digest,
        "status": "failed", "session_id": "sid-1", "exit_code": 1,
    })
    root = tmp_path / "interventions"
    root.mkdir()
    (root / "g1.json").write_text(json.dumps({
        "request_id": "g1", "source": "agent", "key": "scope",
        "prompt": "Scope?", "status": "answered", "response": "small",
        "call_id": "0001", "session_id": "sid-1",
        "request_group_id": "g1", "request_index": 0,
    }))

    prompts = []

    def invoke(prompt, session, **kwargs):
        prompts.append(prompt)
        return _events("done", kwargs["resume_session_id"])

    runner = AgentRunner(None, _backend(), ctx, invoke)
    assert runner.run("task").value == "done"
    assert len(prompts) == 1
    envelope, suffix = prompts[0].split("\n\n<run-append-prompt>\n", 1)
    assert json.loads(envelope) == {
        "__loopflow": {
            "status": "input_received",
            "responses": [{"key": "scope", "response": "small"}],
        }
    }
    assert suffix == "final instruction\n</run-append-prompt>"
    assert prompts[0].count("<run-append-prompt>") == 1


def test_parallel_agent_groups_batch_and_resume_their_own_sessions(tmp_path):
    from loopflow.infrastructure.intervention import (
        InterventionPending,
        answer_requests,
        list_requests,
    )
    from loopflow.runtime import RunContext, agent, parallel, set_context

    backend = _backend()
    resumed = []

    def invoke(prompt, session, **kwargs):
        resume_id = kwargs.get("resume_session_id")
        if resume_id:
            resumed.append((json.loads(prompt), resume_id))
            return _events("done", resume_id)
        key = "left" if "left" in prompt else "right"
        return _events(json.dumps(_control([{
            "key": key, "prompt": f"{key}?", "options": [],
            "allow_custom": True,
        }])), f"sid-{key}")

    set_context(RunContext(run_id="run", run_dir=tmp_path))
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", side_effect=invoke
    ), pytest.raises(InterventionPending):
        parallel([lambda: agent("left task"), lambda: agent("right task")])

    pending = list_requests(tmp_path)
    assert len(pending) == 2
    answer_requests(tmp_path, "run", [
        {"request_id": item["request_id"], "response": f"answer-{item['key']}"}
        for item in pending
    ])
    targets = [{
        "request_group_id": item["request_group_id"],
        "call_id": item["call_id"],
        "session_id": item["session_id"],
    } for item in pending]

    recovery = RunContext(
        run_id="run", run_dir=tmp_path, resume=True, recovery_mode="continue",
        recovery_target_call_id=targets[0]["call_id"], continue_targets=targets,
    )
    set_context(recovery)
    with patch("loopflow.runtime._make_backend", return_value=backend), patch(
        "loopflow.runtime._run_subagent", side_effect=invoke
    ):
        results = parallel([lambda: agent("left task"), lambda: agent("right task")])

    assert [result.value for result in results] == ["done", "done"]
    assert recovery.all_continue_targets_reached()
    assert sorted(session for _, session in resumed) == ["sid-left", "sid-right"]
    assert {
        (payload["__loopflow"]["responses"][0]["key"], session)
        for payload, session in resumed
    } == {("left", "sid-left"), ("right", "sid-right")}


def test_failed_later_continue_target_does_not_requeue_completed_target(tmp_path):
    from loopflow.application.runner import AgentRunner
    from loopflow.domain.agent_def import AgentError
    from loopflow.domain.marshalling import build_intervention_prompt
    from loopflow.infrastructure.context import RunContext
    from loopflow.infrastructure.recovery import append_cache_event, call_input_digest

    targets = [
        {"request_group_id": "g1", "call_id": "0001", "session_id": "sid-1"},
        {"request_group_id": "g2", "call_id": "0002", "session_id": "sid-2"},
    ]
    ctx = RunContext(
        run_id="run", run_dir=tmp_path, resume=True, recovery_mode="continue",
        recovery_target_call_id="0001", continue_targets=targets,
    )
    backend = _backend()
    for call_id, user_prompt, session_id, group_id in (
        ("0001", "first", "sid-1", "g1"),
        ("0002", "second", "sid-2", "g2"),
    ):
        digest = call_input_digest(
            loop_dir=None,
            prompt=f"{user_prompt}\n\n{build_intervention_prompt()}",
            schema=None, backend=None, model=None, agent_definition=None,
            execution_options={},
        )
        path = tmp_path / f"{call_id}.jsonl"
        append_cache_event(path, {"type": "agent_start", "call_id": call_id, "input_digest": digest})
        append_cache_event(path, {"type": "agent_done", "call_id": call_id, "input_digest": digest, "status": "failed", "session_id": session_id, "exit_code": 1})
        root = tmp_path / "interventions"
        root.mkdir(exist_ok=True)
        (root / f"{group_id}.json").write_text(json.dumps({
            "request_id": group_id, "source": "agent", "key": group_id,
            "prompt": "?", "status": "answered", "response": group_id,
            "call_id": call_id, "session_id": session_id,
            "request_group_id": group_id, "request_index": 0,
        }))

    def invoke(prompt, session, **kwargs):
        if kwargs["resume_session_id"] == "sid-2":
            return [{"type": "agent_done", "exit_code": 1, "session_id": "sid-2"}]
        return _events("done", kwargs["resume_session_id"])

    runner = AgentRunner(None, backend, ctx, invoke)
    assert runner.run("first").value == "done"
    assert ctx.remaining_continue_targets() == [targets[1]]
    with pytest.raises(AgentError):
        runner.run("second")
    assert ctx.remaining_continue_targets() == [targets[1]]
