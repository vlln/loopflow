---
title: ADR 0044 — Agent 失败分类与重试/续接策略
description: 将 agent 失败统一退避重试的粗粒度行为细化为五分类（auth/quota/transient/task/unknown）策略；分类来源优先后端结构化上报、stderr 模式匹配兜底，分类写入 agent_done 事件与 run.json error_category
type: adr
status: accepted
created: 2026-07-25T00:00:00Z
---

# ADR 0044: Agent 失败分类与重试/续接策略

## Context

现状对失败的处理是**无差别重试**，三类问题并存：

- `application/runner.py` 对所有失败统一按 3/9/27s 退避重试，`_TRANSIENT_PATTERNS` 仅 6 个 stderr substring，覆盖面极窄
- auth（凭据失效）与 quota（配额耗尽）失败也被照着重试——这类失败重试注定失败，反而**浪费配额、延迟失败反馈**
- `backends/manager.py:185-197` 异常分支把后端异常吞成 `exit_code=1`，类型信息在事件链路上丢失；`AgentError` 无 `category` 字段，上层无从区分失败性质

loopany-platform 的 `classifyFailure` 提供了可借鉴的形态：先分类、再按类别决定策略，而非一招退避打天下。

## Decision

### 1. 失败五分类与来源优先级

失败分类为 `auth` / `quota` / `transient` / `task` / `unknown` 五类。分类来源优先级：

1. **后端结构化上报**：后端在 `agent_done` 事件 payload 中显式携带 `error_category`
2. **stderr 模式匹配兜底**：现有 `_TRANSIENT_PATTERNS` 保留并扩充，仅在无结构化上报时生效

### 2. 策略表

| 分类 | 策略 |
|------|------|
| `transient` | 既有退避重试（3/9/27s，最多 3 次）；recover 可 continue |
| `auth` / `quota` | 不自动重试，直接持久化失败 |
| `task` | 不重试 |
| `unknown` | 按 `task` 处理（保守不重试） |

### 3. 结构化通道

- `backends/manager.py` 的 `agent_done` 事件 payload 增加 `error_category`；异常分支不再吞类型，将异常类型映射为分类
- `AgentError` 增加 `category` 字段，仅携带不做决策
- `run.json` 增加 `error_category`（Spec v15 已声明）

## Alternatives

| 方案 | 评估 |
|------|------|
| 纯 stderr 模式匹配 | 不采纳。各后端错误文本漂移无契约保障，auth/quota 难以靠 substring 可靠识别，误判会把不该重试的失败拖进重试循环 |
| 要求所有后端实现完整错误协议 | 不采纳。违反零依赖与渐进原则；结构化上报是尽力而为，模式匹配兜底保证未上报的后端行为不退化 |

## Consequences

- BR-049；由 AC-026 验收
- 既有 `transient` 行为不变（退避参数、次数、recover 语义均保持），向后兼容
- mock 后端默认不产生结构化分类，走 `unknown` → 按 `task` 处理
- auth/quota 失败从"重试 3 次后失败"变为"立即失败"，失败反馈提前，配额不再被无效重试消耗

## Architecture Boundary

分类产生在 `infrastructure/backends`（结构化上报与异常类型映射）与 `application/runner`（模式匹配兜底 + 策略执行）；domain 的 `AgentError` 只携带 `category` 字段，不参与决策。

## Verification

非技术选型类 ADR：不引入新依赖，退避与事件机制均为既有能力，豁免 spike 验证。正确性由 AC-026 自动化测试直接证明。
