---
title: Backend Feature Strategy — JSON-first, text fallback
description: 所有后端功能（输出格式、skill、结构化输出等）优先使用原生 JSON/结构化模式，仅在原生模式有缺陷时回退到 text 模式
type: adr
status: accepted
created: 2026-07-11T17:00:00Z
---

# ADR 0023: Backend Feature Strategy — JSON-first, text fallback

## 动机

8 个后端对各项功能的支持程度不同。需要一个统一的策略来决定何时使用原生特性、何时回退到 loopflow 层的通用实现。

## 决策

### 原则：JSON-first, text fallback

对所有后端功能，优先使用后端原生的 JSON/结构化模式。仅在原生模式**有实质性缺陷**时回退到 text 模式 + loopflow 层处理。

**"实质性缺陷"的定义**（满足任一条即视为有缺陷）：
1. 信息丢失严重（如 kimi `stream-json` 丢弃所有 thinking 和工具调用过程）
2. 输出格式损坏（如 JSON 行中混入非 JSON 内容）
3. 关键字段缺失（如缺少 session_id、无法判断成功/失败）
4. 后端崩溃或 hang（如某些模式下已知有 bug）

**不是"实质性缺陷"的情况**：
- 输出格式不同但可以解析（如 claude 和 codex 的 JSON 格式不同，但都能提取 text）
- 缺少非关键字段（如 usage 缺失不影响核心功能）
- 需要额外解析工作（如 stream-json 需要逐行解析 JSON）

### 功能矩阵

| 功能 | JSON 模式 | text 回退 | 示例 |
|------|----------|----------|------|
| 输出格式 | `--output-format stream-json` / `--json` | `-p` + 归一化 | kimi: text（JSON 模式信息丢失） |
| Skill | `--skills-dir` / `--skill` | prompt 注入 | kimi: `--skills-dir` ✅ |
| 结构化输出 | `--output-schema` / native tools | prompt 注入 schema | codex: `--output-schema` 待评估 |
| Thinking | `type: "thinking"` 独立字段 | stderr 或丢弃 | claude: `type: "thinking"` ✅ |

### 各后端 JSON 模式评估

| 后端 | JSON 模式 | 评估 | 决策 |
|------|----------|------|------|
| claude | `stream-json --verbose` | ✅ 完整：thinking/text/result 分离 | JSON |
| codex | `--json` | ✅ 完整：agent_message + usage | JSON |
| qwen | `-o stream-json` | 待验证 | 待定 |
| gemini | `-o stream-json` | 待验证 | 待定 |
| **kimi** | `stream-json` | ❌ 仅 2 行，无 thinking、无工具调用 | **text** |
| opencode | 待调研 | 待定 | 待定 |
| kiro | 待调研 | 待定 | 待定 |
| pi | 待调研 | 待定 | 待定 |

## 理由

1. 原生模式通常更可靠（后端自己定义格式，不会因 UI 变化而 break）
2. 原生模式信息更丰富（thinking 分离、usage 统计、结构化元数据）
3. text 回退是安全网，确保所有后端至少能工作
4. 每个后端的决策有明确的判定标准，而非主观判断

## 后果

### 正面

- 每个后端的选择有据可查（ADR 0019-0022 已应用此策略）
- 新后端接入时有明确的评估流程
- 未来后端升级 JSON 模式后，可重新评估并切换

### 负面

- 需要逐个后端调研 JSON 输出格式
- 两种模式共存增加维护复杂度（但 text 回退的代码量很小）

## 约束范围

所有 `src/loopflow/backends/*.py`。新后端接入时必须先评估 JSON 模式，有缺陷时记录在对应 ADR 中。

## 参考

- ADR 0019：kimi — text 模式（JSON 有缺陷）
- ADR 0020：claude — JSON 模式
- ADR 0022：codex — JSON 模式
- ADR 0015/0017：skill 的 JSON-first 策略（原生 `--skills-dir` 优先于 prompt 注入）