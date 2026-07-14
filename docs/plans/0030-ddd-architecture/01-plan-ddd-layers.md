---
title: Plan 01 — DDD 四层架构重构
description: 按 ADR 0030 将 loopflow 重构为 domain/infrastructure/application/presentation 四层
type: plan
status: pending
created: 2026-07-14T00:00:00Z
---

# Plan 01: DDD 四层架构重构

## 目标

按 ADR 0030 实施分层重构，严格依赖方向：领域层不依赖任何其他层。

## 步骤

### 步骤 1: 创建目录结构 + Capabilities 值对象

- 创建 `domain/`, `infrastructure/`, `application/`, `presentation/` 目录
- 创建 `domain/capabilities.py` — `Capabilities` 值对象
- 在 `BaseBackend` 上添加 `capabilities` property
- 各具体 backend 覆写 `capabilities`

### 步骤 2: 移动领域层

- `agent.py` → `domain/agent_def.py`（AgentDef, GoalBlocked, AgentError）
- `agent.py` → `domain/marshalling.py`（marshal, build_goal_steering, add_goal_to_schema, extract_json, validate_json）
- `agent.py` → `domain/goal_loop.py`（run_goal_loop）

### 步骤 3: 移动基础设施层

- `backends/` → `infrastructure/backends/`
- `transports/` → `infrastructure/transports/`
- 新建 `infrastructure/backends/manager.py`（BackendManager）
- `agent.py` parse_agent/list_agents → `infrastructure/repository.py`
- `runtime.py` RunContext/State → `infrastructure/context.py`
- `runtime.py` 缓存/状态持久化 → `infrastructure/context.py`
- `runtime.py` _create_worktree → `infrastructure/worktree.py`

### 步骤 4: 移动应用层

- `runner.py` → `application/runner.py`
- `runtime.py` agent/parallel/pipeline/workflow → `application/orchestrator.py`
- `_run_subagent`, mock → `infrastructure/backends/manager.py`

### 步骤 5: 移动展示层

- `cli.py` → `presentation/cli.py`
- `display/` → `presentation/display/`
- `graph.py` → `presentation/graph.py`
- `runtime.py` _emit_log/_emit_phase/_write_event → `presentation/`

### 步骤 6: 创建兼容性重导出

- 顶层 `agent.py` → 重导出 domain 模块
- 顶层 `runtime.py` → 重导出 application + presentation
- 所有 `__init__.py` 设置

### 步骤 7: 更新测试 + 验证

- 更新 import 路径
- 195 tests 全部通过
- E2E 验证

## Constraints

- 所有现有 import 路径保持兼容
- `from loopflow.runtime import agent` 仍然可用
- `from loopflow.agent import AgentDef, parse_agent` 仍然可用
- 领域层不 import 任何其他三层

## Checkpoint

- [ ] ADR 0030 accepted
- [ ] 195/195 tests pass
- [ ] `import loopflow.domain` 不触发基础设施 import
- [ ] E2E kimi + claude goal mode pass
- [ ] 顶层 import 兼容性保持