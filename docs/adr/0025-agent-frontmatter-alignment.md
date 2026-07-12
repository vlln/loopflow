---
title: ADR 0025 — Agent Frontmatter 格式对齐 Claude Code Subagent Schema
description: 删除 requires 包装层，params 升级为 JSON Schema input，字段对齐 Claude Code subagent frontmatter
type: adr
status: accepted
created: 2026-07-12T00:00:00Z
---

# ADR 0025: Agent Frontmatter 格式对齐 Claude Code

## Context

当前 agent frontmatter 使用 `requires` 包装层，`params` 为退化版 JSON Schema（仅 name + default），与 `output`（完整 JSON Schema）不对称。Claude Code 已有成熟的 subagent frontmatter schema。

## Decision

### 1. 删除 `requires` 包装层

所有字段提升到顶层，减少嵌套。

### 2. `requires.params` → `input`

`input` 使用完整 JSON Schema，与 `output` 对称。

```yaml
# 旧
requires:
  params:
    - language
    - format: markdown

# 新
input:
  type: object
  properties:
    language:
      type: string
    format:
      type: string
      default: markdown
  required:
    - language
```

### 3. 字段对齐 Claude Code

| 旧 | 新 | 说明 |
|----|----|------|
| `requires.skills` | `skills` | 顶层 |
| `requires.mcps` | `mcpServers` | 顶层，对齐 Claude Code |
| `requires.env` | `env` | 顶层 |
| — | `model` | 新增 |
| — | `isolation` | 新增 |
| — | `tools` / `disallowedTools` / `maxTurns` / `hooks` / `effort` / `color` / `background` / `memory` / `permissionMode` | 新增，仅解析接口 |

### 4. 删除 `AgentRequires`

`AgentRequires` 是 `AgentDef` 三个字段的冗余拷贝。后端直接接收 `AgentDef`。

## Consequences

- **破坏性变更**：旧格式 `requires` 不再支持
- 新增 `_input_to_params()` 将 JSON Schema 转换为内部 `ParamSpec`
- 后端接口从 `agent_def: AgentDef | None` 按需取字段
- `initialPrompt` 不采纳（loopflow agent 非 main session agent）

## Alternatives Considered

- **渐进迁移**：同时支持新旧格式 → 增加解析复杂度，用户困惑
- **保留 AgentRequires**：作为后端接口参数 → 与 AgentDef 字段重复，无意义

## References

- [[0023-backend-feature-strategy]] — JSON-first, text fallback 策略
- [[0024-json-extraction]] — jsonschema 提取 JSON