---
title: Agent Output Schema and Infra Failure Handling
description: Agent 定义扩展 output 字段（结构化输出契约），infra 失败抛 AgentError 而非返回 None，让 resume 机制成为错误恢复通道
type: adr
status: accepted
created: 2026-07-08T16:00:00Z
---

# ADR 0011: Agent Output Schema and Infra Failure Handling

## Context

以 bio-reproducer 压力测试为背景，发现两个设计缺口：

1. **Agent 输出无约束**：当前 `agent()` 支持 `schema` 参数获取结构化输出，但 schema 定义位置不明确——放在 workflow.py 中会污染业务逻辑，放在 agent 定义外会丢失契约的内聚性。bio-reproducer 的 validate phase 需要结构化返回值（verdict、score、checks），workflow 依赖 `"FAILED" not in str(report)` 做字符串匹配，脆弱且不可靠。

2. **Infra 失败静默吞没**：当前 `agent()` 在网络断开、后端崩溃、超时等 infra 失败时返回 `None`，workflow 继续执行导致级联失败。loopflow 的 resume 机制本身就是错误恢复通道——crash → resume → 已完成调用缓存命中，失败调用重试。返回 None 剥夺了 resume 的介入机会。

## Decision

### 1. Agent 定义增加 `output` 字段

Agent 定义 frontmatter 新增可选 `output` 字段，值为 JSON Schema。与 `requires.params`（输入契约）对称，`output` 是输出契约。

```yaml
---
name: validate
description: Phase 6 — 验证复现结果
requires:
  params:
    - figure_mode
    - language
    - output_dir
output:
  type: object
  properties:
    verdict:
      type: string
      enum: [REPRODUCED, PARTIAL, FAILED, BLOCKED]
    total_score:
      type: number
  required: [verdict, total_score]
---
```

行为规则：
- `output` 存在时，`agent()` 自动将其作为 `schema` 使用，返回 `dict` 而非 `str`
- Workflow 显式传入 `schema=` 时，覆盖 `output`（显式优先）
- `output` 不存在时，行为不变——返回 `str`

### 1.1 Schema 如何传给 Agent

当前实现 `json.loads(text)` 是事后 parse，agent 不知道 schema 的存在。需要将 schema 事前注入 agent 上下文中。

**方案：Prompt 注入**

在构造 agent prompt 时，将 schema 追加到 prompt 末尾：

```
{prompt}

---
Output format — you MUST respond with a single JSON object matching this schema:
{json.dumps(schema, indent=2)}
Do NOT wrap the JSON in markdown code blocks. Return ONLY the JSON object.
```

### 1.2 Schema 不匹配时的重试

JSON parse 失败不是 infra 故障，而是格式合规失败。不应立即 crash，也不应静默返回 None。

```
agent() 调用
  ↓
Agent 返回 → json.loads() 失败
  ↓
重试（最多 max_retries 次，默认 3）
  → 发送原 prompt + schema + "上次格式不对，请严格按 schema 输出纯 JSON"
  ↓
成功 → 返回 dict
失败 → 超过 max_retries → 抛 AgentError → crash → resume
```

`max_retries` 作为 `agent()` 的参数，默认值 3。workflow 可在调用时覆盖。

| 维度 | 评估 |
|------|------|
| 可靠性 | 低于 function calling，但重试机制弥补 |
| 复杂度 | 低——prompt 注入 + 循环重试 |
| 未来 | 后端支持 function calling 时，升级为 tool 约束 |

### 2. Infra 失败抛 AgentError

`agent()` 在以下情况抛出 `AgentError`（而非返回 `None`）：
- 后端进程非零退出（exit_code ≠ 0）
- 网络超时
- 后端不可用

```python
class AgentError(Exception):
    """Agent call failed at the infrastructure level."""
```

业务失败（agent 正常执行完毕但任务未完成）不在 loopflow 层感知——agent 返回什么就是什么，workflow 自己判断。

### 3. 与 resume 的协作

```
agent() 失败 → AgentError 抛出一 → workflow 崩溃
    ↓
loop resume   → workflow.py 重头执行
    ↓
try_resume()  → 已完成调用缓存命中，跳过
    ↓
失败调用      → 缓存不存在（或 exit_code != 0），重新执行
```

## Consequences

### 正面

- Agent 契约完整：`requires.params`（输入）+ `output`（输出）= 黑盒契约
- Workflow 代码更清晰：`report["verdict"]` 替代 `"FAILED" not in str(report)`
- Infra 失败不再静默——resume 机制自然承接
- 向后兼容：`output` 可选，无 output 的 agent 行为不变

### 代价

- 现有 workflow 中 `if result is None` 的检查需要改为 `try/except AgentError`
- 需要在 `parse_agent()` 中引入 YAML 解析（`yaml.safe_load`）以支持嵌套 `output` schema
- Prompt 注入方式不如 function calling 可靠——JSON parse 失败时返回 None（降级为业务失败，不抛异常）
- 未来升级到 function calling 时，prompt 注入逻辑需移除