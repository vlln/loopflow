---
title: 01-plan-goal-mode
description: 实现 agent goal 反馈循环：runtime.agent() 的 goal 参数、__goal schema wrapper、blocked audit、steering prompt 注入
type: plan
status: done
created: 2026-07-13T00:00:00Z
---

# 01-plan-goal-mode

## 实现步骤

### Step 1: GoalBlocked 异常类

- 文件：`src/loopflow/agent.py`
- 新增 `GoalBlocked(Exception)` 异常类

### Step 2: _add_goal_to_schema() 辅助函数

- 文件：`src/loopflow/runtime.py`
- 将业务 schema 包装为含 `__goal` 的 merged schema
- 防御性拷贝，不修改传入的 schema
- 业务 schema 已有 `__goal` 时 log warning

### Step 3: _build_goal_steering() 辅助函数

- 文件：`src/loopflow/runtime.py`
- 首次迭代：生成含 goal 目标 + Completion Audit + Blocked Audit 规则的 steering prompt
- 后续迭代：生成含迭代计数的轻量 steering prompt

### Step 4: _resume_subagent() 辅助函数

- 文件：`src/loopflow/runtime.py`
- 复用 `_run_subagent` 的 backend 创建逻辑，但调用 `resume_session` 而非 `create_session`

### Step 5: _run_with_goal() 核心循环

- 文件：`src/loopflow/runtime.py`
- 实现 goal 循环：create_session → resume_session × N → complete/blocked
- blocked audit 计数器逻辑
- 达到 goal_max_iterations 抛 GoalBlocked

### Step 6: agent() 函数修改

- 文件：`src/loopflow/runtime.py`
- 新增 `goal` 和 `goal_max_iterations` 参数
- 当 goal 非空时调用 `_run_with_goal()`
- 当 goal 为空时行为不变（向后兼容）

### Step 7: 单元测试

- 文件：`tests/unit/test_runtime.py`
- 覆盖 AC-001 到 AC-005 所有场景
- Mock backend 返回预定义的 active/complete/blocked 序列

## Constraints

- 不修改 agent 定义文件格式
- 不修改 workflow API
- 不修改 backend 接口
- 现有 180 tests 必须全部通过

## Checkpoint

- [ ] 所有 AC 场景通过
- [ ] 180 existing tests pass
- [ ] Goal 模式返回的 result 不含 __goal
- [ ] 不传 goal 时行为不变