"""ADR-0058 / BL-062: goal_loop 与 runner 的 session 恢复通道直接测试。

覆盖 DESIGN 评审（ADR-0058）条件 3 的两个缺口：
- D-5：run_goal_loop(initial_resume_session_id=...) 首轮迭代恢复外部会话 +
  AgentResult.session_id 携带"最近可用会话"（此前只有代码通读证据）
- D-5/D-6：runner.run(resume_session_id=...) 显式透传到 _execute_once
  （普通/native 分支）+ 返回 AgentResult.session_id

不依赖真实 backend：invoke 用 mock 捕获 resume_session_id 并回传 sid。
"""

from __future__ import annotations

import json
from pathlib import Path

from loopflow.application.runner import AgentRunner
from loopflow.domain.goal_loop import AgentResult, run_goal_loop


# ── run_goal_loop：initial_resume_session_id + AgentResult.session_id ────
def test_goal_loop_initial_resume_and_session_id():
    """initial_resume_session_id 作为首轮 resume 传给 call_fn；返回的
    AgentResult.session_id 携带末次非 None 的 backend sid（D-5）。"""
    calls = []

    def call_fn(prompt, session, resume_session_id):
        calls.append((session, resume_session_id))
        # 首轮返回 sid-A；后续轮返回 None（模拟会话结束）
        sid = "sid-A" if session == "goal_1" else None
        result = json.loads('{"__goal": {"status": "complete"}, "v": 1}')
        return result, sid

    r = run_goal_loop(
        "do work", None, goal="finish", goal_max_iterations=3,
        call_fn=call_fn, initial_resume_session_id="sid-ext",
    )
    assert r.status == "complete"
    # 首轮迭代 resume 外部会话；返回保留最近可用 sid
    assert calls[0] == ("goal_1", "sid-ext")
    assert r.session_id == "sid-A"


def test_goal_loop_session_id_latest_known():
    """多次迭代各返回不同 sid → AgentResult.session_id 取最近一次非 None。"""
    sids = iter(["s1", "s2"])

    def call_fn(prompt, session, resume_session_id):
        try:
            return json.loads('{"__goal": {"status": "active"}}'), next(sids)
        except StopIteration:
            return json.loads('{"__goal": {"status": "complete"}}'), None

    r = run_goal_loop(
        "do work", None, goal="finish", goal_max_iterations=5, call_fn=call_fn,
    )
    assert r.status == "complete"
    assert r.session_id == "s2"  # 末次非 None sid（末轮 None 保留最近可用）


def test_goal_loop_no_session_when_none():
    """所有迭代返回 None sid → AgentResult.session_id 为 None。"""
    def call_fn(prompt, session, resume_session_id):
        return json.loads('{"__goal": {"status": "complete"}}'), None

    r = run_goal_loop(
        "do work", None, goal="finish", goal_max_iterations=3, call_fn=call_fn,
    )
    assert r.status == "complete"
    assert r.session_id is None


# ── runner.run：resume_session_id 透传 + AgentResult.session_id ─────────
def _make_ctx(tmp_path):
    from loopflow.infrastructure.context import RunContext, State

    ctx = RunContext(run_id="t", run_dir=Path(tmp_path), state=State())
    return ctx


def test_runner_run_resume_session_passthrough(tmp_path):
    """runner.run(resume_session_id=...) 透传到 invoke（普通路径），
    AgentResult.session_id 携带后端返回的 sid（D-5/D-6）。"""
    ctx = _make_ctx(tmp_path)
    calls = []

    def invoke(prompt, session, **kwargs):
        calls.append(kwargs.get("resume_session_id"))
        return [{"type": "agent_done", "session_id": "sid-backend",
                 "exit_code": 0, "stderr": ""}]

    runner = AgentRunner(None, None, ctx, invoke)
    result = runner.run("hello", resume_session_id="sid-ext")
    assert result.value == ""
    assert result.session_id == "sid-backend"
    assert calls == ["sid-ext"]  # 透传成功


def test_runner_run_no_resume_session_defaults_none(tmp_path):
    """不传 resume_session_id → invoke 收到 None（默认行为不变）。"""
    ctx = _make_ctx(tmp_path)
    calls = []

    def invoke(prompt, session, **kwargs):
        calls.append(kwargs.get("resume_session_id"))
        return [{"type": "agent_done", "session_id": "sid-x",
                 "exit_code": 0, "stderr": ""}]

    runner = AgentRunner(None, None, ctx, invoke)
    result = runner.run("hello")
    assert calls == [None]
    assert result.session_id == "sid-x"


def test_runner_run_goal_branch_resume_session(tmp_path):
    """goal 分支：run 级 resume_session_id 作为 goal_loop 首轮 resume（D-5）。"""
    ctx = _make_ctx(tmp_path)
    calls = []

    def invoke(prompt, session, **kwargs):
        calls.append((session, kwargs.get("resume_session_id")))
        # goal 模式：invoke 返回文本，_maybe_json 解析出 __goal.complete
        payload = '{"__goal": {"status": "complete"}, "v": 1}'
        return [
            {"type": "agent_message", "content": payload},
            {"type": "agent_done", "session_id": "sid-g",
             "exit_code": 0, "stderr": ""},
        ]

    runner = AgentRunner(None, None, ctx, invoke)
    result = runner.run("do it", goal="finish", goal_max_iterations=3,
                        resume_session_id="sid-ext")
    assert result.status == "complete"
    # 首轮迭代 resume 外部会话（session 名由 ctx 生成，关键在 resume_session_id）
    assert calls[0][1] == "sid-ext"
    assert result.session_id == "sid-g"
