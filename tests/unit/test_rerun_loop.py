"""ADR-0058 / BL-062: validation-driven rerun orchestration unit tests.

纯逻辑测试，stage_fn 用 mock（不依赖真实 backend / agent 调用）。
覆盖：顺序执行、回退重跑、预算耗尽、未知路由、validate 异常传播、Stage 透传。
"""

from __future__ import annotations

import pytest

from loopflow.domain.rerun_loop import (
    RerunOutcome,
    RerunResult,
    RouteDecision,
    Stage,
    run_rerun_loop,
)


def _stages(names=("A", "B", "C")):
    return [Stage(name=n, prompt=f"prompt-{n}") for n in names]


def _recording(fn):
    """包装 stage_fn 记录执行顺序。"""
    calls = []

    def wrapper(stage, context):
        calls.append(stage.name)
        out = fn(stage, context) if fn else RerunOutcome(value={"stage": stage.name})
        return out

    return wrapper, calls


def test_linear_execution_when_validate_none():
    """validate 恒 None → 各阶段各执行一次，顺序执行，无回退。"""
    fn, calls = _recording(None)
    r = run_rerun_loop(_stages(), validate=lambda: None, stage_fn=fn, budget=3)
    assert r.status == "complete"
    assert calls == ["A", "B", "C"]
    assert r.stages_run == 3
    assert r.reruns == 0


def test_rerun_on_route_key():
    """validate 首次返回 route_key → 回退到 route_map 指定阶段重跑其下游。"""
    fn, calls = _recording(None)
    validate_results = iter([RouteDecision("data"), None])  # 第一轮末位返回 data，第二轮通过

    def validate():
        return next(validate_results)

    r = run_rerun_loop(
        _stages(), validate=validate, route_map={"data": "B"}, budget=2, stage_fn=fn,
    )
    assert r.status == "complete"
    # A B C 跑完 → 末位校验返回 data → 回退到 B → B C → 校验 None 终止
    assert calls == ["A", "B", "C", "B", "C"]
    assert r.reruns == 1
    assert r.stages_run == 5


def test_budget_exhausted():
    """持续返回 route_key → budget 次回退后耗尽终止，如实记录。"""
    fn, calls = _recording(None)
    r = run_rerun_loop(
        _stages(), validate=lambda: RouteDecision("data"), route_map={"data": "B"}, budget=2, stage_fn=fn,
    )
    assert r.status == "exhausted"
    assert "预算耗尽" in r.reason
    assert r.reruns == 2  # 两次回退后预算 0 → 第三次校验时耗尽
    # 初始 ABC + 2 次回退 BC = 7 次 stage 执行
    assert r.stages_run == 3 + 2 * 2
    assert calls == ["A", "B", "C", "B", "C", "B", "C"]


def test_unknown_route_key_terminates():
    """route_key 不在 route_map → 终止（不无限回退），reason 说明。"""
    r = run_rerun_loop(
        _stages(), validate=lambda: RouteDecision("nope"), route_map={"data": "B"}, budget=5,
    )
    assert r.status == "exhausted"
    assert "不在 route_map" in r.reason


def test_route_target_not_in_stages():
    """route_map 目标不在阶段清单 → 终止。"""
    r = run_rerun_loop(
        _stages(), validate=lambda: RouteDecision("data"), route_map={"data": "Z"}, budget=5,
    )
    assert r.status == "exhausted"
    assert "不在阶段清单" in r.reason


def test_validate_exception_propagates():
    """validate 抛异常 → 传播给调用方（不吞异常）。"""
    def bad_validate():
        raise RuntimeError("validate boom")

    with pytest.raises(RuntimeError, match="validate boom"):
        run_rerun_loop(_stages(), validate=bad_validate, budget=5)


def test_budget_zero_is_linear():
    """budget=0 → 线性执行，validate 结果被忽略（无回退）。"""
    fn, calls = _recording(None)
    r = run_rerun_loop(
        _stages(), validate=lambda: RouteDecision("data"), route_map={"data": "B"}, budget=0, stage_fn=fn,
    )
    assert r.status == "complete"
    assert calls == ["A", "B", "C"]
    assert r.reruns == 0


