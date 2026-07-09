---
title: Design Boundary — What Loopflow Does Not Do
description: 以 bio-reproducer 真实 loop 需求为压力推演，明确 loopflow 的设计边界：哪些能力由 engine/transport/workflow 作者承担，哪些是 loopflow 的实现补全
type: adr
status: accepted
created: 2026-07-08T12:00:00Z
---

# ADR 0010: Design Boundary — What Loopflow Does Not Do

## Context

以 bio-reproducer（7 阶段生物信息学论文复现 skill）为压力测试用例，推演 loopflow 当前设计是否能支撑真实的多阶段、多 agent、条件路由工作流。bio-reproducer 包含：7 个串行阶段、阶段间文件传递、异步长时间任务、失败回滚、人工审批、全局配置锁定等需求。

经过逐项推演，发现 loopflow 当前设计已经完整。以下是明确排除的能力和理由。

## Decision

### 不做的（设计边界外）

| 能力 | 为什么不做的 | 由谁承担 |
|------|-------------|---------|
| **Phase 间数据流** | loopflow 不关心 agent 产出的语义内容。关心则与任务语义耦合，无法通用 | Workflow 作者用 Python 变量或文件系统传递 |
| **异步 agent 执行** | 某些 agent harness 自带异步工具；没有的可以通过 MCP/Hooks 扩展 | Agent 定义时配置（`requires.mcps`），或 transport 层扩展 |
| **业务路由 / Rollback** | Python 本身就是控制流语言。`while`/`if`/`try` 已足够表达任何路由逻辑。Claude Code Workflow 同样没有内置 rollback | Workflow 作者用 Python 控制流 |
| **硬失败自动重试** | Engine 层（transport timeout + backend error handling）已保证：`agent()` 返回值的调用一定是执行完成的。TimeoutError 和所有异常已在 `_run_subagent` 内部捕获 | Transport / Backend 层 |
| **人工审批通道** | 设置前移，通过 `args` 参数化配置。不做运行时交互 | Workflow 作者通过 `args` 预设审批策略 |
| **Phase 内子步骤可见性** | Phase 是 workflow 作者声明的分组，agent 是执行单元。两者的层级关系通过 events.jsonl 的 `phase` 字段体现，不在 Phase 图层面额外展示 agent 级子步骤 | events.jsonl 记录层级关系 |
| **声明式 Phase 计划** | `meta` dict 已存在，加 `phases` 字段即可。不是新设计 | 实现补全 |
| **全局上下文自动注入** | `args` 已存在。每个 agent 是否使用 args 由 workflow 作者决定 | Workflow 作者在 `agent()` 调用时传入 |

### 要做的（实现补全，非新设计）

以下能力已在 Spec 中设计，但实现未完成：

| # | 能力 | 已有设计 | 缺的实现 |
|---|------|---------|---------|
| A1 | `meta` 声明 `phases` | `meta` dict 已存在，`discovery._load_meta()` 已提取 | 加 `phases` 字段 |
| A2 | Agent 事件携带 `phase` 归属 | events.jsonl 格式已定义，phase 和 agent 事件混合 | agent 事件加 `phase` 字段 |
| A3 | `agent()` 接受 `agent_def` 参数 | `AgentDef` dataclass + `parse_agent()` 已实现 | `agent()` 接入 agent 定义加载 |
| A4 | Agent body 模板渲染 `{{param}}` | Spec 已定义 `{{param}}` 占位符语法 | 模板渲染引擎 |

## Consequences

### 正面

- **设计稳定**：loopflow 的核心抽象（phase / agent / meta / events / resume）经过压力测试，无需增加新概念
- **职责清晰**：loopflow 只做编排和状态管理，不侵入 agent 内部语义
- **与 Claude Code Workflow 对齐**：Claude Code Workflow 同样没有 rollback、异步原语、业务路由——控制流由脚本语言承担

### 负面

- 实现补全（A1-A4）是后续开发的主要工作量，但不涉及设计变更
- Workflow 作者需要理解"哪些由 loopflow 保证，哪些由自己写 Python 控制流处理"

## 验证

本 ADR 为约定/标准类，不涉及技术选型，无需 spike 验证。正确性由 bio-reproducer 推演过程证明——每个排除项都有明确的替代承担者。