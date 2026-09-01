---
title: ADR 0058 — 校验驱动的重试编排（validation-driven rerun）
description: 框架层提供通用跨阶段回退编排原语；阶段序列、校验回调、路由映射由调用方注入；路由决策携带反馈经 context 送达重跑阶段；回退重跑可恢复该阶段上次 backend session；不引入 phase 概念（ADR-0052）
type: adr
status: accepted
created: 2026-08-31T00:00:00Z
---

# ADR 0058: 校验驱动的重试编排（validation-driven rerun）

## Context

bio-reproducer（loop 层）实现了「Validate 判定复现目标不达标 → 回退到上游阶段重跑 →
预算控制」的跨阶段回退机制，通过 `06_validate/routing.jsonl`（追加式事件文件）+ 
workflow.py 手写 while 循环 + ROUTE_CHAINS 路由表实现。

该机制的通用部分（阶段序列执行、校验后回退、预算控制）是**任何多阶段 agent 工作流**
的共性需求（代码迁移：lint 失败回退；文档生成：校验失败重跑；数据处理流水线：
质检不过重算），不应绑定在单个 loop 里。但当前实现同时存在三个问题：

1. **机制绑定在 loop 层**：routing.jsonl 读写、回退循环、预算消耗都在
   `bio-reproducer/workflow.py`，其他 loop 无法复用；
2. **loop 层自造事件文件**：routing.jsonl 是 loop 自定义格式，需自写自检
   （FC-003 键名白名单）——而框架层已有 `State`（state.json 每次 agent 后自动
   持久化）与 `run_goal_loop`（单 agent 迭代-校验-预算），无需 loop 再造文件；
3. **与 ADR-0052 的 AgentGraph 模型不协调**：现框架以「每个 agent() 调用 = 图节点」
   表达执行图，无 phase 概念；引入 routing 的「阶段」语义需映射到既有模型。

## Decision

框架层新增**校验驱动的重试编排**（validation-driven rerun）通用原语，位于
`src/loopflow/domain/rerun_loop.py`（`run_rerun_loop`，与 `run_goal_loop` 命名
平行）。设计遵循 ADR-0052（不引入 phase 抽象）与 goal_loop 既有模式：

### 1. API 形态

```python
@dataclass(frozen=True)
class RouteDecision:
    route_key: str          # 路由去向
    message: str | None     # 触发原因/反馈（信息传递通道）

@dataclass(frozen=True)
class RerunOutcome:
    value: Any = None                    # 阶段结果
    session_id: str | None = None        # 该阶段本次调用的 backend session id

@dataclass(frozen=True)
class RerunResult:
    status: str              # "complete" | "exhausted"
    value: Any = None        # 末位阶段结果（complete 时）
    stages_run: int = 0      # 实际执行的 stage 次数（含回退重跑）
    reruns: int = 0          # 回退次数
    reason: str = ""         # exhausted 原因

def run_rerun_loop(
    stages: list[Stage],                 # 阶段清单（name 唯一）
    validate: Callable[[], RouteDecision | None],  # 末位阶段后校验回调
    route_map: dict[str, str] | None = None,  # route_key → 重跑起始 stage 名
    budget: int = 0,                     # 回退预算；0=线性执行（validate 不调用，直接 complete）
    stage_fn: Callable[[Stage, dict], RerunOutcome | Any] | None = None,
    emit_log: Callable[[str], None] | None = None,
) -> RerunResult:
    """按序执行 stages；末位阶段后调用 validate()；返回非 None 的 RouteDecision
    时按 route_map 回退重跑；预算耗尽终止。"""
```

- `Stage`：dataclass，含 name/prompt/agent_def/label/goal/goal_max_iterations/
  schema/extra（与现有 PHASES 注册表字段一致，便于 loop 直接转换）
- `validate`：回调，由调用方注入——返回 `None` 表示「全部达标，终止」；返回
  `RouteDecision` 表示「该目标不达标，回退」（route_key 指明去向）
- **信息传递通道**：`RouteDecision.message`（触发原因/反馈）在回退时注入
  重跑阶段 stage_fn 的 `context["feedback"]`（后续阶段持续可见），被路由重跑
  的 agent 可把反馈拼进 prompt——重跑带着"为什么重跑、哪步失败"的上下文，
  而非无脑重试；多次回退取最近一次 message
- **session 恢复通道**：stage_fn 返回 `RerunOutcome(value, session_id)`（或裸
  value）；`session_id` 按阶段记录，回退重跑时注入该阶段 stage_fn 的
  `context["resume_session_id"]`——调用方传给 `agent(resume_session_id=...)`
  即可恢复该阶段上次对话（`agent()` 返回值 `AgentResult.session_id` 提供真实
  后端会话 id；mock 下为 None）。阶段返回 None sid 时清除旧记录（重开会话）
- `route_map`：`{route_key: stage_name}`——回退到哪一阶段（该阶段及其下游重跑）
- `budget`：回退预算（0=线性），来自调用方参数，**框架不写死上限**。**语义**：
  `budget=0` 时 `validate` **完全不调用**、按序执行一遍后直接 complete；
  `budget>0` 时每轮末位阶段后调用 `validate`，每次回退消耗 1，耗尽后仍需回退
  则返回 exhausted（如实记录，不掩盖）
