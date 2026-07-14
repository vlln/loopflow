---
title: Plan 01 — AgentRunner 重构实施
description: 将 Agent 类重构为 AgentRunner + 模块级函数，消除 backend 双重创建和两条执行路径重复
type: plan
status: done
created: 2026-07-14T00:00:00Z
---

# Plan 01: AgentRunner 重构实施

## 目标

按 ADR 0029 实施重构，消除四个问题：Agent 贫血、Backend 双重创建、执行路径重复、能力查询浪费。

## 步骤

### 步骤 1: 提取模块级函数到 agent.py

- 删除 `Agent` 类
- 将 `marshal()`, `build_goal_steering()`, `add_goal_to_schema()` 改为模块级函数
- 保留 `AgentDef`, `parse_agent`, `GoalBlocked`, `AgentError` 等不变

### 步骤 2: 创建 runner.py — AgentRunner 类

- 新建 `src/loopflow/runner.py`
- `AgentRunner.__init__(self, definition, backend, context)`
- `AgentRunner.run(prompt, goal=None, **params) → Any`
- `AgentRunner._execute_once(prompt, session, schema, ...)` — 统一执行路径
- `AgentRunner._run_goal_loop(resolved, schema, goal, ...)` — goal 循环

### 步骤 3: 更新 runtime.py — agent() 薄 facade

- `agent()` 函数简化为 ~20 行：加载 AgentDef → 创建 Backend → AgentRunner.run()
- 移除 `_call_agent_once()` 和重复的执行逻辑
- 保留 `parallel()`, `pipeline()`, `workflow()`, 上下文管理

### 步骤 4: 更新测试

- 更新 `test_agent.py`：`Agent` 类 → `AgentRunner` + 模块级函数
- 更新 `test_runtime.py`：移除对 `Agent` 类的引用
- 195 tests 全部通过

### 步骤 5: E2E 验证

- kimi: goal mode 正常工作
- claude: native goal 正常工作

## Constraints

- `agent()` 函数签名不变，所有现有 workflow 无需修改
- `AgentDef` 不变
- 所有 Backend 不变
- 195 tests 必须全部通过

## Checkpoint

- [ ] ADR 0029 accepted
- [ ] 195/195 tests pass
- [ ] E2E kimi goal mode pass
- [ ] E2E claude native goal pass
- [ ] `Agent` 类已删除，代码中无残留引用