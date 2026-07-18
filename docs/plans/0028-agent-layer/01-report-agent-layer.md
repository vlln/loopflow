---
title: 01-report-agent-layer
description: Agent 层重构报告：Agent 类封装能力 marshalling，runtime.py 简化，195/195 pass
type: report
status: complete
created: 2026-07-13T00:00:00Z
---

# 01-report-agent-layer

## 实现概要

引入 `Agent` 类：`Agent = Backend + Capabilities`。能力 marshalling（skills/schema/goal/model）从 `runtime.py` 迁移到 `agent.py`。

## 变更

| 文件 | 新增 | 删除 | 净变化 |
|------|------|------|--------|
| `agent.py` | +251 | -1 | +250 |
| `runtime.py` | +46 | -294 | -248 |
| `test_runtime.py` | +1 | -1 | 0 |
| **总计** | +298 | -295 | **+3** |

## Agent 类 API

```python
class Agent:
    def __init__(self, ad: AgentDef | None = None)
    def marshal(self, prompt, goal=None, backend_name=None, **params) -> tuple[str, dict | None, bool]
    def build_goal_steering(self, goal, iteration, max_iterations) -> str
    def add_goal_to_schema(self, schema) -> dict
    def run_goal_loop(self, prompt, schema, goal, max_iterations, call_fn, emit_log=None) -> Any
```

## AC 验证

| AC | 状态 |
|----|------|
| AC-001-N-1 Agent 创建并调用 | [PASS] |
| AC-001-N-2 无 agent_def | [PASS] |
| AC-002-N-1 Goal 原生支持 | [PASS] |
| AC-002-N-2 Goal 降级 | [PASS] |
| AC-003-N-1 行为等价 | [PASS] |
| AC-004-N-1 全量测试 | [PASS] 195/195 |
| AC-004-N-2 Goal mode 不变 | [PASS] |

## Commit

`refactor(agent): Agent class — capability marshalling from runtime.py to agent.py` (61c567b)