---
title: Cache Normalization Schema — ACP SessionNotification
description: 将 ACP SessionNotification 作为 {seq}.jsonl 的归一化 schema，统一 CLI 和 ACP 后端的输出格式
type: adr
status: proposed
created: 2026-07-11T15:30:00Z
---

# ADR 0021: Cache Normalization Schema — ACP SessionNotification

## 动机

当前 `{seq}.jsonl` 的 schema 过于简陋——只有 `agent_text` + `agent_done` 两种事件类型，无法区分 thinking 和 text、不记录 tool call、不含结构化元数据（duration、usage）。需要一个更丰富的标准化 schema。

## 调研

### ACP SessionNotification 类型

ACP 协议定义了 `session/update` 通知，包含以下 update 类型（`schema.py:5719`）：

| update 类型 | 含义 | loopflow 用途 |
|------------|------|--------------|
| `agent_message_chunk` | agent 文本输出 | ✅ 核心：归一化为 `agent_text` |
| `agent_thought_chunk` | agent 思考过程 | ✅ 可选：独立存储或丢弃 |
| `tool_call_start` | 工具调用开始 | ✅ 可选：可观察性 |
| `tool_call_progress` | 工具调用进度 | ✅ 可选：可观察性 |
| `agent_plan_update` | 计划更新 | 可选 |
| `usage_update` | token 用量 | ✅ 诊断 |
| `current_mode_update` | 模式变更 | 忽略 |
| `session_info_update` | 会话信息 | 忽略 |
| `available_commands_update` | 可用命令 | 忽略 |
| `config_option_update` | 配置变更 | 忽略 |

### 与当前 loopflow 事件映射

| 当前 loopflow | ACP 等价 | 说明 |
|-------------|---------|------|
| `agent_text` | `agent_message_chunk` | 1:1 映射 |
| — | `agent_thought_chunk` | 新增：thinking 独立存储 |
| — | `tool_call_start` / `tool_call_progress` | 新增：工具调用可见 |
| `agent_done` | 无直接等价 | 保留：标记 agent 调用完成（exit_code） |
| `agent_start` | 无直接等价 | 保留：标记 agent 调用开始 |
| `phase` | 无直接等价 | 保留：loopflow 特有 |

## 决策

### `{seq}.jsonl` 使用 ACP 兼容的事件格式

```jsonl
{"type":"agent_start","session":"wf_xxx_1","phase":"Reader"}
{"type":"agent_thought_chunk","content":"The user wants me to..."}
{"type":"agent_message_chunk","content":"开始 Phase 1..."}
{"type":"tool_call_start","tool_call_id":"call_1","title":"Reading paperutils","kind":"read"}
{"type":"tool_call_progress","tool_call_id":"call_1","status":"completed","content":[{"type":"text","text":"..."}]}
{"type":"agent_message_chunk","content":"Phase 1 完成"}
{"type":"agent_done","exit_code":0,"duration_ms":45230,"usage":{"input_tokens":12000,"output_tokens":800}}
```

### 字段语义

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `type` | string | ACP update 类型 | `agent_message_chunk` / `agent_thought_chunk` / `tool_call_start` / `tool_call_progress` |
| `content` | string | ACP `content.text` | 归一化后的纯文本 |
| `tool_call_id` | string | ACP `toolCallId` | 工具调用唯一标识 |
| `title` | string | ACP `title` | 工具调用标题 |
| `kind` | string | ACP `kind` | 工具类别 |
| `status` | string | ACP `status` | pending / in_progress / completed / failed |
| `exit_code` | int | loopflow | 进程退出码（仅 `agent_done`） |
| `duration_ms` | int | ACP `result` / 后端计算 | agent 执行耗时 |
| `usage` | object | ACP `usage_update` | token 用量 |

### `agent_start` 和 `agent_done` 保留

这两个是 loopflow 特有事件，不在 ACP 协议中。`agent_start` 标记调用开始（含 session 和 phase），`agent_done` 标记调用完成（含 exit_code）。Resume 逻辑依赖 `agent_done` 判断是否已完成。

### CLI 后端归一化

每个 CLI 后端将其原生输出转换为 ACP 兼容事件：

- **kimi text 模式**：stdout 的 assistant 文本 → `agent_message_chunk`；stderr 的 thinking → `agent_thought_chunk`
- **claude JSON 模式**：`type: "text"` → `agent_message_chunk`；`type: "thinking"` → `agent_thought_chunk`；`type: "result"` → 提取 duration/usage 写入 `agent_done`
- **其他后端**：后续 ADR 逐个定义

### ACP 后端

未来 ACP 后端（`AcpBackend`）直接透传 `SessionNotification`，无需转换。`AcpBackend._on_update` 当前只处理 `agent_message_chunk`，后续扩展到完整类型。

## 理由

1. **标准化**：ACP 是行业协议（Zed Industries），有明确的 schema 定义和版本管理。避免自造轮子。
2. **向前兼容**：未来引入标准 ACP client 库后，ACP 后端直接透传，零转换成本。
3. **信息完整**：thinking 和 text 分离、tool call 可见、usage 可追溯，远超当前 `agent_text` + `agent_done`。
4. **渐进式**：当前只要求 CLI 后端输出 `agent_message_chunk`（等价于当前的 `agent_text`），`agent_thought_chunk` 和 `tool_call_*` 可选，不阻塞现有功能。

## 依赖

- `agent-client-protocol` Python 包（`pip install agent-client-protocol`）：用于类型定义和验证。添加到 loopflow 的项目依赖。

## 后果

### 正面

- 统一的、有版本管理的 schema
- thinking/text 分离，解决 kimi 输出污染问题
- 为未来 ACP 后端铺平道路

### 负面

- 新增外部依赖 `agent-client-protocol`
- 需要修改 `_write_event`、`_append_cache`、`_write_cache` 的事件格式
- 需要修改 `try_resume` 的事件类型检查
- 需要修改 `PhaseGraph.from_events` 的事件类型过滤

## 约束范围

`src/loopflow/runtime.py` — 事件写入和 resume 逻辑；`tests/` — 事件类型断言更新。

## 参考

- ADR 0019：kimi text 模式，strip `•`
- ADR 0020：claude JSON 模式，thinking/text 分离
- ACP SDK: `~/GithubProjects/acp-python-sdk/src/acp/schema.py`