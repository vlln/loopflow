---
title: Agent Structured Intervention Design Report
description: 记录 Agent structured requests 与 workflow intervene 的职责边界修订
type: report
status: complete
created: 2026-07-23T17:30:00Z
---

# Summary

0059 DESIGN 已完成。人工介入抽象从“单个 schema request”修订为“Agent structured requests/options + workflow intervene routing gate”：

- Agent structured requests 是主路径，用于给当前 Agent 继续执行所需输入。
- `intervene()` 保留为 workflow-level routing/control gate，回答由 workflow 代码消费。
- 两者共享 Request/Response 持久化和 WebUI，但 consumer、resume mode 和业务语义不同。

# Decisions

| 主题 | 决策 |
|------|------|
| Agent request 用途 | agent-level task input，回答交还给当前 Agent session |
| `intervene()` 用途 | workflow-level routing/control gate，回答用于 workflow 分支 |
| response 类型 | string |
| 预设选项 | request 可携带 string `options` |
| 自定义输入 | `allow_custom=false` 时只能选择 options；`true` 时允许任意非空 string |
| 多 request | 一个 Agent turn 可返回多个 requests |
| 多 pending 来源 | 主要来自并行 Agent worker，或单个 Agent turn 的多 request |
| 恢复模式 | workflow request 默认 `replay`；Agent request 默认 `continue` |

# Changes

- `docs/adr/0036-recovery-intervention.md`
  - 明确两类 intervention 来源和 consumer。
  - 将 Agent 控制输出改为 `requests[]`。
  - 将回答校验从 JSON schema 收敛为 options/custom string 约束。
- `docs/spec/0001-loopflow.md`
  - 更新 BR-035/036/037。
  - 更新 Agent structured intervention 控制对象示例和字段约束。

# Next

进入 TEST_INFRA，补 AC/interface/contract tests：

1. Agent 单 turn 多 requests。
2. request options/allow_custom 校验。
3. batch respond all-or-nothing。
4. WebUI 多问题表单与一次提交。
