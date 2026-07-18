---
title: ADR 0028 — Agent 层抽象
description: 将 agent 的 prompt 组装逻辑从 runtime.py 抽取到 Agent 类，Agent = Backend + Capabilities，能力 marshalling 遵循"尽力而为"原则
type: adr
status: accepted
created: 2026-07-13T00:00:00Z
---

# ADR 0028: Agent 层抽象

## Context

当前 `runtime.py` 的 `agent()` 函数直接处理 5 种能力（agent 定义、skills、schema、goal、model），每种能力通过字符串拼接注入 prompt。这导致：

1. `agent()` 函数过长（~200 行），新能力只能继续往里塞
2. 能力 marshalling 逻辑分散在 `runtime.py` 各处（`_run_with_goal`、`_add_goal_to_schema`、`_build_goal_steering`、`build_skill_prompt` 等）
3. "尽力而为"原则（backend 原生支持 → 优先使用；否则 → 框架降级）缺乏统一入口

## Decision

引入 `Agent` 类，封装 "Backend + Capabilities" 的语义：

```
Agent = Backend + Capabilities
         │          │
         │          ├── Skills (声明式能力)
         │          ├── Schema (输出契约)
         │          ├── Goal (完成条件)
         │          ├── System Prompt (背景知识)
         │          └── Model (模型选择)
         │
         └── Backend (provider 适配)
```

### 核心设计

**1. Agent 类是 Agent Runtime 层的入口**

```python
class Agent:
    """Agent = Backend + Capabilities."""
    
    def __init__(self, ad: AgentDef):
        self.ad = ad
    
    def call(self, prompt: str, backend, goal=None, **params) -> dict | str:
        """Marshall capabilities → backend call."""
```

**2. 能力 marshalling 遵循"尽力而为"**

每种能力检查 backend 是否原生支持，优先使用最优路径：

| 能力 | Backend 原生支持 | 降级路径 |
|------|-----------------|---------|
| skills | skill 参数传 backend | 文本注入到 system prompt |
| schema | structured output 传 backend | schema hint 文本注入 |
| goal | `/goal` 前缀交给 backend | loopflow goal 循环 |
| model | `--model` 参数 | 忽略 |
| body | system prompt 参数 | 文本注入 |

**3. 不引入新的抽象框架**

使用简单的 `if/else` 检查，不引入 Pipeline/Transform/Plugin 模式。当前规模（8 backend × 5 capability）不需要插件架构。

**4. Agent 类放在 `agent.py`**

与 `AgentDef`、`parse_agent` 在同一模块，保持 agent 相关代码的凝聚性。

### 影响范围

| 文件 | 变更 |
|------|------|
| `agent.py` | 新增 `Agent` 类（~100 行），包含 `call()` 和 marshalling 逻辑 |
| `runtime.py` | `agent()` 简化为 `Agent(ad).call(prompt)` 的薄封装（~20 行删减）；移除 `_run_with_goal`、`_add_goal_to_schema`、`_build_goal_steering` 到 `agent.py` |
| `tests/unit/test_agent.py` | 新增 Agent 类的单元测试 |
| `tests/unit/test_runtime.py` | 更新现有 goal mode 测试适配新结构 |

## Consequences

### 正面

- `runtime.py` 的 `agent()` 函数从 ~200 行缩减到 ~50 行
- 新能力只需在 `Agent` 类中添加一个方法，不修改 `runtime.py`
- "尽力而为"策略集中在一处，易于理解和维护
- `Agent` 类可独立测试（不依赖 RunContext）

### 负面

- 新增一个类的学习成本（但语义清晰：Agent = Backend + Capabilities）
- `Agent.call()` 需要接收 `backend` 参数（当前隐式通过 `_make_backend` 创建）

### 风险

- 重构可能导致现有 behavior 变化 → 通过全量测试覆盖缓解
- Agent 类与 RunContext 的交互（session 管理、缓存）需要明确边界

## 验证

| 项目 | 验证方式 |
|------|---------|
| 功能等价 | 现有 195 tests 全部通过 |
| 新测试 | `TestAgent` 类覆盖 marshalling 逻辑 |
| E2E | goal mode 多后端测试通过 |