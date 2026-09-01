"""Validation-driven rerun orchestration — multi-stage execution with rollback.

ADR-0058 / BL-062. 通用跨阶段回退编排原语：按序执行阶段序列，每轮末尾调用
校验回调；校验返回非 None 的 RouteDecision 时按 route_map 回退到指定阶段重跑
其下游；预算耗尽终止。路由决策携带 message（原因/反馈），经 stage_fn 的
context 传给被路由重跑的阶段——**信息传递通道**（重跑 agent 带着"为什么
重跑、哪步失败"的上下文，而非无脑重试）。

与 ``run_goal_loop`` 同设计语言（goal_loop 迭代在单 agent 内，本原语迭代在
阶段序列上），但不引入 phase 概念（ADR-0052）：阶段仅是编排层抽象，每个
agent() 调用仍各自成为 AgentGraph 节点。

框架不感知任何领域语义：阶段清单、校验回调、路由映射全部由调用方注入；
路由事件由调用方（workflow）写入 State 持久化，本模块不定义事件文件、
不检查格式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class RouteDecision:
    """校验回调的返回值：路由去向 + 触发原因（反馈）。

    message 会被注入重跑阶段 stage_fn 的 context["feedback"]——信息传递
    通道：被路由重跑的阶段可读到"为什么重跑、哪步失败"。
    """

    route_key: str
    message: str | None = None


@dataclass(frozen=True)
class Stage:
    """一个编排阶段：字段与 loop 层 PHASES 注册表对齐，便于直接转换。"""

    name: str
    prompt: str
    agent_def: str | None = None
    label: str | None = None
    goal: str | None = None
    goal_max_iterations: int = 10
    schema: dict | None = None
    # 调用方扩展参数（透传给 stage_fn）
    extra: dict = field(default_factory=dict)


# 校验回调：返回 None=全部达标（终止）；返回 RouteDecision=该目标不达标（回退）。
ValidateFn = Callable[[], RouteDecision | None]
# 阶段执行回调：与 run_goal_loop 的 call_fn 同签名风格。
# 返回 RerunOutcome（推荐，显式 value + session_id）或裸 value（无 session）。
# context 含 stage_index/reruns/feedback/resume_session_id（回退重跑时携带
# 该阶段上次调用的 backend session id——session 恢复通道）。
StageFn = Callable[[Stage, dict], "RerunOutcome | Any"]
# 路由映射：route_key → 重跑起始 stage 名。
RouteMap = dict[str, str]
# 日志回调。
LogFn = Callable[[str], None] | None


@dataclass(frozen=True)
class RerunOutcome:
    """stage_fn 的显式返回值：阶段结果 + 可选 backend session id。

    D-2 修复：取代 (value, sid) 元组启发式（避免 value 本身是二元 tuple
    时被误判）。stage_fn 返回 RerunOutcome 携带 session_id；返回**裸 value**
    视为无 session。**不支持 (value, sid) 元组**——二元 tuple 本身就是合法
    value（如坐标），元组路径已被 RerunOutcome 取代。
    """

    value: Any = None
    session_id: str | None = None


@dataclass(frozen=True)
class RerunResult:
    """一次 rerun_loop 执行的结果。"""

    status: str  # "complete" | "exhausted"
    value: Any = None       # 最后一个 stage 的返回值（complete 时）
    stages_run: int = 0     # 实际执行的 stage 次数（含回退重跑）
    reruns: int = 0         # 回退次数
    reason: str = ""        # exhausted 时的原因


def run_rerun_loop(
    stages: list[Stage],
    validate: ValidateFn,
    route_map: RouteMap | None = None,
    budget: int = 0,
    stage_fn: StageFn | None = None,
    emit_log: LogFn = None,
) -> RerunResult:
    """按序执行 stages；每轮末尾调用 validate()；回退重跑直到预算耗尽。

    Args:
        stages: 阶段清单，按执行顺序（name 必须唯一）。
        validate: 校验回调 → RouteDecision | None（None=达标终止）。
        route_map: {route_key: stage_name}——回退目标（该阶段及其下游重跑）。
        budget: 回退预算；0=线性执行（不校验回退，仅顺序跑一遍）。
        stage_fn: 阶段执行回调 (stage: Stage, context: dict) ->
            RerunOutcome（携带 session_id）或裸 value（无 session）；
            context 含 stage_index/reruns/feedback（路由决策 message）/
            resume_session_id（回退重跑时该阶段上次调用的 session，供
            agent(resume_session_id=...) 恢复对话历史；缺省用 mock）。
        emit_log: 日志回调。

    Returns:
        RerunResult：complete（validate 通过终止）或 exhausted（预算耗尽）。

    Raises:
        ValueError: budget 非非负 int；stages 含 None/非 Stage/name 非空 str
            不满足/重名（D-3/D-7）。
    """
    if not stages:
        return RerunResult(status="complete", value=None)

    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        raise ValueError(f"budget 必须为非负 int，收到 {budget!r}")
    if any(s is None or not isinstance(s, Stage) for s in stages):
        raise ValueError("stages 含 None 或非 Stage 元素")
    names = [s.name for s in stages]
    if any(not isinstance(n, str) or not n for n in names):
        raise ValueError("Stage.name 必须为非空 str")
    if len(set(names)) != len(names):
        dup = {n for n in names if names.count(n) > 1}
        raise ValueError(f"stages name 必须唯一，重复: {sorted(dup)}")

    route_map = route_map or {}
    fn = stage_fn or _default_stage_fn
    by_name = {s.name: s for s in stages}
    log = emit_log or (lambda _m: None)

    idx = 0
    stages_run = 0
    reruns = 0
    remaining = budget
    last_value: Any = None
    feedback: str | None = None  # 最近一次路由决策的 message（信息传递通道）
    # session 恢复通道：stage_name → 该阶段最近一次调用的 backend session id
    session_by_stage: dict[str, str | None] = {}

    while idx < len(stages):
        stage = stages[idx]
        log(f"rerun: stage={stage.name} (stages_run={stages_run + 1})")
        ctx = {
            "stage_index": idx,
            "reruns": reruns,
            "feedback": feedback,
            "resume_session_id": session_by_stage.get(stage.name),
        }
        outcome = fn(stage, ctx)
        # stage_fn 返回约定：RerunOutcome（推荐，显式 value+session_id）或裸 value
        # （无 session）。**不**支持 (value, sid) 元组——二元 tuple 本身就是合法
        # value（如坐标），启发式解析歧义（D-2），已由 RerunOutcome 取代。
        if isinstance(outcome, RerunOutcome):
            last_value = outcome.value
            backend_sid = outcome.session_id
        else:
            last_value, backend_sid = outcome, None
        # D-4：sid 为 None 时清除旧记录（backend 重开会话）；非 None 才记录
        if backend_sid is not None:
            session_by_stage[stage.name] = backend_sid
        elif stage.name in session_by_stage:
            del session_by_stage[stage.name]
        stages_run += 1

        # 非末位阶段：继续下一个
        if idx < len(stages) - 1:
            idx += 1
            continue

        # 末位阶段（校验点）：budget<=0 为线性执行（不调用 validate）；
        # 否则调用 validate 决定是否回退；回退预算耗尽（remaining<=0 且仍
        # 需回退）→ exhausted。
        if budget <= 0:
            return RerunResult(status="complete", value=last_value,
                               stages_run=stages_run, reruns=reruns)

        decision = validate()
        if decision is None:
            return RerunResult(status="complete", value=last_value,
                               stages_run=stages_run, reruns=reruns)

        route_key = decision.route_key
        if remaining <= 0:
            return RerunResult(
                status="exhausted",
                value=last_value,
                stages_run=stages_run,
                reruns=reruns,
                reason=f"route_key={route_key!r} 且回退预算耗尽",
            )

        target = route_map.get(route_key)
        if target is None:
            return RerunResult(
                status="exhausted",
                value=last_value,
                stages_run=stages_run,
                reruns=reruns,
                reason=f"route_key={route_key!r} 不在 route_map（未知路由）",
            )
        if target not in by_name:
            return RerunResult(
                status="exhausted",
                value=last_value,
                stages_run=stages_run,
                reruns=reruns,
                reason=f"route_map 目标 {target!r} 不在阶段清单",
            )

        # 回退到 route_map 指定阶段（dict 保持 stages 插入顺序 → 下标即阶段序）
        idx = list(by_name).index(target)
        reruns += 1
        remaining -= 1
        feedback = decision.message  # 反馈送达重跑阶段（及后续阶段）
        log(f"rerun: route_key={route_key!r} → 回退到 {target}"
            f"（剩余预算 {remaining}）"
            + (f" message={decision.message!r}" if decision.message else ""))

    # 理论上不可达（validate 恒 None 时会在末位返回）；防御兜底
    return RerunResult(status="complete", value=last_value,
                       stages_run=stages_run, reruns=reruns)


def _default_stage_fn(stage: Stage, context: dict) -> RerunOutcome:
    """缺省阶段执行回调：纯逻辑占位，返回阶段名（测试/mock 用）。"""
    return RerunOutcome(value={"stage": stage.name})
