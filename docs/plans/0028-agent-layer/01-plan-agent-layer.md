---
title: 01-plan-agent-layer
description: 实现 Agent 类，将能力 marshalling 从 runtime.py 抽取到 agent.py，Agent = Backend + Capabilities
type: plan
status: pending
created: 2026-07-13T00:00:00Z
---

# 01-plan-agent-layer

## 实现步骤

### Step 1: Agent 类骨架

- 文件：`src/loopflow/agent.py`
- 新增 `Agent` 类：`__init__(ad)`、`call(prompt, backend, goal, **params)`
- 将 `_run_with_goal`、`_add_goal_to_schema`、`_build_goal_steering` 从 `runtime.py` 移到 `agent.py`
- 将 `_call_agent_once`、`_extract_session_id` 移到 `agent.py`

### Step 2: 能力 marshalling

- `Agent._marshal_body()`: 渲染 body + 模板参数
- `Agent._marshal_skills()`: backend 支持原生 skill → 保留；否则 → 文本注入
- `Agent._marshal_schema()`: backend 支持 structured output → 保留；否则 → schema hint 文本
- `Agent._marshal_goal()`: backend 支持 native goal → `/goal` 前缀；否则 → loopflow goal 循环
- `Agent._marshal_model()`: 选 model 参数

### Step 3: runtime.py 简化

- `agent()` 函数简化为：加载 `AgentDef` → 创建 `Agent` → 调用 `Agent.call()`
- 移除已迁移的辅助函数
- 保留 session 管理、缓存、context 相关逻辑

### Step 4: 测试更新

- `test_agent.py`: 新增 `TestAgent` 类，测试 marshalling 逻辑
- `test_runtime.py`: 更新 goal mode 测试适配新结构

## Constraints

- 不修改 `agent()` 函数签名（workflow API 不变）
- 不修改 backend 接口
- 现有 195 tests 全部通过

## Checkpoint

- [ ] Agent 类创建并调用
- [ ] 能力 marshalling 尽力而为
- [ ] goal mode 功能不变
- [ ] 195 tests pass