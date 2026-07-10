---
title: Mock Mode Redesign — auto generation from output schema
description: --mock 模式从 shell 执行重构为两档：bash（兼容旧用法）+ auto（根据 output schema 自动生成），删除 echo
type: adr
status: accepted
created: 2026-07-09T14:00:00Z
---

# ADR 0014: Mock Mode Redesign

## Context

`--mock` 源自 subagent-skills 时代——当时 prompt 是 shell 命令，mock 就是执行它。loopflow 的 prompt 是自然语言，shell 执行无意义。需要重新设计 mock 模式，使其适合 loopflow 的 agent 定义体系。

Mock 的职责是**快速迭代，省 API 费用**——让 workflow 作者写完 workflow 后立即跑通，验证流程结构。不是替代 workflow 作者自己的测试。

## Decision

### 两档模式

| 模式 | CLI | 行为 |
|------|-----|------|
| bash | `--mock bash` | 把 prompt 当 shell 执行（兼容旧用法） |
| auto | `--mock auto` | 自动生成 mock 数据。有 `output` schema 时生成合法 dict；无时返回固定字符串 |

删除 `echo` 模式——`auto` 覆盖了它的场景。

### auto 生成规则

```
schema 类型 → mock 值
─────────────────────
string  + enum → 第一个枚举值
string  (无 enum) → 字段名
number  → 0
integer → 0
boolean → false
array   → 空列表 []
object  → 空对象 {}
```

### 示例

```yaml
output:
  type: object
  properties:
    verdict: {type: string, enum: [REPRODUCED, PARTIAL, FAILED, BLOCKED]}
    total_score: {type: number}
    deviations: {type: array}
  required: [verdict, total_score]
```

→ 生成：

```json
{"verdict": "REPRODUCED", "total_score": 0, "deviations": []}
```

### 边界

- **不做遍历**——固定选第一个枚举值，覆盖不同路径是 workflow 作者的事
- **不做嵌套递归**——嵌套 object 生成空对象 `{}`
- **不做参数注入**——mock 值不可配置，不需要 `--mock-values`

## Consequences

### 正面

- Workflow 作者可以快速迭代，不花 API 费用
- auto 模式生成合法数据，workflow 逻辑可完整跑通
- 删除无用的 echo 模式，减少概念

### 代价

- 固定选第一个枚举值，无法自动覆盖不同业务路径（如 REPRODUCED vs FAILED）
- 嵌套 object 和 array 生成空值，可能不够"真实"