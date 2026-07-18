---
title: 01-report-goal-mode
description: Goal mode 实现报告：agent 反馈循环、__goal schema wrapper、blocked audit、15 新测试
type: report
status: complete
created: 2026-07-13T00:00:00Z
---

# 01-report-goal-mode

## 实现概要

实现了 `agent()` 的 goal 反馈循环：当 goal 参数非空时，框架内部循环调用 agent 直到完成或阻塞。

## 实现步骤

| 步骤 | 文件 | 变更 |
|------|------|------|
| Step 1 | `agent.py` | 新增 `GoalBlocked(Exception)` |
| Step 2 | `runtime.py` | `_add_goal_to_schema()` — 框架层 __goal wrapper |
| Step 3 | `runtime.py` | `_build_goal_steering()` — 自动生成 steering prompt |
| Step 4 | `runtime.py` | `_run_subagent()` 新增 `resume_session_id` 参数 |
| Step 5 | `runtime.py` | `_call_agent_once()` — 单次 agent 调用 |
| Step 6 | `runtime.py` | `_run_with_goal()` — goal 循环核心逻辑 |
| Step 7 | `runtime.py` | `agent()` 新增 `goal`/`goal_max_iterations` 参数 |
| Step 8 | `test_runtime.py` | 15 个单元测试 |

## AC 验证

| AC | 状态 |
|----|------|
| AC-001-N-1 单次迭代完成 | [PASS] `test_goal_completes_in_one_iteration` |
| AC-001-N-2 多次迭代完成 | [PASS] `test_goal_completes_after_multiple_iterations` |
| AC-001-N-3 无 goal 行为不变 | [PASS] `test_goal_without_goal_behaves_normally` |
| AC-001-B-1 达到迭代上限 | [PASS] `test_goal_at_max_iterations_with_complete` |
| AC-001-B-2 空 goal | [PASS] `test_goal_empty_string_behaves_as_none` |
| AC-001-B-3 无 schema | [PASS] `test_goal_no_schema_extracts_goal_from_text` |
| AC-001-F-1 迭代上限 | [PASS] `test_goal_max_iterations_exceeded` |
| AC-001-F-2 3 次 blocked | [PASS] `test_goal_three_blocked_raises` |
| AC-002-N-1 不同原因重置 | [PASS] `test_blocked_different_reasons_reset_counter` |
| AC-002-N-2 2 次 blocked 后完成 | [PASS] `test_blocked_twice_then_complete` |
| AC-002-B-1 无 reason | [PASS] `test_blocked_no_reason_defaults_unknown` |
| AC-003-N-1 剥离 __goal | [PASS] `test_goal_result_strips_goal_field` |
| AC-003-N-2 schema 不修改 | [PASS] `test_goal_does_not_mutate_input_schema` |
| AC-005-N-1 向后兼容 | [PASS] `test_goal_does_not_affect_existing_agent_call` |
| AC-001-E-3 错误传播 | [PASS] `test_goal_blocked_agent_error_propagates` |

## 测试统计

- 新增：15 tests
- 总计：195 tests passed
- 现有测试：180 tests unchanged

## Commit

`feat(runtime): goal mode — agent feedback loop with __goal schema wrapper` (1cff6f9)