- **末位校验点取舍**：`validate` 仅在**每轮末位阶段后**调用一次（单裁决点），
  而非每阶段后——阶段序列内的完成度由 stage_fn 出参/调用方自检；需要中途
  校验点的场景由调用方**嵌套多次 run_rerun_loop** 组合。与 bio-reproducer
  （Validate 恰为序列末位阶段）精确匹配，保持单裁决点简洁
- **路由结果持久化**：`RerunResult` 返回给调用方；调用方（workflow）自行写入
  `State`（如 `state.rerun_result`），经框架既有 state.json 机制落盘
  （execution 路径在 workflow 返回后强制持久化；CLI 路径仅 agent 级持久化）

### 2. 与既有机制的关系

| 机制 | 关系 |
|------|------|
| `run_goal_loop` | 同设计语言：`run_rerun_loop` 是它的**跨阶段版本**——goal_loop 迭代在单 agent 内，rerun_loop 迭代在阶段序列上。内部阶段仍可各自用 goal 模式；goal 模式阶段经 `initial_resume_session_id` + `AgentResult.session_id` 同样支持回退恢复会话 |
| `State` | 路由结果由**调用方**写入 State（`state.rerun_result` 等），经框架既有 state.json 持久化；原语自身不接触 State（不新增事件文件） |
| ADR-0052 AgentGraph | 不引入 phase 概念。**与 ADR-0052 判据对照**：phase 因「与 Agent 1:1、无独立语义」且带整套框架面（meta 预声明/PhaseGraph/phase 事件/CLI 选项/WebUI 节点）被移除；`Stage` 是调用方注入的编排层数据——无框架生命周期（不入 meta、非图节点、无事件/CLI/WebUI），且与 agent() 调用**非 1:1**（stage_fn 可包裹任意次 agent() 调用）。PHASES 字段对齐是迁移便利的刻意设计，非 phase 复辟 |

### 3. 边界（不做什么）

- **不定义 routing.jsonl 格式**：路由记录是调用方交付物，不属框架职责
- **不内置任何领域路由表**：route_map 完全由调用方注入（框架不知道
  data/provision/run/reader 等业务含义）
- **不检查格式**：RerunOutcome/RerunResult 是框架数据结构，格式由构造保证，
  无需 loop 自检
- **不在 `loopflow.runtime` 暴露**（0115 未实现；需要时经 `loopflow.domain`
  导入 `run_rerun_loop`）

## 影响

- **框架层**：新增 `run_rerun_loop` 原语 + Stage/RouteDecision/RerunOutcome/
  RerunResult 类型 + `AgentResult.session_id` 字段 + `agent()`/`runner.run()`
  `resume_session_id` 参数 + `run_goal_loop` `initial_resume_session_id`；
  无破坏性变更（纯增量）
- **loop 层（bio-reproducer）**：可迁移到 run_rerun_loop（注入 stages/validate/
  route_map），routing.jsonl 不再是机制必需（保留为可选交付记录或删除，
  由 bio-reproducer 侧决定）
- **测试**：新增 unit（顺序执行/回退/预算耗尽/feedback/session 恢复/入口校验）
  + e2e（mock backend 的 demo loop 黑盒，与 bio-reproducer 无关）

## 替代方案

1. **在 loop 层继续手写**（现状）：机制不可复用，loop 自造文件自检，违背框架职责
2. **上移机制但保留 routing.jsonl 为框架格式**：引入框架级自定义文件格式，
   与 State 持久化重复，且使框架感知交付物概念——拒绝
3. **仅提供回调接口不做编排**：调用方仍需手写回退循环，只省了文件读写，
   没有解决"通用编排"需求——不完整
4. **直接扩展 run_goal_loop 为多阶段**：最邻近的替代路径。否决理由：
   `run_goal_loop` 的契约形状是「单 agent 迭代」——goal steering/schema 注入/
   blocked-exhausted 语义都围绕"同一 prompt 反复跑到 complete"；跨阶段回退是
   「阶段序列 + 路由映射 + 回退预算」的序列形状。两种循环语义（迭代上限 vs
   回退预算）合并会使 goal_loop 契约失真、破坏其既有调用方。故保留独立原语，
   `run_rerun_loop` 与 `run_goal_loop` 平行（关系表：goal_loop 迭代在单 agent
   内，rerun_loop 迭代在阶段序列上；内部阶段仍可各自用 goal 模式）

## 验证

- unit：run_rerun_loop 顺序执行（validate 恒 None → 各阶段各跑一次）
- unit：回退（validate 首次返回 key → 回退到 route_map 指定阶段重跑其下游）
- unit：预算耗尽（持续返回 key → budget 次后终止，如实记录）；budget=1 边界
- unit：validate 回调异常传播；重名/None stage 拒绝（入口校验）
- unit：feedback 传递（message → context["feedback"]，多次回退取最近一次）
- unit：session 恢复（stage_fn 返回 sid → 回退重跑 resume_session_id 携带；
  返回 None 清除旧记录）
- e2e：mock backend demo loop（阶段 1 故意失败 → 校验 → 回退 → 阶段 1 修复后
  通过），事件退出码序列如实反映 [1,0,0,0]，黑盒验证，与 bio-reproducer 无关
- 兼容：bio-reproducer 单个 entry 在现有（未迁移）代码上验证不受影响
