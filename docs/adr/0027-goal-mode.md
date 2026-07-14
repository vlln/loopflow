---
title: ADR 0027 — Agent Goal Mode
description: 在 agent 调用层引入 goal 反馈循环，让 agent 内部自主迭代直到完成或阻塞，workflow 层不再需要处理 partial/retry 语义
type: adr
status: accepted
created: 2026-07-13T00:00:00Z
---

# ADR 0027: Agent Goal Mode

## Context

当前 agent 调用是一次性的：`agent(prompt)` → 返回 → workflow 判断结果。这导致两个问题：

1. **可靠性责任落在 workflow 层**。Agent 返回 `partial`（部分完成）时，workflow 需要理解 `retry`/`skip`/`ask_user` 等语义并做出推进决策。workflow 不应承担保证输出可靠性的责任。
2. **Agent 无法自主迭代**。如果数据下载未完成，agent 只能返回 `partial + retry`，由 workflow 重试。但 agent 本身有能力等待、轮询、重试——它缺少的是"继续工作直到完成"的授权。

参考 kimi-code、Codex、Claude Code 的 Goal 模式设计（session 级 goal 循环），将 goal 概念下沉到 agent 调用层——loopflow 的 `runtime.agent()` 内部。

## Decision

在 `agent()` 函数引入 `goal` 参数。当 `goal` 非空时，agent 进入 goal 模式：框架内部循环调用 agent，直到 agent 声明 `complete` 或 `blocked`。

### 核心设计

**1. 两层 Schema 分离**

框架层 `__goal` 与业务层 `output` schema 完全分离，对 workflow 开发者透明：

- 框架注入时自动 wrap 业务 schema，添加 `__goal` 字段
- 提取结果时框架消费 `__goal`，剥离后返回纯业务 output
- Workflow 开发者不知道 `__goal` 的存在

```
业务 schema:                   框架注入后 agent 看到的:
{ properties: {                { properties: {
    figures: {...},                figures: {...},
    summary: {...}                 summary: {...},
  },                               __goal: { status, reason }
}                                },
                                  required: [figures, __goal]
                                }
```

**2. Goal 循环**

```
agent(goal="完成数据获取") →
  _run_with_goal()
    Iter 1: create_session → steering prompt → result → __goal=active → 继续
    Iter 2: resume_session → steering prompt → result → __goal=blocked → 计数1
    Iter 3: resume_session → steering prompt → result → __goal=blocked → 计数2
    Iter 4: resume_session → steering prompt → result → __goal=complete → 剥离__goal, 返回
```

**3. 完成信号**

Agent 通过 `__goal.status` 字段主动声明：

| status | 含义 | 框架行为 |
|--------|------|---------|
| `active` | 继续工作 | 进入下一迭代 |
| `complete` | 目标达成 | 剥离 __goal，返回业务 result |
| `blocked` | 遇到阻塞 | 同一 reason 连续 3 次 → 抛 `GoalBlocked`；否则继续 |

**4. Blocked Audit（3 轮确认）**

防止模型过早放弃：同一阻塞原因必须连续 3 次声明才生效。不同原因重置计数器。

- 第 1 次 blocked("网络超时") → 计数 1，继续
- 第 2 次 blocked("网络超时") → 计数 2，继续
- 第 3 次 blocked("网络超时") → 计数 3，抛 `GoalBlocked`

如果第 2 次换成 blocked("权限不足") → 计数器重置为 1。

**5. 框架层提示词注入**

Goal 模式的 steering prompt 由框架自动生成，不暴露到 agent 定义或 workflow：

- 首次迭代：注入 goal 目标 + Completion Audit 规则 + Blocked Audit 规则
- 后续迭代：注入迭代计数 + 继续指令
- 所有注入通过 prompt 追加（不修改 agent body），复用现有 schema 注入路径

**6. 迭代上限**

`goal_max_iterations`（默认 10）硬上限防止无限循环。达到后抛 `GoalBlocked`。

### 与现有机制的复用

- **Schema 提取**：复用现有 `json.loads` → `extract_json` "尽力而为"路径
- **Session 管理**：首次 `create_session`，后续 `resume_session`（所有 backend 已支持）
- **Schema 注入**：复用现有 `schema_hint` 追加到 prompt 末尾的机制

### API

```python
def agent(
    prompt: str,
    *,
    schema: dict | None = None,
    max_retries: int = 3,
    goal: str | None = None,           # NEW
    goal_max_iterations: int = 10,     # NEW
    ...
) -> dict | str:
```

当 `goal` 为 `None` 时行为不变（向后兼容）。当 `goal` 非空时进入 goal 模式。

### Agent 定义不变

`goal` 是运行时参数，不在 agent frontmatter 中定义。agent 定义文件无需修改。

## Consequences

### 正面

- Workflow 层简化：不再需要 `_check_phase()` 处理 `partial`/`retry` 语义
- Agent 可靠性提高：框架保证 agent 内部迭代直到完成或真阻塞
- 对业务透明：`__goal` schema wrapper 完全由框架管理

### 负面

- 单次 agent 调用可能消耗更多 token（多轮迭代）
- 增加 `GoalBlocked` 异常，workflow 需处理（或放任崩溃由 resume 恢复）
- 需要 backend 支持 `resume_session`（当前所有 backend 已支持）

### 风险

- Agent 可能"自我感觉良好"提前声明 complete → Completion Audit 规则缓解
- 上下文膨胀（多轮 resume 同一 session）→ 迭代上限缓解

## 替代方案

### 方案 A：Workflow 层 goal 循环

在 workflow.py 中实现 retry 循环，而非 runtime 层。

- 优点：实现简单，不修改 runtime
- 缺点：每个 workflow 都要重复实现；无法利用 session resume 累积上下文

**拒绝**：可靠性应该封装在框架层，不应由每个 workflow 重复实现。

### 方案 B：外部 evaluator agent

用独立 agent 判断 goal 是否完成（类似 Claude Code 的 stop hook evaluator）。

- 优点：评估更客观
- 缺点：成本翻倍；增加延迟

**拒绝**：当前阶段采用"信任模型"（self-declare + audit rules），外部 evaluator 作为未来增强方向。

## 验证

| 项目 | 验证方式 |
|------|---------|
| Goal 循环正确性 | 单元测试：mock backend 返回 active→active→complete |
| Blocked audit | 单元测试：mock backend 返回 3 次相同 blocked reason |
| Schema wrapper | 单元测试：业务 schema 不被污染，__goal 正确剥离 |
| 向后兼容 | 单元测试：不传 goal 时行为不变 |
| Resume session | 集成测试：第二次迭代复用同一 session |