---
title: AC 0003 — Agent 层抽象
description: Agent 类封装 Backend + Capabilities，能力 marshalling 遵循"尽力而为"原则，runtime.py 的 agent() 简化为薄封装
type: ac
status: active
created: 2026-07-13T00:00:00Z
---

# AC 0003: Agent 层抽象

## AC-001: Agent 类基本功能

**描述**：`Agent` 类封装 `AgentDef`，提供 `call()` 方法。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-N-1 | Agent 创建并调用 | `ad = parse_agent(...)`; `agent = Agent(ad)`; `agent.call("task", backend)` | 返回 agent 执行结果，行为与当前 `agent()` 一致 |
| AC-001-N-2 | 无 agent_def 时 | `Agent(None).call("task", backend)` | 直接调用 backend，无额外能力注入 |
| AC-001-N-3 | Agent 携带 skills | ad 声明 `skills: [paperutils]`，backend 不支持 native skill | skills 文本注入到 system prompt |

### 边界场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-B-1 | 空 skills 列表 | `skills: []` | 不注入任何 skill 内容 |
| AC-001-B-2 | 无 output schema | ad 无 `output` 字段 | 不注入 schema hint，返回原始文本 |

### 失败场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-F-1 | Skill 文件不存在 | ad 声明 `skills: [nonexistent]` | 抛 RuntimeError（与当前行为一致） |

---

## AC-002: 能力 Marshalling 尽力而为

**描述**：每种能力检查 backend 支持度，选择最优路径。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-002-N-1 | Goal 原生支持 | backend 支持 native goal | 注入 `/goal ...` 到 prompt，单次调用 |
| AC-002-N-2 | Goal 降级 | backend 不支持 native goal | loopflow goal 循环，`__goal` schema wrapper |
| AC-002-N-3 | Schema 原生支持 | backend 支持 structured output | 传 schema 给 backend，不注入文本 hint |
| AC-002-N-4 | Schema 降级 | backend 不支持 structured output | 注入 schema hint 文本到 prompt |

---

## AC-003: runtime.py 简化

**描述**：`runtime.agent()` 变成 `Agent` 类的薄封装。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-003-N-1 | agent() 调用等价 | 任意参数组合 | 行为与重构前完全一致 |
| AC-003-N-2 | agent() 函数签名不变 | 现有 workflow 代码 | 所有现有 workflow 无需修改 |

---

## AC-004: 向后兼容

**描述**：重构不破坏现有功能。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-004-N-1 | 全量测试通过 | 195 tests | 全部 pass |
| AC-004-N-2 | Goal mode 功能不变 | loopflow goal + native goal | 均正常工作 |
| AC-004-N-3 | Skills 功能不变 | 声明 skills 的 agent | 注入行为不变 |