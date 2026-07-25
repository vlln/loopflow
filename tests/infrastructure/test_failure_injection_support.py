"""ADR-0048 失败注入测试基建自证（TEST_INFRA，非 AC-026~029 业务用例）。"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from tests.recovery_support import (
    AttemptResult,
    LoopStateFactory,
    QueueEntryFactory,
    RunFactory,
    SessionBackendFake,
    resolve_error_category,
    run_metadata,
)
from tests.recovery_support.fixtures import FIXTURE_BASE_TIME


def test_scripted_attempts_consumed_in_order_then_fall_back_to_fixed_fields():
    backend = SessionBackendFake(
        create_exit_code=9,
        create_script=[
            AttemptResult(exit_code=1, stderr="boom"),
            AttemptResult(exit_code=2, stderr="boom again"),
        ],
    )

    assert backend.create_session("first") == ("session-1", 1)
    assert backend.create_session("second") == ("session-1", 2)
    # 脚本耗尽后回退既有固定字段
    assert backend.create_session("third") == ("session-1", 9)
    assert [call[0] for call in backend.calls] == ["create", "create", "create"]
    assert [result.exit_code for result in backend.results] == [1, 2, 9]


def test_scripted_transient_failures_then_success_sequence():
    backend = SessionBackendFake(
        create_script=[
            AttemptResult(exit_code=1, stderr="rate limited", error_category="transient"),
            AttemptResult(exit_code=1, stderr="rate limited", error_category="transient"),
            AttemptResult(exit_code=0),
        ]
    )

    outcomes = [backend.create_session(f"attempt-{index}") for index in range(3)]

    assert [exit_code for _, exit_code in outcomes] == [1, 1, 0]
    assert backend.agent_done_payload()["exit_code"] == 0


def test_agent_done_payload_reports_all_four_failure_categories():
    for category in ("auth", "quota", "transient", "task"):
        backend = SessionBackendFake(
            create_script=[
                AttemptResult(exit_code=1, stderr="failure", error_category=category)
            ]
        )
        backend.create_session("prompt")

        payload = backend.agent_done_payload()

        assert payload["error_category"] == category
        assert resolve_error_category(payload) == category


def test_structured_category_wins_over_conflicting_stderr():
    backend = SessionBackendFake(
        create_script=[
            # stderr 命中 transient 模式，但结构化上报为 auth —— 结构化优先（ADR-0044 §1）
            AttemptResult(exit_code=1, stderr="rate limited", error_category="auth")
        ]
    )
    backend.create_session("prompt")
    payload = backend.agent_done_payload()

    assert resolve_error_category(payload) == "auth"
    # 同一 stderr 无结构化上报时走模式匹配兜底
    assert resolve_error_category({"exit_code": 1, "stderr": "rate limited"}) == "transient"


def test_unreported_and_unmatched_failure_resolves_to_unknown():
    backend = SessionBackendFake(create_exit_code=1)
    backend.create_session("prompt")
    payload = backend.agent_done_payload()

    assert "error_category" not in payload
    assert resolve_error_category(payload) == "unknown"
    with pytest.raises(ValueError, match="unknown error category"):
        resolve_error_category({"exit_code": 1, "error_category": "bogus"})


def test_script_behavior_overrides_fixed_behavior_per_attempt():
    backend = SessionBackendFake(
        create_script=[
            AttemptResult(exit_code=1, behavior="exception"),
            AttemptResult(exit_code=0),
        ]
    )

    with pytest.raises(RuntimeError, match="injected backend exception"):
        backend.create_session("first")
    assert backend.create_session("second") == ("session-1", 0)


def test_resume_script_is_independent_of_create_script():
    backend = SessionBackendFake(
        create_script=[AttemptResult(exit_code=0)],
        resume_script=[AttemptResult(exit_code=3, error_category="task")],
    )

    sid, created = backend.create_session("prompt")
    resumed = backend.resume_session(sid, "continue")

    assert (created, resumed) == (0, 3)
    assert backend.agent_done_payload()["error_category"] == "task"


def test_run_factory_stale_since_relative_offset(tmp_path):
    factory = RunFactory(tmp_path / "runs")

    stale_path = factory.create("run-stale", stale_since_offset=-3600)
    fresh_path = factory.create("run-fresh")

    stale = json.loads(stale_path.read_text(encoding="utf-8"))
    expected = (FIXTURE_BASE_TIME - timedelta(seconds=3600)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert stale["stale_since"] == expected
    assert stale["status"] == "running"
    fresh = json.loads(fresh_path.read_text(encoding="utf-8"))
    assert "stale_since" not in fresh  # legacy 形态：无 stale_since 键


def test_run_metadata_carries_error_category_when_failed():
    value = run_metadata("run-failed", status="failed", error_category="quota")

    assert value["status"] == "failed"
    assert value["error_category"] == "quota"
    assert "error_category" not in run_metadata("run-ok")


def test_loop_state_factory_roundtrip(temp_loopflow_home):
    factory = LoopStateFactory(temp_loopflow_home / "loop_state")

    initial = factory.create("hello")
    paused = factory.create(
        "broken",
        consecutive_failures=5,
        paused=True,
        paused_reason="failure_streak:5",
        paused_at="2026-07-22T09:00:00Z",
        last_run_id="run-5",
    )

    assert json.loads(initial.read_text(encoding="utf-8")) == {
        "consecutive_failures": 0,
        "paused": False,
        "paused_reason": None,
        "paused_at": None,
        "last_run_id": None,
    }
    paused_value = json.loads(paused.read_text(encoding="utf-8"))
    assert paused_value["paused"] is True
    assert paused_value["consecutive_failures"] == 5
    assert paused_value["paused_reason"] == "failure_streak:5"


def test_queue_entry_factory_status_roundtrip(temp_loopflow_home):
    factory = QueueEntryFactory(temp_loopflow_home / "queue")

    pending = factory.create("entry-1")
    deferred = factory.create(
        "entry-2", status="deferred", status_reason="resource lock unavailable"
    )
    superseded = factory.create(
        "entry-3", status="superseded", superseded_by="entry-2"
    )

    pending_value = json.loads(pending.read_text(encoding="utf-8"))
    assert pending_value["status"] == "pending"
    assert "status_reason" not in pending_value
    assert "superseded_by" not in pending_value
    deferred_value = json.loads(deferred.read_text(encoding="utf-8"))
    assert deferred_value["status"] == "deferred"
    assert deferred_value["status_reason"] == "resource lock unavailable"
    superseded_value = json.loads(superseded.read_text(encoding="utf-8"))
    assert superseded_value["status"] == "superseded"
    assert superseded_value["superseded_by"] == "entry-2"


def test_transient_patterns_copy_matches_production_runner():
    # 漂移守卫：failure.py 无法模块级导入生产代码（manifest 脚本裸 python3 导入链），
    # 模式表为拷贝，此处断言与生产 _TRANSIENT_PATTERNS 一致
    from loopflow.application.runner import _TRANSIENT_PATTERNS

    from tests.recovery_support.failure import TRANSIENT_PATTERNS

    assert TRANSIENT_PATTERNS == _TRANSIENT_PATTERNS


def test_existing_fake_behavior_regression():
    # ADR-0048 §1 向后兼容：不触碰脚本字段时既有行为逐项保持
    backend = SessionBackendFake(create_exit_code=7, resume_exit_code=8)

    sid, created = backend.create_session("prompt")

    assert (sid, created) == ("session-1", 7)
    assert backend.resume_session(sid, "continue") == 8
    assert backend.calls == [("create", "prompt", None), ("resume", "continue", "session-1")]

    exceptional = SessionBackendFake(resume_behavior="exception")
    with pytest.raises(RuntimeError, match="injected backend exception"):
        exceptional.resume_session("session-1", "continue")

    unknown = SessionBackendFake(create_behavior="bogus")
    with pytest.raises(ValueError, match="unknown backend behavior"):
        unknown.create_session("prompt")
