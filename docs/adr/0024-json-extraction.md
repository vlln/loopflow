---
title: JSON Extraction — best-effort parse from text-mode backend responses
description: 当 text 模式后端的回复不是纯 JSON 时，使用 output schema 定位并提取 JSON 对象，跳过 retry
type: adr
status: proposed
created: 2026-07-11T17:30:00Z
---

# ADR 0024: JSON Extraction from Text-mode Responses

## 动机

text 模式后端（如 kimi）在 `agent()` 有 `schema` 参数时，agent 可能返回符合 JSON 格式但混杂了其他字符的回复：

```
以下是分析结果：

{"verdict": "PASS", "score": 95}

以上是完整报告。
```

当前 `json.loads()` 直接失败 → retry（最多 3 次）→ 仍失败 → `AgentError`。实际上 JSON 已经在回复中，只是因为被文字包裹而无法解析。

## 决策

### 在 `json.loads` 失败后、retry 之前，使用 output schema 尽力提取 JSON

```python
def _extract_json(text: str, schema: dict) -> dict | None:
    """Extract JSON matching schema from agent text response."""
    required_keys = set(schema.get("properties", {}).keys())
    if not required_keys:
        return None
    
    start = 0
    while True:
        idx = text.find('{', start)
        if idx == -1:
            break
        depth = 0
        for i, ch in enumerate(text[idx:], idx):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[idx:i+1])
                        if isinstance(obj, dict) and required_keys.issubset(obj.keys()):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    start = i + 1
                    break
        else:
            break
    
    return None
```

### 流程

```
json.loads(text)
  → 成功 → 返回
  → 失败 → _extract_json(text, schema)
      → 成功 → 返回（跳过 retry）
      → 失败 → 正常 retry 流程
```

### 关键设计决策

1. **使用 schema 的 properties keys 作为匹配条件**，而非假设 ````json` 或 `{...}` 模式。schema 是唯一可信的"真相源"。
2. **提取成功直接返回，跳过 retry**。节省 API 调用，不浪费 token。
3. **仅在 text 中搜索**。thinking 已在 `thought_handler` 中分离，`text` 中只有 `agent_message_chunk` 内容。
4. **不需要显式判断 `output-format`**。提取逻辑在 `json.loads` 失败时自然触发。`output-format` 是 JSON（如 `stream-json`）不保证 `agent_message_chunk.text` 的内容是纯 JSON——agent 仍可能包裹 markdown。**真正消除提取需求的是 native structured output**（`--json-schema` / `--output-schema`），此时后端保证回复为合法 JSON，`json.loads` 直接成功。

### 与 output-format 和 structured output 的关系

| 概念 | 含义 | 示例 | 保证内容为 JSON？ |
|------|------|------|-----------------|
| `output-format` | 传输格式 | `--output-format stream-json` | ❌ 传输结构化，内容不保证 |
| structured output | 原生 JSON Schema 约束 | `--json-schema`、`--output-schema` | ✅ 模型输出受约束 |
| `agent(schema=...)` | loopflow 的 schema 参数 | 当前：prompt 注入 | ❌ 仅提示，不约束 |

本 ADR 的 JSON 提取是 **prompt 注入 schema 场景的安全网**。当后端支持 native structured output 时，`agent(schema=...)` 应映射到后端原生参数，此时不需要此逻辑。

## 后果

### 正面

- text 模式后端的 schema 成功率大幅提升
- 不浪费 retry 的 API 调用
- 使用 schema 作为匹配条件，误匹配概率极低

### 负面

- 如果 schema 的 required keys 为空（如 `{"type": "object"}`），无法匹配
- 极端情况下，agent 可能在正文中写出与 schema 结构相同的 JSON 示例（概率极低）

## 约束范围

`src/loopflow/agent.py` — 新增 `_extract_json`；`src/loopflow/runtime.py` — `agent()` 的 schema 合规检查流程。

## 与 output-format 和 structured output 的关系

| 概念 | 含义 | 示例 |
|------|------|------|
| `output-format` | 后端输出格式（text/json/stream-json） | `--output-format stream-json` |
| structured output | 后端原生 JSON Schema 约束 | claude `--json-schema`，codex `--output-schema` |
| `agent(schema=...)` | loopflow 的 schema 参数 | 当前：prompt 注入。未来：映射到后端 native structured output |

本 ADR 的 JSON 提取是 text 模式 + prompt 注入 schema 场景的安全网。当后端支持 native structured output 时（如 codex `--output-schema`），不需要此逻辑。