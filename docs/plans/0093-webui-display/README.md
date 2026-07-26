# 0093 — WebUI call/occurrence 显示简化（BL-021）

对应阶段：`DEVELOP`（0.23.0 迭代）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [WebUI 显示简化](01-plan-webui-display.md) | [Report](01-report-webui-display.md) | done |

## 范围

- BL-021：`web/src/App.tsx` 四处显示简化
  - call-list 主显 `call_id`，`session` 降为 `title` tooltip
  - PhaseNode 节点显示 `×N`（替代 `N occurrence(s)`）
  - phase-detail-bar 显示 `第 N 次执行`（替代 `Occurrence N`）
  - EventTimeline 标题显示 `N 个事件`（替代 `N events`）

## 非范围

- 不改 loopflow 后端代码、不改 deep-research
- 不重构 App.tsx 其他部分（仅这 4 处显示字符串）
- 不合并分支（由用户合并）

## 依据

- BL-021（backlog）
- [AC-015-N-9 / B-5 / E-4 / F-4](../../ac/0010-webui.md)（2026-07-26 追加）
