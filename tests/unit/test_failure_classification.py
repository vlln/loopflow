"""Tests for AC-026 Agent 失败分类处理（ADR-0044 / BR-049）。

分类来源优先级：后端结构化上报（agent_done payload error_category）
> stderr 模式匹配兜底 > unknown。transient 保持既有 3/9/27s 退避重试，
auth/quota/task/unknown 不自动重试。
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_mock():
    from loopflow.runtime import set_mock
    set_mock(None)
    yield
    set_mock(None)


@pytest.fixture
def temp_run_dir():
    d = Path(tempfile.mkdtemp()) / "test-run"
    d.mkdir(parents=True)
    yield d


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.create_session.return_value = ("test-sid", 0)
    backend.resume_session.return_value = 0
    backend.supports_native_goal = False
    backend.capabilities.native_goal = False
    return backend


# ── helpers ───────────────────────────────────────────────────────────────

def _agent_with_script(temp_run_dir, mock_backend, script):
    """Drive one agent() call through a scripted _run_subagent.

    script: list of event lists, one per backend attempt.
    Returns (result_or_none, error_or_none, call_count).
    """
    from loopflow.runtime import RunContext, agent, set_context

    ctx = RunContext(run_dir=temp_run_dir)
    set_context(ctx)

    calls = []

    def _mock_run(prompt, session, backend=None, model=None, cwd=None,
                  agent_def=None, cache_path=None, **kwargs):
        calls.append(session)
        return script[min(len(calls), len(script)) - 1]

    result, error = None, None
    with patch("loopflow.runtime._make_backend", return_value=mock_backend):
        with patch("loopflow.runtime._run_subagent", side_effect=_mock_run):
            with patch("time.sleep", return_value=None):
                try:
                    result = agent("test")
                except Exception as exc:  # noqa: BLE001 — asserted by callers
                    error = exc
    return result, error, len(calls)


def _done_events(exit_code, stderr="", error_category=None, text=None):
    events = []
    if text is not None:
        events.append({"type": "agent_message", "content": text})
    done = {"type": "agent_done", "exit_code": exit_code, "stderr": stderr}
    if error_category is not None:
        done["error_category"] = error_category
    events.append(done)
    return events


def _read_events(run_dir):
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _create_failing_loop(loops_root):
    loop = loops_root / "hello"
    loop.mkdir(parents=True)
    (loop / "loop.md").write_text("---\nname: hello\n---\n")
    (loop / "workflow.py").write_text(
        "def run(agent, **kwargs):\n"
        "    agent('boom')\n"
    )
    return loop


def _execute_with_fake_backend(tmp_path, monkeypatch, fake):
    """Run the failing loop end-to-end with SessionBackendFake wired into
    the real manager chain; returns (run_dir, agent_done payloads)."""
    import loopflow.infrastructure.backends.manager as manager
    from loopflow.application.execution import execute_workflow

    loops = tmp_path / "loops"
    _create_failing_loop(loops)
    monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    outer_backend = MagicMock()
    outer_backend.create_session.return_value = ("test-sid", 0)
    outer_backend.resume_session.return_value = 0
    outer_backend.supports_native_goal = False
    outer_backend.capabilities.native_goal = False

    payloads = []
    real_run_subagent = manager._run_subagent

    def _recording(prompt, session, **kwargs):
        events = real_run_subagent(prompt, session, **kwargs)
        payloads.extend(e for e in events if e.get("type") == "agent_done")
        return events

    with patch("loopflow.runtime._make_backend", return_value=outer_backend):
        with patch.object(manager, "_make_backend", return_value=fake):
            with patch("loopflow.runtime._run_subagent", side_effect=_recording):
                with patch("time.sleep", return_value=None):
                    execute_workflow("hello", {}, {}, "run-1", run_dir)
    return run_dir, payloads


# ── 分类函数单测 ──────────────────────────────────────────────────────────

class TestClassifyError:
    def test_structured_report_wins_for_all_five_categories(self):
        from loopflow.application.runner import _classify_error
        for category in ("auth", "quota", "transient", "task", "unknown"):
            assert _classify_error(category, "timeout rate_limit") == category

    def test_structured_report_wins_over_conflicting_stderr(self):
        from loopflow.application.runner import _classify_error
        assert _classify_error("quota", "error: timeout") == "quota"
        assert _classify_error("auth", "rate_limit") == "auth"

    def test_invalid_reported_category_falls_back_to_stderr(self):
        from loopflow.application.runner import _classify_error
        assert _classify_error("bogus", "error: timeout") == "transient"
        assert _classify_error("bogus", "error: ???") == "unknown"

    def test_auth_patterns(self):
        from loopflow.application.runner import _classify_error
        assert _classify_error(None, "HTTP 401 from provider") == "auth"
        assert _classify_error(None, "error: Unauthorized") == "auth"
        assert _classify_error(None, "invalid api key configured") == "auth"

    def test_quota_patterns(self):
        from loopflow.application.runner import _classify_error
        assert _classify_error(None, "insufficient_quota: upgrade plan") == "quota"
        assert _classify_error(None, "error: quota exceeded") == "quota"

    def test_transient_patterns_unchanged(self):
        from loopflow.application.runner import _classify_error
        assert _classify_error(None, "provider.connection_error: terminated") == "transient"
        assert _classify_error(None, "error: rate_limit hit") == "transient"
        assert _classify_error(None, "request timed out") == "transient"

    def test_auth_quota_win_over_transient_substring(self):
        # 保守原则：宁可不重试，不可把 quota/auth 误判为 transient
        from loopflow.application.runner import _classify_error
        assert _classify_error(None, "quota exceeded: request timeout") == "quota"
        assert _classify_error(None, "401 unauthorized: connection_error") == "auth"

    def test_unmatched_and_empty_stderr_resolve_to_unknown(self):
        from loopflow.application.runner import _classify_error
        assert _classify_error(None, "error: something broke") == "unknown"
        assert _classify_error(None, "") == "unknown"


# ── AC-026 场景 ───────────────────────────────────────────────────────────

class TestFailureClassificationScenarios:
    def test_ac026_n1_transient_retries_then_succeeds(self, temp_run_dir, mock_backend):
        """AC-026-N-1: transient 失败退避重试后成功，agent_retry 事件完整。"""
        script = [
            _done_events(1, stderr="error: rate_limit exceeded"),
            _done_events(0, text="recovered"),
        ]
        result, error, calls = _agent_with_script(temp_run_dir, mock_backend, script)

        assert error is None and result.value == "recovered" and calls == 2
        events = _read_events(temp_run_dir)
        retries = [e for e in events if e["type"] == "agent_retry"]
        assert len(retries) == 1
        assert retries[0]["payload"]["attempt"] == 1
        assert retries[0]["payload"]["reason"] == "rate_limit"
        assert retries[0]["payload"]["delay"] == 3
        # agent_done 的 error_category 缺省或 transient（本脚本未上报 → 缺省）
        assert script[0][-1].get("error_category") in (None, "transient")

    def test_ac026_n2_structured_quota_beats_transient_stderr(self, temp_run_dir, mock_backend):
        """AC-026-N-2: 结构化上报 quota + stderr 含 timeout → 不重试。"""
        from loopflow.domain import AgentError
        script = [_done_events(1, stderr="error: timeout", error_category="quota")]

        result, error, calls = _agent_with_script(temp_run_dir, mock_backend, script)

        assert result is None and isinstance(error, AgentError)
        assert error.category == "quota"
        assert calls == 1
        retries = [e for e in _read_events(temp_run_dir) if e["type"] == "agent_retry"]
        assert retries == []

    def test_ac026_n3_run_json_matches_agent_done_category(self, tmp_path, monkeypatch):
        """AC-026-N-3: run.json error_category 与 agent_done payload 一致。"""
        from tests.recovery_support.fakes import AttemptResult, SessionBackendFake
        fake = SessionBackendFake(
            create_script=[AttemptResult(exit_code=1, stderr="boom", error_category="task")]
        )
        run_dir, payloads = _execute_with_fake_backend(tmp_path, monkeypatch, fake)

        metadata = json.loads((run_dir / "run.json").read_text())
        assert metadata["status"] == "failed"
        assert payloads and payloads[-1]["error_category"] == "task"
        assert metadata["error_category"] == payloads[-1]["error_category"]
        assert metadata["error_category"] in ("auth", "quota", "transient", "task", "unknown")

    def test_ac026_b1_auth_failure_fails_without_retry(self, tmp_path, monkeypatch):
        """AC-026-B-1: auth 失败不自动重试，run 直接 failed，error_category=auth。"""
        from tests.recovery_support.fakes import AttemptResult, SessionBackendFake
        fake = SessionBackendFake(
            create_script=[AttemptResult(
                exit_code=1, stderr="HTTP 401 unauthorized", error_category="auth"
            )]
        )
        run_dir, payloads = _execute_with_fake_backend(tmp_path, monkeypatch, fake)

        metadata = json.loads((run_dir / "run.json").read_text())
        assert metadata["status"] == "failed"
        assert metadata["error_category"] == "auth"
        assert payloads[-1]["error_category"] == "auth"
        assert len(fake.calls) == 1
        retries = [e for e in _read_events(run_dir) if e["type"] == "agent_retry"]
        assert retries == []

    def test_ac026_b2_unmatched_failure_is_unknown_no_retry(self, temp_run_dir, mock_backend):
        """AC-026-B-2: 无法匹配的失败 → unknown，按 task 处理不重试。"""
        from loopflow.domain import AgentError
        script = [_done_events(1, stderr="error: something broke")]

        result, error, calls = _agent_with_script(temp_run_dir, mock_backend, script)

        assert result is None and isinstance(error, AgentError)
        assert error.category == "unknown"
        assert calls == 1

    def test_ac026_e1_transient_exhausts_backoff_then_fails(self, temp_run_dir, mock_backend):
        """AC-026-E-1: transient 连续失败 → AgentError(category=transient)，
        agent_retry 共 3 条，退避 3/9/27s。"""
        from loopflow.domain import AgentError
        script = [_done_events(1, stderr="error: timeout")] * 4

        result, error, calls = _agent_with_script(temp_run_dir, mock_backend, script)

        assert result is None and isinstance(error, AgentError)
        assert error.category == "transient"
        assert calls == 4  # 1 次初始 + 3 次重试
        retries = [e for e in _read_events(temp_run_dir) if e["type"] == "agent_retry"]
        assert len(retries) == 3
        assert [e["payload"]["delay"] for e in retries] == [3, 9, 27]
        assert [e["payload"]["attempt"] for e in retries] == [1, 2, 3]


# ── manager 异常映射（ADR-0044 §3） ───────────────────────────────────────

class TestManagerExceptionMapping:
    def _run_with_broken_backend(self, temp_run_dir, instance):
        import loopflow.infrastructure.backends.manager as manager
        from loopflow.infrastructure.context import RunContext, set_context
        set_context(RunContext(run_dir=temp_run_dir))
        with patch.object(manager, "_make_backend", return_value=instance):
            return manager._run_subagent("prompt", "session-1")

    def test_connection_error_maps_to_transient(self, temp_run_dir):
        instance = MagicMock()
        instance.create_session.side_effect = ConnectionError("refused")
        del instance._transport  # 无 transport 的真实后端形态

        events = self._run_with_broken_backend(temp_run_dir, instance)

        done = [e for e in events if e["type"] == "agent_done"][-1]
        assert done["exit_code"] == 1
        assert done["error_category"] == "transient"

    def test_other_exception_maps_to_unknown(self, temp_run_dir):
        instance = MagicMock()
        instance.create_session.side_effect = RuntimeError("weird backend state")
        del instance._transport

        events = self._run_with_broken_backend(temp_run_dir, instance)

        done = [e for e in events if e["type"] == "agent_done"][-1]
        assert done["exit_code"] == 1
        assert done["error_category"] == "unknown"

    def test_structured_category_from_backend_reaches_payload(self, temp_run_dir):
        """后端实例上报 error_category 时，agent_done payload 原样携带。"""
        from tests.recovery_support.fakes import AttemptResult, SessionBackendFake
        fake = SessionBackendFake(
            create_script=[AttemptResult(
                exit_code=1, stderr="insufficient_quota", error_category="quota"
            )]
        )

        events = self._run_with_broken_backend(temp_run_dir, fake)

        done = [e for e in events if e["type"] == "agent_done"][-1]
        assert done["exit_code"] == 1
        assert done["error_category"] == "quota"
        assert done["stderr"] == "insufficient_quota"
