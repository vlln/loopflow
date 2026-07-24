---
title: Declared Phases Pre-Display Implementation Report
description: ADR-0040 Declared phases 预显示实现完成报告
type: report
status: done
created: 2026-07-23T17:00:00Z
---

# Summary

ADR-0040 Declared phases 预显示实现完成。Loop frontmatter 的 `meta.phases` 声明阶段在 WebUI 中预显示，运行时图合并声明阶段作为 pending 占位节点。

# Changes

## Python 后端

- `src/loopflow/infrastructure/web_resources.py`：
  - 新增 `_extract_declared_phases(metadata)` 函数，从 frontmatter 提取 `phases` 列表
  - `LoopRepository.summary()` 返回 `declared_phases` 字段
  - `LoopRepository.detail()` 返回 `declared_phases` 字段
  - 无效条目（missing/empty title, non-string title, non-dict）静默跳过
- `src/loopflow/application/execution.py`：
  - `execute_workflow()` 在创建 run_metadata 时从 loop meta 提取 declared_phases 并写入 run.json
  - 仅当 phases 存在且有效时写入
- `src/loopflow/infrastructure/web_storage.py`：
  - `read_detail()` 返回 `declared_phases`（从 run.json 读取，legacy Run 返回 None）

## 前端

- `web/src/types.ts`：
  - `PhaseNode` 新增 `is_declared?` / `is_undeclared?` 可选字段
  - `RunDetail` 新增 `declared_phases?` 字段
  - `LoopSummary` / `LoopDetail` 新增 `declared_phases?` 字段
- `web/src/App.tsx`：
  - `PhaseGraph` 合并 runtime nodes + declared phases（未执行的声明阶段作为 pending 占位节点）
  - runtime 中存在但未在 declared_phases 中的阶段标记为 `is_undeclared`
  - `PhaseNodeView` 显示 declared（pending）和 undeclared 视觉状态
- `web/src/styles.css`：
  - `.phase-node.is-declared` 虚线边框 + 半透明
  - `.phase-node.is-undeclared` 橙色边框

## 测试

- `tests/web_support/factories.py`：`create_loop()` 新增 `phases` 参数
- `tests/integration/test_web_api.py`：5 个 declared phases 测试
  - `test_loop_summary_includes_declared_phases`
  - `test_loop_summary_without_phases_returns_empty_list`
  - `test_loop_summary_skips_invalid_phase_entries`
  - `test_run_detail_includes_declared_phases_from_run_json`
  - `test_run_detail_without_declared_phases_returns_none`

# Verification

- Python: 365 passed, 1 skipped
- Frontend: 15 passed, typecheck clean, 99.48% stmt coverage
- AC-009 declared phases 场景覆盖

# Decisions

- declared_phases 在 Loop summary/detail 中始终返回 list（空 list 表示无声明），在 Run detail 中从 run.json 读取（None 表示 legacy Run 未持久化）。
- 无效 phase 条目静默跳过，不报错——保持 Loop 仍 valid。
- 前端合并策略：runtime nodes 优先，declared phases 中未执行的追加为 pending 占位节点。
