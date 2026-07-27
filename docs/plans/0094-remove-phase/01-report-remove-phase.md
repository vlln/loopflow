---
title: 移除 Phase 抽象 - 执行报告
description: ADR-0052 实现完成报告
type: report
status: complete
created: 2026-07-27T00:00:00Z
---

# 0094: 移除 Phase 抽象 - 执行报告

## 结果

所有步骤完成。503 tests passed（排除 2 个 phase 特定测试文件）。

## 变更文件

| 文件 | 变更 |
|------|------|
| `src/loopflow/runtime.py` | 删除 `phase()`，移除 `_emit_phase` 导入，移除 from_phase/only_phase |
| `src/loopflow/presentation/events.py` | 删除 `_emit_phase()`，精简为 `_emit_log` + `_write_event` 重导出 |
| `src/loopflow/presentation/graph.py` | **删除** |
| `src/loopflow/presentation/display/graph_renderer.py` | **删除** |
| `src/loopflow/presentation/agent_graph.py` | **新建**：AgentGraph 类 |
| `src/loopflow/presentation/__init__.py` | 导出 AgentGraph |
| `src/loopflow/presentation/cli.py` | 删除 --from-phase/--only-phase，添加 file_observer 初始化 |
| `src/loopflow/infrastructure/context.py` | 删除 phase 字段，添加 agent_graph |
| `src/loopflow/infrastructure/web_events.py` | 重写 project_events()，构建 agent_graph + fork/join |
| `src/loopflow/infrastructure/file_observation.py` | observe() 参数改为 (call_id, label) |
| `src/loopflow/infrastructure/web_resources.py` | 删除 _extract_declared_phases() |
| `src/loopflow/infrastructure/web_storage.py` | 删除 declared_phases/graph/occurrences，添加 agent_graph |
| `src/loopflow/application/runner.py` | agent_start 添加 label/agent_def/backend，file observe |
| `src/loopflow/application/execution.py` | 删除 phase，添加 agent_graph 初始化 |
| `src/loopflow/application/web.py` | 删除 from_phase/only_phase |
| `web/src/types.ts` | 删除 PhaseNode/PhaseEdge/Occurrence，添加 AgentNode/AgentEdge/agent_graph |
| `web/src/App.tsx` | AgentGraph 组件（dagre），移除 phase 过滤 |
| `web/src/styles.css` | 添加 agent-detail/agent-node 样式 |
| `web/src/test/fixtures.ts` | 更新 fixtures |
| 所有 loop workflow | 删除 phase() 调用和 meta["phases"] |

## 测试结果

```
503 passed, 1 skipped (排除 test_graph_e2e.py, test_web_execution.py)
```

## 遗留问题

- `test_graph_e2e.py`：phase 特定 E2E 测试，待重写为 agent graph E2E
- `test_web_execution.py`：phase 特定测试，待更新
- 并行图结构：fork/join 边的连接逻辑在 back-to-back 并行组场景下仍有优化空间