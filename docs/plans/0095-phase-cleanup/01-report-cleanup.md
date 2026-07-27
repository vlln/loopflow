---
title: 0.24.0 Phase 残留收尾 Report
description: BL-022~025 执行结果
type: report
status: complete
created: 2026-07-27T06:00:00Z
---

# Report: 0.24.0 Phase 残留收尾

## 执行结果

### BL-022: Phase 残留清理 [PASS]

删除了 ADR-0052 声称删除但实际未删的全部符号：

| 删除项 | 文件 |
|--------|------|
| `def phase(title)` | runtime.py |
| `_emit_phase()` | events.py |
| `PhaseGraph`, `Edge` | graph.py (整文件删除) |
| `TerminalGraphRenderer` | graph_renderer.py (整文件删除) |
| `from_phase`/`only_phase` CLI 选项 | cli.py |
| `from_phase`/`only_phase` context 属性 | context.py |
| `from_phase`/`only_phase` web API | web.py |
| `from_phase`/`only_phase` execution options | execution.py |
| `_phase_counter`/`_current_phase`/`_prev_phase` context 属性 | context.py |
| `declared_phases` 元数据提取 | execution.py |
| `phase`/`phase_id` EventWriter.append 参数 | web_events.py |
| `phase`/`phase_id` `_write_event` 处理 | context.py |
| `test_graph.py`, `test_graph_renderer.py` | 测试文件删除 |

重写 19 个失败测试：
- test_graph_e2e.py: 8→7 测试，基于 agent_graph 投影
- test_web_execution.py: 移除 phase() 调用和 phase_id 断言
- test_runtime.py: 删除 TestPhaseTracking 类
- test_web_events.py: 重写 v2 envelope 断言
- test_cli.py: 删除 --graph flag 测试

### BL-023: agent_graph fan-in 投影修复 [PASS]

`project_events()` 的 3 个 bug 全部修复：
1. **back-to-back fork join 边不生成** → fork_start 时检查 pending_join，fork_end 时为每个 child 添加 join 边
2. **pending_join 跨组合并** → fork_end 时正确消费 pending_join
3. **fork source 错误** → back-to-back 场景下 fork_parent=None，不生成错误的 fork 边

新增 `fork_active` 标志区分 "在 fork 内" 和 "fork_parent 非空"。

新增 3 个单元测试：single fork、back-to-back forks、fork without preceding agent。

join-edge CSS：`.join-edge` 用虚线 + mint-strong 色，区别于 fork-edge（实线 accent 色）和 sequential（默认）。

### BL-024: 节点详情面板 [PASS]

新增 `agent-detail-panel` 组件（App.tsx），点击 agent 节点时显示：
- Agent label, agent_def, backend, model, exit code
- Started/finished 时间
- Events scope tabs（Events / Unattributed / Malformed）

### BL-025: Playwright fixture 清理 [PASS]

- webui.spec.ts: 移除 phase_id 字段
- App.test.tsx: 14 个失败测试修复（Phase graph → Agent graph，phase_id → call_id/label，删除 3 个 phase 专属测试）
- styles.css: `.phase-node` → `.agent-node`，删除 is-declared/is-undeclared

## 测试结果

| 层 | 通过 | 跳过 | 失败 |
|----|------|------|------|
| Python (pytest) | 500 | 1 | 0 |
| WebUI (vitest) | 42 | 0 | 0 |
| Playwright | 13 | 2 | 0 |

## Commit

- `feat(phase): BL-022 complete phase cleanup` — 删除 PhaseGraph/TerminalGraphRenderer，移除 phase()/from_phase/only_phase，重写 19 测试
- `fix(graph): BL-023 fix project_events fan-in for back-to-back forks + join-edge CSS + 3 unit tests`
- `feat(webui): BL-024 node detail panel + BL-025 fix 14 WebUI tests + Playwright fixture phase_id cleanup`
- `fix(css): replace .phase-node with .agent-node — fix Playwright visual regression`