def test_stage_fields_passed_to_fn():
    """Stage 全部字段（含 extra）透传给 stage_fn。"""
    seen = {}

    def fn(stage, context):
        seen["name"] = stage.name
        seen["goal"] = stage.goal
        seen["agent_def"] = stage.agent_def
        seen["extra"] = stage.extra
        return RerunOutcome(value={"ok": True})

    stages = [
        Stage(name="X", prompt="p", agent_def="ad", goal="g", goal_max_iterations=3,
              extra={"k": "v"}),
    ]
    r = run_rerun_loop(stages, validate=lambda: None, stage_fn=fn)
    assert r.status == "complete"
    assert seen == {"name": "X", "goal": "g", "agent_def": "ad", "extra": {"k": "v"}}


def test_empty_stages():
    """空阶段清单 → 直接 complete。"""
    r = run_rerun_loop([], validate=lambda: RouteDecision("x"), budget=3)
    assert r.status == "complete"
    assert r.stages_run == 0


def test_value_from_last_stage():
    """末位阶段返回值作为 result.value（complete 时）。"""
    def fn(stage, context):
        return RerunOutcome(value={"stage": stage.name, "done": True})

    r = run_rerun_loop(_stages(), validate=lambda: None, stage_fn=fn)
    assert r.status == "complete"
    assert r.value == {"stage": "C", "done": True}


# ── 信息传递：路由决策 message → 重跑阶段 context["feedback"] ────────────
def test_feedback_delivered_to_rerun_stage():
    """validate 返回带 message 的 RouteDecision → 重跑阶段（及后续阶段）的
    context["feedback"] 携带该 message（信息传递通道）。"""
    seen = []

    def fn(stage, context):
        seen.append((stage.name, context.get("feedback")))
        return {"stage": stage.name}

    decisions = iter([
        RouteDecision("data", message="数据下载不完整：GSE136831 传输层失败"),
        None,
    ])

    def validate():
        return next(decisions)

    r = run_rerun_loop(
        _stages(), validate=validate, route_map={"data": "B"}, budget=2, stage_fn=fn,
    )
    assert r.status == "complete"
    # 首轮 A/B/C：feedback 全 None；回退后 B/C：feedback=message
    assert seen == [
        ("A", None),
        ("B", None),
        ("C", None),
        ("B", "数据下载不完整：GSE136831 传输层失败"),
        ("C", "数据下载不完整：GSE136831 传输层失败"),
    ]


def test_feedback_none_when_no_message():
    """RouteDecision 无 message → context["feedback"]=None（不传空串/占位）。"""
    seen = []

    def fn(stage, context):
        seen.append(context.get("feedback"))
        return {}

    decisions = iter([RouteDecision("data"), None])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"data": "B"},
                   budget=2, stage_fn=fn)
    assert seen == [None, None, None, None, None]


def test_feedback_updates_on_consecutive_reruns():
    """多次回退时 feedback 取**最近一次**路由决策的 message。"""
    seen = []

    def fn(stage, context):
        seen.append(context.get("feedback"))
        return {}

    decisions = iter([
        RouteDecision("data", message="第一轮：数据不符"),
        RouteDecision("data", message="第二轮：仍不符"),
        None,
    ])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"data": "B"},
                   budget=3, stage_fn=fn)
    # ABC | B C(第一轮 feedback) | B C(第二轮 feedback) | B C(通过，feedback 保持第二轮)
    assert seen[0:3] == [None, None, None]
    assert seen[3] == "第一轮：数据不符"
    assert seen[5] == "第二轮：仍不符"  # 第三次回退后的 B
    assert seen[-1] == "第二轮：仍不符"


# ── session 恢复通道：回退重跑时携带该阶段上次 backend session ──────────
def test_resume_session_id_delivered_on_rerun():
    """阶段首次调用返回 backend_sid → 回退重跑时 context['resume_session_id']
    携带该 sid（session 恢复通道）。"""
    seen = []
    # 按阶段返回不同 sid：A→"sid-A"、B→"sid-B"、C→"sid-C"
    sid_map = {"A": "sid-A", "B": "sid-B", "C": "sid-C"}

    def fn(stage, context):
        seen.append((stage.name, context.get("resume_session_id")))
        return RerunOutcome(value={"stage": stage.name}, session_id=sid_map.get(stage.name))

    decisions = iter([RouteDecision("data"), None])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"data": "B"},
                   budget=2, stage_fn=fn)
    # 首轮 A/B/C：无 resume（None）；回退后 B/C：resume=各自上次 sid
    assert seen == [
        ("A", None),
        ("B", None),
        ("C", None),
        ("B", "sid-B"),
        ("C", "sid-C"),
    ]


