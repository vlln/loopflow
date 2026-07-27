---
title: 0.24.0 Phase 残留收尾
description: 清理 ADR-0052 未完成的 phase 残留、修复 agent_graph fan-in、实现节点详情面板
type: plan
status: pending
created: 2026-07-27T05:00:00Z
---

# Plan: 0.24.0 Phase 残留收尾

关联：ADR-0052 (accepted) · BL-022 / BL-023 / BL-024 / BL-025

## 范围

0.24.0 声称移除 Phase 抽象，但实际残留：`phase()` 函数未删、14 个测试红灯、graph 投影 fan-in 损坏、节点详情面板缺失。本轮为完成度修补，不涉及新架构决策。

## 子任务

### BL-022: Phase 残留清理

**1. runtime.py 清理**

删除以下符号：
- `def phase(title)` (line ~241)
- `from loopflow.presentation.events import _emit_phase` (import line 27，保留 `_emit_log`)
- `from_phase` / `only_phase` context 逻辑 (lines ~72-78)
- 模块 docstring 中 `phase` 公开 API 声明
- `meta["phases"]` 相关代码（如有残留）

**2. events.py 清理**

- 删除 `_emit_phase()` 函数（如仍存在）
- 删除 phase 事件类型定义（如仍存在）

**3. test_graph_e2e.py 重写（8 个测试）**

当前：全部基于 `phase()` 构建 workflow，断言 `phase` 事件类型和 `phase_count`。
重写为：基于 `agent()` 构建，断言 `agent_start`/`agent_done` 事件和 agent_graph 结构。覆盖：
- 线性图（A→B→C）
- 并行图（fork/join）
- events.jsonl 内容校验

**4. test_web_execution.py 重写（6 个测试）**

当前：workflow 使用 `phase('Work')`，断言 `phase_id`。
重写为：移除 `phase()` 调用，断言 `call_id` 和 `label`。

### BL-023: agent_graph fan-in 投影修复

**问题**：`project_events()` (web_events.py) 处理 back-to-back parallel 时 3 个 bug：
1. 第一组 join 边永远不生成（`fork_start` 不清 `pending_join`，第二个 `fork_start` 设 `fork_parent` 非空后 join 分支不可达）
2. `pending_join` 跨组合并（`fork_end` 用 `extend`，不清空）
3. 第二组 fork source 错误（解析为第一组最后一个 child）

**修复方案**：
- `fork_start` 时：如果 `pending_join` 非空，先生成 join 边到当前 agent，再清空 `pending_join`
- 或：在 `fork_end` 时检查是否有后续 agent，如果没有则 join 边留到 run 结束时丢弃

**CSS**：`App.tsx` 中 `join` edge 添加 `join-edge` class，与 `fork-edge` / `sequential` 区分。

**测试**：`test_web_events.py` 添加 fork/join 投影单元测试。

### BL-024: 节点详情面板

点击 agent 节点时，展示合并详情面板：events timeline + file changes + call info（backend/model/exit code）。

### BL-025: Playwright fixture 清理

`web/tests/webui.spec.ts` mock fixture 中 `phase_id` 字段移除，更新为 `call_id` + `label` 格式。

## 验证

- [ ] `pytest tests/` 全绿（0 failures）
- [ ] `npm run test:browser` 通过
- [ ] deep-research 端到端运行，WebUI 图正确显示 fan-in/fan-out
- [ ] 节点点击弹出详情面板
