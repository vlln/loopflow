---
title: AC 0002 — Agent Goal Mode
description: Agent goal 反馈循环的验收标准：goal 循环、完成/阻塞判定、schema wrapper、向后兼容
type: ac
status: active
created: 2026-07-13T00:00:00Z
---

# AC 0002: Agent Goal Mode

## AC-001: Goal 循环 — 正常完成

**描述**：agent 在 goal 模式下自主迭代，直到完成目标。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-N-1 | 单次迭代完成 | goal="获取数据"，agent 首次返回 `__goal.status=complete` | 返回业务 result（__goal 已剥离），不触发额外迭代 |
| AC-001-N-2 | 多次迭代后完成 | goal="获取数据"，agent 返回 active→active→complete | 共 3 次迭代，最终返回业务 result，session 复用 |
| AC-001-N-3 | 无 goal 时行为不变 | 不传 goal 参数 | 行为与当前一致，无 __goal schema 注入 |

### 边界场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-B-1 | 恰好达到迭代上限 | goal_max_iterations=3，agent 第 3 次返回 complete | 正常完成，不抛异常 |
| AC-001-B-2 | goal 字符串为空 | goal="" | 行为与 goal=None 一致（无 goal 模式） |
| AC-001-B-3 | 业务 schema 为 None | goal 非空，schema=None | 框架自动创建 __goal schema，agent 返回纯文本中提取 __goal JSON |

### 异常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-E-1 | Agent 返回无效 JSON | 有 schema 但返回格式错误 | 触发现有 schema retry 机制（非 goal 层），retry 耗尽后抛 AgentError |
| AC-001-E-2 | Backend 不支持 resume | resume_session 抛异常 | 抛 AgentError，不吞异常 |
| AC-001-E-3 | 中途 session 断开 | 第 2 次迭代时 backend 崩溃 | 抛 AgentError，不进入 goal blocked 逻辑 |

### 失败场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-F-1 | 达到迭代上限 | goal_max_iterations=5，agent 始终返回 active | 抛 GoalBlocked，reason="max_iterations"，实际执行 5 次 |
| AC-001-F-2 | 3 次相同 blocked | agent 连续 3 次返回 `__goal.status=blocked`，reason="网络超时" | 第 3 次抛 GoalBlocked，reason="网络超时" |

---

## AC-002: Blocked Audit 机制

**描述**：3 次连续相同阻塞原因才真正 blocked。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-002-N-1 | 不同原因重置计数器 | blocked("网络超时") → blocked("权限不足") → blocked("网络超时") | 不抛异常，继续迭代 |
| AC-002-N-2 | 2 次相同 blocked 后完成 | blocked("网络超时") → blocked("网络超时") → complete | 正常完成，blocked 计数器不生效 |

### 边界场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-002-B-1 | reason 为 None | `__goal.status=blocked` 但无 reason 字段 | 视为 reason="unknown"，计数器正常累加 |
| AC-002-B-2 | reason 大小写敏感 | blocked("Network Timeout") vs blocked("network timeout") | 视为不同 reason（不做 lowercase 归一化） |

### 失败场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-002-F-1 | 3 次不同 blocked 后仍抛 | blocked("A") → blocked("B") → blocked("C")，agent 持续返回 blocked | 不抛（每次重置），直到迭代上限抛 GoalBlocked("max_iterations") |

---

## AC-003: Schema Wrapper 透明性

**描述**：框架层 __goal 对业务层完全透明。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-003-N-1 | 业务 result 不含 __goal | goal 模式完成 | 返回的 dict 不含 __goal 键 |
| AC-003-N-2 | 业务 schema 不被修改 | 传入 `schema={"properties": {"x": {}}}` | 传入的 schema 对象不被框架修改（防御性拷贝） |
| AC-003-N-3 | Agent 看到的 schema 含 __goal | 运行时 | 注入到 prompt 的 schema 含 __goal 字段 |

### 边界场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-003-B-1 | 业务 schema 已有 __goal 字段 | 业务层误用 __goal 字段名 | 框架覆盖（框架 __goal 优先），log warning |
| AC-003-B-2 | Agent 返回了额外的 __goal 属性 | goal 模式，agent 在 __goal 对象中加了多余字段 | 框架只消费 status/reason，多余字段随 __goal 一起剥离 |

---

## AC-004: Steering Prompt 注入

**描述**：框架自动生成的 steering prompt 正确注入。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-004-N-1 | 首次迭代含完整规则 | goal 模式 Iter 1 | prompt 包含 goal 目标文本、Completion Audit 规则、Blocked Audit 规则 |
| AC-004-N-2 | 后续迭代含迭代计数 | goal 模式 Iter 3/10 | prompt 包含 "Iteration 3/10" |
| AC-004-N-3 | 业务 prompt 不被修改 | goal 模式 | agent body 内容不变，steering 在 prompt 层面追加 |

### 边界场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-004-B-1 | goal 文本很长（2000 字符） | goal 字符串 2000 字符 | 完整注入，不截断 |
| AC-004-B-2 | goal 含特殊字符 | goal 含 `{}` `[]` `"` 等 JSON 敏感字符 | 正确转义/处理，不破坏 prompt 结构 |

---

## AC-005: 向后兼容

**描述**：不传 goal 时行为完全不变。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-005-N-1 | 现有 workflow 正常运行 | 不传 goal 参数 | 行为与实现前完全一致 |
| AC-005-N-2 | 现有测试全部通过 | 运行全量测试 | 所有现有测试 pass |
| AC-005-N-3 | 现有 schema 提取逻辑不变 | schema 非空，不传 goal | json.loads → extract_json 路径不变 |