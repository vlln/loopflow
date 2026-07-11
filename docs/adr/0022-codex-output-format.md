---
title: Codex CLI Output Format — codex exec --json
description: 分析 codex CLI 的 JSON 输出格式，确定归一化策略
type: adr
status: accepted
created: 2026-07-11T16:00:00Z
---

# ADR 0022: Codex CLI Output Format

## 动机

Codex 使用 `codex exec` 而非 `-p`，需要确认其 JSON 输出格式和归一化策略。

## 调研

### 命令格式

```
codex exec --json --dangerously-bypass-approvals-and-sandbox [PROMPT]
```

非交互模式使用 `codex exec` 子命令，`--json` 启用 JSONL 输出。

### JSON 输出格式

```
codex exec --json "say hello"
```

```json
{"type":"thread.started","thread_id":"019f521d-..."}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hello"}}
{"type":"turn.completed","usage":{"input_tokens":11915,"cached_input_tokens":8576,"output_tokens":5,"reasoning_output_tokens":0}}
```

### 事件类型

| type | 含义 | 关键字段 |
|------|------|---------|
| `thread.started` | 会话开始 | `thread_id` |
| `turn.started` | 轮次开始 | — |
| `item.completed` | 消息完成 | `item.type: "agent_message"`, `item.text` |
| `turn.completed` | 轮次完成 | `usage` (input_tokens, output_tokens, ...) |

### 特点

- **无流式输出**：Codex 一次性返回完整消息（`item.completed`），不分 chunk
- **无 thinking 可见**：`reasoning_output_tokens` 有计数但内容不暴露
- **无工具调用可见**：不展示中间工具调用过程
- **原生 `--output-schema`**：支持 JSON Schema 约束输出，可替代 loopflow 的 prompt 注入方式

### 对比

| 维度 | Codex | kimi | Claude |
|------|-------|------|--------|
| 命令 | `codex exec` | `kimi -p` | `claude -p` |
| JSON 模式 | `--json` ✅ | `--output-format stream-json` ❌ | `--output-format stream-json --verbose` ✅ |
| thinking 可见 | ❌ | ✅ (stderr) | ✅ (type: "thinking") |
| 流式输出 | ❌ 一次性 | ✅ 逐行 | ✅ 逐行 |
| 工具调用可见 | ❌ | ✅ (stderr) | ✅ |
| 原生 schema | ✅ `--output-schema` | ❌ | ❌ |

## 决策

**使用 `--json` 模式，当前实现已基本正确，仅需补充 `usage` 提取。**

### 归一化规则

当前 `_CodexCli._parse_line` 已实现：

1. `thread.started` → 提取 `thread_id` 作为 session_id
2. `item.completed` (type: "agent_message") → 提取 `text` → `agent_message_chunk`

需补充：

3. `turn.completed` → 提取 `usage` → `usage_update`

### 关于 `--output-schema`

Codex 原生支持 JSON Schema 约束输出（`--output-schema <FILE>`）。这比 loopflow 当前的 prompt 注入方式更可靠。未来可考虑：
- 当 `agent()` 有 `schema` 参数时，将 schema 写入临时文件，通过 `--output-schema` 传递给 Codex
- 属于独立功能，不在本 ADR 范围

## 后果

### 正面

- 输出格式最干净，无前缀、无 thinking 混入
- 已有 JSON 模式，解析逻辑简单
- 原生 schema 支持为未来优化留下空间

### 负面

- 无流式输出，agent 执行期间看不到进度（`item.completed` 一次性返回）
- 无 thinking 可见，调试能力受限

## 约束范围

`src/loopflow/backends/codex.py` — `_CodexCli._parse_line` 补充 `turn.completed` 处理。