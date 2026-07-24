---
title: Agent Structured Intervention Design Plan
description: 修订 Agent structured requests 与 workflow intervene 的职责边界
type: plan
status: done
created: 2026-07-23T17:30:00Z
---

# Goal

冻结下一版人工介入抽象：Agent structured intervention 是主路径，`intervene()` 是 workflow routing gate；两者共享 Request/Response 持久化和 WebUI，但 consumer、resume mode 和业务语义不同。

# Decisions To Freeze

1. Agent structured requests 用于给当前 Agent 继续执行所需的信息，不由 workflow 解释。
2. `intervene()` 用于 workflow 显式人工 gate，回答由 workflow 代码消费，用于路由或控制流。
3. Agent request response 统一为 string。
4. 每个 request 可包含 string `options` 和 `allow_custom`。
5. 一个 Agent turn 可返回多个 requests。
6. 同一 Run 多个 pending requests 主要来自并行 Agent worker，或单个 Agent turn 的多 request 控制输出。
7. WebUI 应展示 pending request form，支持预设选项和手动输入，提交时可一次提交多个回答。

# Steps

1. 修订 ADR 0036 的 intervention 设计段。
2. 修订 Spec 0001 的 BR-035/036 和 Agent 控制输出契约。
3. 写 Report，标记本 DESIGN 容器 done。

# Exit

用户审核通过后进入 TEST_INFRA，补 Agent requests/options、batch response 与 WebUI form 的 AC/interface/contract tests。