def test_resume_session_id_updated_on_consecutive_reruns():
    """多次回退时 resume_session_id 取该阶段**最近一次**调用的 sid。"""
    seen = []
    sid_counter = {"B": 0}

    def fn(stage, context):
        seen.append((stage.name, context.get("resume_session_id")))
        if stage.name == "B":
            sid_counter["B"] += 1
            return RerunOutcome(value={"stage": stage.name}, session_id=f"sid-B-{sid_counter['B']}")
        return {"stage": stage.name}, None

    decisions = iter([RouteDecision("data"), RouteDecision("data"), None])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"data": "B"},
                   budget=3, stage_fn=fn)
    # 执行序 ABC | B C | B C | B C；B 每次返回递增 sid
    # 首轮 A/B/C 均无 resume；之后每次 B 携带上次 B 的 sid，C 无 sid
    assert [s for s, _ in seen] == ["A", "B", "C", "B", "C", "B", "C"]
    resumes = [r for _, r in seen]
    assert resumes[0:3] == [None, None, None]
    assert resumes[3] == "sid-B-1"   # 第二次 B 携带第一轮 B 的 sid
    assert resumes[5] == "sid-B-2"   # 第三次 B 携带第二轮 B 的 sid


def test_tuple_value_not_misread_as_value_sid():
    """stage_fn 返回的 value 本身是二元 tuple（如坐标）→ 不被误判为 (value, sid)。"""
    def fn(stage, context):
        return (1, 2)  # 裸 tuple value（无 sid）

    r = run_rerun_loop([Stage(name="A", prompt="p")], validate=lambda: None, stage_fn=fn)
    assert r.status == "complete"
    assert r.value == (1, 2)  # 而非 (1, 2) 被拆成 value=1, sid=2


def test_rerun_outcome_session_id_recorded():
    """RerunOutcome(value, session_id) → session_id 记录，回退重跑时 resume 携带。"""
    seen = []

    def fn(stage, context):
        seen.append(context.get("resume_session_id"))
        return RerunOutcome(value={"stage": stage.name}, session_id="sid-abc")

    decisions = iter([RouteDecision("data"), None])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"data": "B"},
                   budget=2, stage_fn=fn)
    # 首轮 B 无 resume；回退 B 携带 sid-abc
    assert seen[1] is None
    assert seen[3] == "sid-abc"


# ── D-3/D-7（对抗审查发现）：入口校验 ─────────────────────────────────
def test_duplicate_stage_names_rejected():
    """重名 stage → ValueError（D-3：by_name 覆盖导致回退错位）。"""
    with pytest.raises(ValueError, match="必须唯一"):
        run_rerun_loop(
            [Stage(name="A", prompt="p1"), Stage(name="A", prompt="p2")],
            validate=lambda: None,
        )


def test_none_stage_rejected():
    """stages 含 None → ValueError（D-7）。"""
    with pytest.raises(ValueError, match="None|Stage"):
        run_rerun_loop([None], validate=lambda: None)


# ── D-4（对抗审查发现）：session 清除语义 ─────────────────────────────
def test_session_cleared_when_stage_returns_none_sid():
    """阶段返回 None sid → 清除旧记录，后续回退不再 resume 陈旧会话（D-4）。"""
    log = []

    def fn(stage, context):
        log.append(context.get("resume_session_id"))
        if len(log) == 1:
            return RerunOutcome(value=1, session_id="sid-A")
        return RerunOutcome(value=1, session_id=None)

    decisions = iter([RouteDecision("data"), RouteDecision("data"), None])

    def validate():
        return next(decisions)

    run_rerun_loop([Stage(name="A", prompt="p")], validate=validate,
                   route_map={"data": "A"}, budget=3, stage_fn=fn)
    assert log == [None, "sid-A", None]  # 第2次 resume 上次；第3次已清除


