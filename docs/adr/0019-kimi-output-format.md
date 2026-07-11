---
title: Kimi CLI Output Format — text mode with `•` prefix, no viable JSON mode
description: 分析 kimi-code CLI 的两种输出模式，确定归一化策略
type: adr
status: accepted
created: 2026-07-11T15:00:00Z
---

# ADR 0019: Kimi CLI Output Format

## 动机

kimi-code CLI 有两种输出模式，loopflow 需要确定使用哪种以及如何归一化处理输出。

## 调研

### Text 模式（默认）

```
kimi -p "hello"
```

- **stdout**：assistant 回复，每行以 ` • ` 开头（硬编码常量 `run-prompt.ts:95`）
- **stderr**：thinking 内容（进度叙述、工具调用等）
- **session ID**：出现在 stderr，格式 `kimi -r session_xxx`

### JSON 模式

```
kimi -p "hello" --output-format stream-json
```

仅 2 行 JSON：

```json
{"role":"assistant","content":"<最终回复>"}
{"role":"meta","type":"session.resume_hint","session_id":"session_xxx","command":"kimi -r session_xxx","content":"To resume this session: ..."}
```

- **无 thinking**：`stream-json` 丢弃所有 thinking 内容
- **无工具调用过程**：看不到 agent 中间步骤
- **`role` 字段**：`assistant` = 最终回复，`meta` = resume hint

### 对比

| 维度 | Text 模式 | JSON 模式 |
|------|----------|-----------|
| thinking 可见 | ✅ stderr | ❌ 丢弃 |
| 工具调用可见 | ✅ stderr | ❌ 丢弃 |
| 输出结构化 | ❌ 纯文本 + `•` 前缀 | ✅ JSON |
| 信息完整度 | ✅ 完整 | ❌ 极度精简 |
| 适合 loopflow | 可接受（需处理 `•`） | 不适合（信息丢失严重） |

## 决策

**使用 text 模式，在 loopflow 层 strip ` • ` 前缀。**

### 归一化规则

在 `_KimiCli._parse_line` 或 `_on_stdout_line` 中处理：

1. 每行 strip 前导 ` • `（如果存在）
2. 空行跳过
3. stderr 上的 thinking 内容保留（当前 `_on_stderr_line` 已处理，过滤 `•` 和 resume hint）

### 理由

1. JSON 模式信息丢失严重——没有 thinking、没有工具调用过程，用户完全看不到 agent 在做什么。这与 loopflow 的"可观察性"目标矛盾。
2. `•` 前缀是纯文本修饰，strip 成本为零。
3. Text 模式是 kimi 的默认行为，未来版本更可能保持兼容。

## 后果

### 正面

- 保留完整的 thinking + 工具调用可见性
- 归一化后输出干净，不含 `•` 前缀

### 负面

- `•` strip 依赖 kimi 内部实现细节（`run-prompt.ts:95`），未来 kimi 可能改变格式。但这是 kimi 最稳定的 UI 常量之一，变更概率低。
- 如果 kimi 未来改进 JSON 模式（增加 thinking），需重新评估。

## 约束范围

`src/loopflow/backends/kimi.py` — `_KimiCli` 的 stdout 行处理逻辑。