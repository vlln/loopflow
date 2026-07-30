---
title: AC-014 Runs 工作台覆盖报告
description: 0112-03 执行结果：14 个 planned 场景补齐，含 1 处产品修复 + reconcile 契约对齐
type: report
status: complete
created: 2026-07-30T00:00:00Z
---

# Summary

AC-014 的 14 个 planned 场景全部补齐为真实测试节点。strict 检查 AC-014 段 0 planned（其余 AC-015/AC-019 共 35 个 planned 属后续单元）。本单元含一处产品行为修复（B-6 working_directory）和一次契约对齐（B-7 reconcile，经人类裁决对齐 ADR-0046）。

# Acceptance Results

| AC | 测试节点 | 结果与提交 |
|----|----------|------------|
| AC-014-N-1 | `test_ac014_n1_runs_list_all_statuses_default_latest` | [PASS] `be64c77` |
| AC-014-N-2 | `test_ac014_n2_failed_filter_in_place_switch` | [PASS] `be64c77` |
| AC-014-N-4 | `test_ac014_n4_start_run_returns_201_location_and_running` | [PASS] `be64c77` |
| AC-014-N-7 | `test_ac014_n7_rerun_creates_new_run_preserves_source` | [PASS] `be64c77` |
| AC-014-N-8 | `test_ac014_n8_loop_filter_and_text_search` | [PASS] `be64c77` |
| AC-014-N-10 | `App.test.tsx::AC-014-N-10: declared args prefill...`（复用已有） | [PASS] `be64c77` |
| AC-014-N-11 | `test_ac014_n11_system_meta_returns_running_version` | [PASS] `be64c77` |
| AC-014-B-2 | `test_ac014_b2_empty_runs_shows_empty_state` | [PASS] `be64c77` |
| AC-014-B-5 | `App.test.tsx::AC-014-B-5: ...blank editor`（复用已有） | [PASS] `be64c77` |
| AC-014-B-6 | `test_ac014_b6_working_directory_basename_in_summary` | [PASS] `be64c77` |
| AC-014-B-7 | `test_ac014_b7_reconcile_stale_since_cleans_failed` | [PASS] `be64c77` |
| AC-014-E-1 | `test_ac014_e1_unreadable_run_returned_as_summary` | [PASS] `be64c77` |
| AC-014-E-2 | `test_ac014_e2_stale_detection_records_stale_since_once` | [PASS] `be64c77` |
| AC-014-F-2 | `test_ac014_f2_reconcile_expired_stale_atomic_failed` | [PASS] `be64c77` |

# 契约对齐（人类裁决）

**AC-014-B-7 / AC-029-B-1 与 ADR-0046 矛盾**：两份 AC 要求宽限内 reconcile 返回 409 `run_in_grace`，但 ADR-0046（2026-07-27 修订，accepted）已移除宽限期阻塞，实现也按此执行（200 直接清理）。人类裁决：**reconcile 宽限阻塞是无意义设计——进程死亡即可清理，后端 session 仍可 resume**。

据此修订（commit `843b622`）：AC-014-B-7、AC-029-B-1 oracle 改为「进程确认死亡即清理为 failed」；Spec v19→v20 的 BR-032/BR-052/US-032/术语表、Interface 0001 reconcile 错误描述同步对齐。`run_in_grace` 保留于错误映射表仅为向后兼容。

**基建缺陷（commit `056c6e4`）**：recovery manifest 的 `check_manifest` 缺节点存在性检查（web manifest 有），导致 AC-029-B-1、AC-020-F-3 引用已改名测试函数未被 strict 拦截。已补 `_test_node_exists` 校验，修正两处漂移映射，并自证（临时改坏节点名→ERROR，还原→98 scenarios ok）。

# Verification

| 门禁 | 结果 |
|------|------|
| strict manifest（AC-014 段） | 0 planned；其余段 35 planned 不变 |
| infrastructure 回归 | 82 passed, 1 skipped |
| 全量 Python（非 system） | 672 passed, 1 skipped |
| Frontend | 58 passed |
| recovery manifest | 98 scenarios ok（含新存在性检查） |

# 产品修复

`src/loopflow/infrastructure/web_storage.py::_working_directory`：原实现只读 runs index，不读 run.json 持久化的 `working_directory`，导致 AC-014-B-6 左栏无法显示真实 basename。修复为优先持久化值、回落 index、再回落目录名，与 `resolve_working_directory` 优先级一致。全量 672 测试无回归。

# Acceptance Reasonableness

- N-7 断言 rerun 后新 run.json args 与源一致且源 run.json 字节不变。
- F-2 断言 reconcile 后 run.json 原子替换且 pid/process_started_at/stale_since 三字段均清除。
- E-2 断言首次读取写入 stale_since、二次读取不改写（值相等）。
- E-1 断言非法 run.json 返回 unreadable 摘要含 parse_error 且合法 Run 正常、请求不 500。
- B-6 修复前后跑红/跑绿确认（修复前 summary 返回目录名 `runs`，修复后返回持久化路径）。
