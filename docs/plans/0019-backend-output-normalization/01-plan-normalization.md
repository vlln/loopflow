---
title: Backend Output Normalization — kimi, claude, codex
description: 将 kimi/claude/codex 后端的原生输出归一化为 ACP 兼容事件，更新缓存 schema 从 agent_text 到 agent_message_chunk
type: plan
status: pending
created: 2026-07-11T16:00:00Z
---

# Plan 0019: Backend Output Normalization

## 关联文档

- ADR: [0019-kimi](../adr/0019-kimi-output-format.md), [0020-claude](../adr/0020-claude-output-format.md), [0021-cache](../adr/0021-cache-acp-schema.md), [0022-codex](../adr/0022-codex-output-format.md)
- Spec: [0001-loopflow](../spec/0001-loopflow.md) v8

## 步骤

### 01 — kimi: strip `•` 前缀 + thinking 分离

**文件：** `src/loopflow/backends/kimi.py`

- `_KimiCli._on_stdout_line`：strip 前导 ` • `（如果存在），`text_handler` 传递归一化文本
- 区分 thinking 和 text：kimi 的 thinking 在 stderr，当前 `_on_stderr_line` 已处理。但实测发现 thinking 也在 stdout（`• The user just wants...`）——需要识别 thinking 行（以 `•` 开头且不含中文/实质内容）还是全部当 `agent_message_chunk`

### 02 — claude: 切换到 stream-json 模式

**文件：** `src/loopflow/backends/claude.py`

- `_cmd_create`：追加 `--output-format stream-json --verbose`
- `_parse_line` 重写：解析 JSON 行
  - `type: "system", subtype: "init"` → 提取 `session_id`
  - `type: "assistant", content[type: "thinking"]` → `agent_thought_chunk`
  - `type: "assistant", content[type: "text"]` → `agent_message_chunk`
  - `type: "result"` → 提取 `duration_ms`, `usage` → `agent_done`
  - `type: "system", subtype: "thinking_tokens"` → 忽略

### 03 — codex: 补充 usage 提取

**文件：** `src/loopflow/backends/codex.py`

- `_parse_line`：`turn.completed` → 提取 `usage` → `usage_update`

### 04 — 缓存 schema 迁移：`agent_text` → `agent_message_chunk`

**文件：** `src/loopflow/runtime.py`, `tests/`

- `_write_event`, `_append_cache`, `_write_cache`：`agent_text` → `agent_message_chunk`
- `try_resume`：查找 `agent_message_chunk`（而非 `agent_text`）
- `PhaseGraph.from_events`：更新事件类型过滤
- `tests/`：同步更新所有事件类型断言

## 约束

- 不修改 `events.jsonl` 的 phase 事件格式
- `agent_start` 和 `agent_done` 保留不变
- `agent_done` 新增 `duration_ms` 和 `usage` 字段（可选，从后端提取）
- 向后兼容：旧缓存文件（`agent_text` 类型）仍可被 resume 识别

## 检查点

- [ ] kimi: 输出无 `•` 前缀
- [ ] claude: stream-json 模式正常工作，thinking 和 text 分离
- [ ] codex: usage 信息已提取
- [ ] `{seq}.jsonl` 使用 `agent_message_chunk`（非 `agent_text`）
- [ ] `events.jsonl` 同步更新
- [ ] Resume 兼容旧 `agent_text` 和新 `agent_message_chunk` 两种格式
- [ ] 全部测试通过