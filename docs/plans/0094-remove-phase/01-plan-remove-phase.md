---
title: 移除 Phase 抽象
description: 删除 phase() 函数和相关概念，改为 Agent 实例图。ADR-0052 实现。
type: plan
status: done
created: 2026-07-27T00:00:00Z
---

# 0094: 移除 Phase 抽象

## 关联

- ADR: [0052-remove-phase](../../adr/0052-remove-phase.md)
- 分支: `feat/0094-remove-phase`

## 步骤

### 01: 删除 phase() 及相关函数

- [x] 删除 `phase()` 函数（`runtime.py`）
- [x] 删除 `_emit_phase()`（`events.py`）
- [x] 删除 `PhaseGraph`（`graph.py`）
- [x] 删除 `TerminalGraphRenderer`（`graph_renderer.py`）
- [x] 删除 `meta["phases"]` / `declared_phases`
- [x] 删除 `--from-phase` / `--only-phase`

### 02: 创建 AgentGraph

- [x] 新建 `agent_graph.py`：AgentGraph 类，节点=agent 实例
- [x] `parallel()` 产生 fork/join 事件
- [x] `project_events()` 构建 fork/join 边

### 03: 更新 runner

- [x] agent_start 事件包含 `label`、`agent_def`、`backend`
- [x] 移除 phase 字段
- [x] file observe 在 agent 完成后触发

### 04: 更新 file_observation

- [x] `observe()` 参数改为 `(call_id, label)`
- [x] file_changes.jsonl 字段改为 `call_id` + `label`

### 05: 更新 WebUI

- [x] 替换 PhaseGraph 为 AgentGraph（dagre DAG 布局）
- [x] 移除 phase 过滤
- [x] File Changes 按 call_id 过滤
- [x] 移除 phase 事件渲染
- [x] 修复重复 agent_message（`_write_cache` 冗余写入）
- [x] 修复 backend 字段缺失

### 06: 更新 loop workflows

- [x] 所有 loop 移除 `phase()` 调用
- [x] 所有 loop 移除 `meta["phases"]`

### 07: 更新测试

- [x] 删除 phase 特定测试
- [x] 更新 file_observation 测试
- [x] 更新 web_events 测试
- [x] 更新 web_storage 测试

## 验证

- [x] 503 tests passed
- [x] deep-research 完整运行通过
- [x] WebUI Agent Graph 渲染正常
- [x] File Changes 正常工作