---
title: AC-015 AgentGraph 覆盖报告
description: 0112-04 执行结果：21 个 planned 场景补齐，含 3 处产品修复
type: report
status: complete
created: 2026-07-30T00:00:00Z
---

# Summary

AC-015（AgentGraph 与 Agent Call 运行过程）21 个 planned 场景全部补齐为真实测试节点。strict 检查 AC-015 段 0 planned（仅剩 AC-019 14 个 planned，属 0112-05）。本单元含 3 处产品行为修复（E-2 malformed reason、E-3 label fallback、B-3/N-6 declared_phases 清理），全部为 AC oracle 明确要求但实现缺失的行为，先跑红确认缺口再修复。

# Acceptance Results

后端集成（tests/integration/test_web_api.py）：
| AC | 测试节点 | 结果 |
|----|----------|------|
| AC-015-N-1 | `test_ac015_n1_sequential_graph_structure` | [PASS] |
| AC-015-N-3 | `test_ac015_n3_fork_join_graph` | [PASS] |
| AC-015-N-4 | `test_ac015_n4_back_to_back_fork_join` | [PASS] |
| AC-015-N-6 | `test_ac015_n6_empty_agent_graph_no_declared_phases` | [PASS] |
| AC-015-N-7 | `test_ac015_n7_live_agent_start_marks_running_current` | [PASS] |
| AC-015-N-8 | `test_ac015_n8_same_label_distinct_nodes_not_merged` | [PASS] |
| AC-015-B-1 | `test_ac015_b1_run_without_agent_events_empty_graph` | [PASS] |
| AC-015-B-2 | `test_ac015_b2_hundred_sequential_calls_ordered` | [PASS] |
| AC-015-B-3 | `test_ac015_b3_no_declared_phases_in_loop_or_run` | [PASS] |
| AC-015-B-4 | `test_ac015_b4_single_done_node_no_edges` | [PASS] |
| AC-015-E-2 | `test_ac015_e2_missing_call_id_goes_to_malformed` | [PASS] |
| AC-015-E-3 | `test_ac015_e3_empty_label_falls_back_to_call_id` | [PASS] |
| AC-015-F-1 | `test_ac015_f1_missing_events_jsonl_returns_empty` | [PASS] |
| AC-015-F-3 | `test_workflow_syntax_error_run_start_fails_without_placeholders`（复用已有） | [PASS] |

前端（web/src/App.test.tsx）：
| AC | 测试节点 | 结果 |
|----|----------|------|
| AC-015-N-2 | `AC-015-N-2: selecting a graph node filters Events and file changes` | [PASS] |
| AC-015-N-5 | `AC-015-N-5: Inspector shows run state...` | [PASS] |
| AC-015-N-9 | `AC-015-N-9: call-list shows call_id as primary...`（复用已有） | [PASS] |
| AC-015-B-5 | `AC-015-B-5: call without session_id...`（复用已有） | [PASS] |
| AC-015-E-1 | `AC-015-F-4: legacy events...unattributed`（复用，unattributed 语义） | [PASS] |
| AC-015-E-4 | `AC-015-E-4: graph node count...without occurrence terms` | [PASS] |
| AC-015-F-4 | `AC-015-F-4: legacy events...unattributed`（复用已有） | [PASS] |

实现提交 `ba8e473`。

# 产品修复（3 处，先红后绿）

1. **E-2 malformed reason**：投影把缺 call_id 的 v2 事件塞进 malformed 但无 `reason` 字段，detail 的 `events` 也未排除坏事件 raw。修复 `web_events.py` 投影包装为 `{reason: "missing_call_id"|"invalid_event", raw: event}`，`web_storage.py` 的 detail `events` 排除 malformed raw。
2. **E-3 label fallback**：`payload.get("label", call_id)` 把空字符串当有效 label。改为 `payload.get("label") or call_id`，空/缺失 label 回退 call_id。
3. **B-3/N-6 declared_phases 清理**：loop summary/detail 主动暴露 `declared_phases`，违反 ADR-0052（Phase 抽象已删除）。从 `web_resources.py` 的 summary/detail 移除。

# Verification

| 门禁 | 结果 |
|------|------|
| strict manifest（AC-015 段） | 0 planned；AC-019 14 planned 不变 |
| infrastructure 回归 | 82 passed, 1 skipped |
| 全量 Python（非 system） | 686 passed, 1 skipped |
| Frontend | 61 passed |

# Acceptance Reasonableness

- N-8 断言同 label 两节点独立存在且 edges 无 occurrence 概念（字符串级断言图无 occurrence）。
- E-2 断言 malformed/malformed_count 精确等于 1、reason=missing_call_id、坏事件 raw 不在合法 events/calls/graph 中、合法 call-1 仍入图。
- E-4 断言节点计数文本与 occurrence 术语缺失。
- B-2 断言 100 节点顺序稳定、首尾标识正确、每个 call 事件只带自己 call_id。
- 3 处产品修复均先写测试跑红确认缺口，修复后转绿，全量 686+61 无回归。
