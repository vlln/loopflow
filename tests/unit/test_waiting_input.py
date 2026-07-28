"""AC-031 unit tests: intervene default/timeout, unattended, lazy timeout,
replay consistency, and the interactive prompt module (ADR-0056)."""

import json
from datetime import datetime, timezone

import pytest

from loopflow.application.execution import execute_workflow


def _create_loop(root, workflow_source):
    loop = root / "hello"
    loop.mkdir(parents=True)
    (loop / "loop.md").write_text("---\nname: hello\nstate:\n  answer: null\n---\n")
    (loop / "workflow.py").write_text(workflow_source)
    return loop


_INTERVENE_DEFAULT = (
    "def run(intervene, state, **kwargs):\n"
    "    state.answer = intervene('approve', '继续？', options=['继续', '停止'],"
    " allow_custom=False, default='继续', timeout=3600)\n"
)


def _only_request(run):
    return next((run / "interventions").glob("*.json"))


# ── AC-031-E-1/E-2: default/timeout declaration validation ───────────────


def test_ac031_e1_invalid_default_raises_value_error(tmp_path):
    """intervene(default=...) failing options/allow_custom validation raises
    ValueError at call time; no request is created."""
    from loopflow.runtime import RunContext, intervene, set_context

    set_context(RunContext(run_dir=tmp_path, run_id="r1"))

    with pytest.raises(ValueError, match="default"):
        intervene("approve", "继续？", options=["a", "b"], allow_custom=False, default="c")

    assert not (tmp_path / "interventions").exists()


def test_ac031_e2_timeout_without_default_raises_value_error(tmp_path):
    """intervene(timeout=...) without a default raises ValueError at call
    time; no request is created."""
    from loopflow.runtime import RunContext, intervene, set_context

    set_context(RunContext(run_dir=tmp_path, run_id="r1"))

    with pytest.raises(ValueError, match="timeout"):
        intervene("approve", "继续？", timeout=60)

    assert not (tmp_path / "interventions").exists()


# ── AC-031-B-1: lazy timeout on replay ────────────────────────────────────


def test_ac031_b1_lazy_timeout_answers_default_on_replay(tmp_path, monkeypatch):
    """A pending request past created_at + timeout is answered with its
    default (response_source=timeout_default) when the run is recovered —
    no daemon or timer involved."""
    loops = tmp_path / "loops"
    _create_loop(loops, _INTERVENE_DEFAULT)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()

    execute_workflow("hello", {}, {}, "run-1", run)
    metadata = json.loads((run / "run.json").read_text())
    assert metadata["status"] == "waiting_input"

    request_path = _only_request(run)
    request = json.loads(request_path.read_text())
    request["created_at"] = "2020-01-01T00:00:00+00:00"
    request_path.write_text(json.dumps(request))

    execute_workflow("hello", {}, {"recover": True, "recovery_mode": "retry"}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    assert metadata["status"] == "done"
    request = json.loads(request_path.read_text())
    assert request["status"] == "answered"
    assert request["response"] == "继续"
    assert request["response_source"] == "timeout_default"
    assert json.loads((run / "state.json").read_text())["answer"] == "继续"


# ── AC-031-F-1: default/timeout changes diverge replay ────────────────────


def test_ac031_f1_default_or_timeout_change_replay_diverges(tmp_path, monkeypatch):
    loops = tmp_path / "loops"
    loop = _create_loop(loops, _INTERVENE_DEFAULT)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run = tmp_path / "run"
    run.mkdir()

    execute_workflow("hello", {}, {}, "run-1", run)
    assert json.loads((run / "run.json").read_text())["status"] == "waiting_input"

    (loop / "workflow.py").write_text(_INTERVENE_DEFAULT.replace("default='继续'", "default='停止'"))
    execute_workflow("hello", {}, {"recover": True, "recovery_mode": "retry"}, "run-1", run)

    metadata = json.loads((run / "run.json").read_text())
    assert metadata["status"] == "failed"
    assert metadata["error_summary"] == "replay_diverged"


# ── AC-031-B-2 / F-2: interactive prompt module ───────────────────────────


def _prompt_request(**overrides):
    request = {
        "request_id": "req-1",
        "key": "approve",
        "prompt": "继续？",
        "options": ["继续", "停止"],
        "allow_custom": False,
        "schema": None,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    request.update(overrides)
    return request


def test_ac031_b2_prompt_countdown_uses_default(monkeypatch):
    """The CLI foreground countdown expires → the default is taken and marked
    response_source=timeout_default."""
    from loopflow.presentation.intervene_prompt import collect_responses

    monkeypatch.setattr(
        "loopflow.presentation.intervene_prompt._select",
        lambda *args: ([], [], []),
    )
    request = _prompt_request(default="继续", timeout_seconds=30)

    responses = collect_responses([request])

    assert responses == [
        {"request_id": "req-1", "response": "继续", "response_source": "timeout_default"}
    ]
    assert "response" not in request


def test_ac031_f2_invalid_input_reprompts_without_persisting(monkeypatch, capsys):
    """An answer outside options (allow_custom=false) is rejected locally and
    re-prompted; nothing is persisted by the prompt module."""
    from loopflow.presentation.intervene_prompt import collect_responses

    inputs = iter(["other", "2"])
    monkeypatch.setattr("builtins.input", lambda *args: next(inputs))
    request = _prompt_request()

    responses = collect_responses([request])

    assert responses == [{"request_id": "req-1", "response": "停止"}]
    assert "Invalid answer" in capsys.readouterr().out
    assert "response" not in request