# ── G 系列覆盖缺口（测试审查 5104e413 建议）────────────────────────────
def test_validate_only_called_at_round_end():
    """validate 只在每轮末位阶段后调用（G1）。"""
    validate_calls = []

    def fn(stage, context):
        return RerunOutcome(value={"stage": stage.name})

    def validate():
        validate_calls.append("validate")
        return None  # 恒通过

    run_rerun_loop(_stages(), validate=validate, budget=3, stage_fn=fn)
    assert validate_calls == ["validate"]  # 只有一轮，末位 C 后调 1 次


def test_budget_one_minimal_exhausted():
    """budget=1 恒 decision → exhausted、reruns==1、stages_run==5（G2）。"""
    r = run_rerun_loop(
        _stages(), validate=lambda: RouteDecision("data"),
        route_map={"data": "B"}, budget=1,
        stage_fn=lambda s, c: RerunOutcome(value={"stage": s.name}),
    )
    assert r.status == "exhausted"
    assert r.reruns == 1
    assert r.stages_run == 5  # ABC + BC
    assert r.reason  # 有耗尽原因


def test_rollback_to_final_stage_terminates():
    """回退目标 = 末位阶段自身（校验反复抱怨末位产物）→ 预算耗尽不�死循环（G3）。"""
    stages = [Stage(name="A", prompt="p1"), Stage(name="B", prompt="p2")]
    r = run_rerun_loop(
        stages, validate=lambda: RouteDecision("x"),
        route_map={"x": "B"}, budget=2,
        stage_fn=lambda s, c: RerunOutcome(value={"stage": s.name}),
    )
    assert r.status == "exhausted"
    assert r.reruns == 2
    assert r.stages_run == 4  # A,B + B + B（回退到末位只重跑 B）


def test_rollback_to_first_stage_reruns_all():
    """回退目标 = 首阶段 → 全量重跑（G4）。"""
    seen = []

    def fn(stage, context):
        seen.append(stage.name)
        return RerunOutcome(value={"stage": stage.name})

    decisions = iter([RouteDecision("x"), None])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"x": "A"},
                   budget=2, stage_fn=fn)
    assert seen == ["A", "B", "C", "A", "B", "C"]


def test_feedback_cleared_by_message_less_decision():
    """有 message 后无 message 的决策 → feedback 回 None（G9）。"""
    seen = []

    def fn(stage, context):
        seen.append(context.get("feedback"))
        return RerunOutcome(value={"stage": stage.name})

    decisions = iter([
        RouteDecision("data", message="m1"),
        RouteDecision("data"),  # 无 message
        None,
    ])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"data": "B"},
                   budget=3, stage_fn=fn)
    # ABC | B(m1) C | B(None) C | B(None) C——第 2 次回退轮 feedback 已清除
    assert seen[0:3] == [None, None, None]
    assert seen[3] == "m1"
    assert seen[5] is None  # 第二次回退轮 feedback 已清除
    assert seen[-1] is None


# ── G7（复审确认）：emit_log 回调断言 ─────────────────────────────────
def test_emit_log_lines_cover_stages_and_rerun():
    """emit_log 收到每阶段执行行 + 回退行（G7）。"""
    logs = []

    def fn(stage, context):
        return RerunOutcome(value={"stage": stage.name})

    decisions = iter([RouteDecision("data"), None])

    def validate():
        return next(decisions)

    run_rerun_loop(_stages(), validate=validate, route_map={"data": "B"},
                   budget=2, stage_fn=fn, emit_log=logs.append)
    stage_lines = [l for l in logs if l.startswith("rerun: stage=")]
    rerun_lines = [l for l in logs if "回退到" in l]
    assert len(stage_lines) == 5  # A B C B C
    assert len(rerun_lines) == 1  # 一次回退
    assert rerun_lines[0].startswith("rerun: route_key='data' → 回退到 B")


def test_non_string_stage_name_rejected():
    """Stage.name 非 str → ValueError（复审备注：不可哈希 name 不再抛 TypeError）。"""
    with pytest.raises(ValueError, match="非空 str"):
        run_rerun_loop([Stage(name=1, prompt="p")], validate=lambda: None)


# ── 终审低-1/低-2（验收审查 41528686）：budget 校验 + goal sid 语义 ──────
def test_budget_type_validated():
    """budget 非 int / 负数 / bool → ValueError（终审低-1）。"""
    for bad in (-1, 1.5, True, "2"):
        with pytest.raises(ValueError, match="非负 int"):
            run_rerun_loop([Stage(name="A", prompt="p")], validate=lambda: None,
                           budget=bad)
