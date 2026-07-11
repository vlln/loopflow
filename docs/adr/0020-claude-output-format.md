---
title: Claude CLI Output Format — stream-json with thinking/text separation
description: 分析 claude-code CLI 的两种输出模式，确定归一化策略
type: adr
status: proposed
created: 2026-07-11T15:00:00Z
---

# ADR 0020: Claude CLI Output Format

## 动机

claude-code CLI 支持 `--output-format stream-json --verbose`，提供丰富的结构化输出。loopflow 需要确定归一化策略。

## 调研

### Text 模式（默认）

```
claude -p "hello"
```

- **stdout**：纯文本回复（不含 thinking）
- **stderr**：进度信息
- 无结构化元数据

### JSON 模式

```
claude -p "hello" --output-format stream-json --verbose
```

多阶段 JSON 行流：

```json
// 1. 初始化
{"type":"system","subtype":"init","session_id":"...","tools":[...],"model":"...","permissionMode":"...",...}

// 2. thinking token 估算（多次推送）
{"type":"system","subtype":"thinking_tokens","estimated_tokens":1,"estimated_tokens_delta":1,...}

// 3. thinking 内容
{"type":"assistant","message":{"content":[{"type":"thinking","thinking":"The user is asking..."}],...}}

// 4. assistant 文本回复
{"type":"assistant","message":{"content":[{"type":"text","text":"1+1=2"}],...}}

// 5. 结果汇总
{"type":"result","subtype":"success","duration_ms":2784,"num_turns":1,"result":"1+1=2","total_cost_usd":0.013,"usage":{...}}
```

### 关键字段

| type | subtype | 含义 | loopflow 处理 |
|------|---------|------|--------------|
| `system` | `init` | 会话初始化，含 session_id、工具列表、模型 | 提取 session_id |
| `system` | `thinking_tokens` | thinking token 实时估算 | 忽略 |
| `assistant` | — | 消息内容，含 `thinking` 和 `text` 两种 content 类型 | 提取 `text`，`thinking` 可选展示 |
| `result` | `success` / `error` | 最终结果，含 duration、cost、usage | 提取 exit_code |

### 对比

| 维度 | Text 模式 | JSON 模式 |
|------|----------|-----------|
| thinking 分离 | ❌ 混在一起或无 | ✅ 独立 `type: "thinking"` |
| text 精确提取 | ❌ 需靠启发式 | ✅ 独立 `type: "text"` |
| 结构化元数据 | ❌ 无 | ✅ session_id、duration、cost |
| 实现复杂度 | 低 | 中（需解析 JSON 行） |
| 适合 loopflow | 可接受 | ✅ 理想 |

## 决策

**使用 JSON 模式（`--output-format stream-json --verbose`），仅提取 `type: "text"` 内容。**

### 归一化规则

在 `_ClaudeCli` 中：

1. `_cmd_create` 追加 `--output-format stream-json --verbose`
2. `_parse_line` 解析 JSON 行：
   - `type: "assistant"` → 提取 `content` 中 `type: "text"` 的文本，传递给 `text_handler`
   - `type: "assistant"` → `type: "thinking"` 可选：传递给独立的 thinking_handler 或丢弃
   - `type: "result"` → 提取 `subtype` 判断成功/失败
   - `type: "system", subtype: "init"` → 提取 `session_id`

### 理由

1. JSON 模式提供完整的 thinking/text 分离，是归一化的理想范式。其他后端若支持类似格式，应统一到相同处理逻辑。
2. `--verbose` 是获取 thinking 的必要参数，不加则只有 `assistant` 和 `result` 两种 type。
3. 仅提取 `text` 内容传递给 `text_handler`，thinking 可选择性地输出到 stderr 供用户观察。

## 后果

### 正面

- 精确提取 agent 回复文本，无 thinking 污染
- 结构化元数据可用于诊断（duration、cost、usage）
- 为其他后端的归一化提供参考范式

### 负面

- 需要解析 JSON 行（当前 `CliBackend` 的子类 `_parse_line` 已支持）
- `--verbose` 增加输出量（thinking 内容），但 loopflow 可以丢弃

## 约束范围

`src/loopflow/backends/claude.py` — `_ClaudeCli` 的命令构建和行解析逻辑。

## 参考

- kimi ADR 0019：text 模式，strip `•` 前缀
- 本 ADR 的 JSON 模式（thinking/text 分离）可作为其他后端归一化的参考范式