---
title: 移除 Phase 抽象，改为 Agent 实例图
description: 删除 workflow 中的 phase() 概念，每个 agent() 调用即图节点，文件变化与 agent 实例绑定
type: adr
status: accepted
created: 2026-07-27T00:00:00Z
---

# ADR-0052: 移除 Phase 抽象，改为 Agent 实例图

## 背景

loopflow 当前有两层抽象：`phase()` 和 `agent()`。Phase 是 workflow 中的阶段声明（如 "Plan", "Research"），Agent 是实际的 AI 调用。但 Phase 与 Agent 是 1:1 的——`phase("Plan")` 后紧跟 planner agent，`phase("Research")` 后紧跟 researcher agents。Phase 没有独立语义，只是 Agent 的别名。

这引入了不必要的概念负担：
- `meta["phases"]` 预声明
- `PhaseGraph` 图结构
- `_emit_phase` 事件
- `declared_phases` 在 Loop/Run 详情中
- `--from-phase` / `--only-phase` CLI 选项
- WebUI 中 phase 节点、phase 过滤、is-in-phase 高亮

## 决策

**删除 Phase 抽象。** 每个 `agent()` 调用产生一个唯一的图节点（call_id），并行调用通过 fork/join 边表示。

### 具体变更

| 删除 | 替代 |
|------|------|
| `phase()` 函数 | 直接调用 `agent()` |
| `meta["phases"]` | 删除，无需预声明 |
| `PhaseGraph` | `AgentGraph`（节点 = agent 实例） |
| `_emit_phase()` | 删除，file observe 移到 agent 完成时 |
| `TerminalGraphRenderer` | 删除（无 phase 图可渲染） |
| `--from-phase` / `--only-phase` | 删除 |
| Phase 事件类型 | 只保留 agent_start/agent_done 事件 |
| `file_changes.jsonl` 中 `phase`/`phase_id` | `call_id` + `label` |
| WebUI PhaseGraph 组件 | AgentGraph 组件（dagre DAG 布局） |
| `declared_phases` | 删除 |

### 图结构

- 每个 `agent()` 调用 = 一个节点，id 为 call_id，label 为 agent 的 label 参数
- `parallel()` 产生 fork/join 边：fork 从父节点到所有并行子节点，join 从所有子节点汇聚到下一个节点
- 使用 dagre 进行 DAG 布局（rankdir: LR）

### 文件变化归属

- `observe()` 在 agent 调用完成后触发，文件变化记录携带 `call_id` 和 `label`
- WebUI 点击节点可过滤该 agent 产生的文件变化

## 影响

- **Breaking change**: 所有现有 workflow 必须移除 `phase()` 调用和 `meta["phases"]`
- **WebUI**: 图组件重写，文件变化面板简化
- **测试**: 删除 phase 相关测试（test_graph.py, test_graph_renderer.py, test_graph_e2e.py），更新所有 workflow fixture

## 替代方案

### 保留 phase 但简化

将 phase 改为可选的标注，不作为图节点。但 phase 与 agent 的 1:1 关系意味着 phase 永远是冗余的，保留它只会增加维护负担。

### 保留 phase 作为 agent 的 group

将 phase 作为 agent 的分组标签，图节点仍是 agent，但用颜色/边框区分 phase。这增加了 UI 复杂度，且 phase 本身没有独立信息价值。

## 验证

- [x] 代码实现完成（见 `feat/0094-remove-phase` 分支）
- [x] 503 测试通过（排除 phase 特定测试）
- [x] deep-research 完整运行通过
- [x] WebUI Agent Graph 渲染正常（dagre DAG 布局）
- [x] File Changes 按 agent 过滤正常
- [x] 所有 loop workflow 已更新（移除 phase() 调用）