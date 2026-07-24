---
title: WebUI 信息架构收敛 Report
description: Runs 视图信息架构收敛、面板头部抽象、文件变化目录树执行结果
type: report
status: done
created: 2026-07-24T05:15:00Z
---

# Summary

Runs 视图完成信息架构收敛：消除全部重复表达，三栏按任务分工，面板头部统一为 PanelHeader / SectionHeader 抽象，文件变化升级为 per-phase 目录树。代码提交见 `fix/0074-webui-ia` 分支 `fix(webui)` 提交。

# Changes

| 项 | 内容 |
|----|------|
| 去重 | 删除 Inspector 面板（facts 并入 Calls 列表选中行内联展开）、删除 metrics 行（duration/iterations/stream 并入工具栏 meta，Calls 计数留在 Calls 区块头） |
| 三栏分工 | 左栏 run 列表精简（去 working_directory）；中栏 = 工具栏 + intervention 横幅 + phase graph + 事件主区；右栏 File changes 独占全高 |
| 抽象 | `ui.tsx` 新增 `PanelHeader` / `SectionHeader`，8 处面板/区块头部套用；删除 6 套手写头部变体（workspace-title、section-heading、file-changes-header、event-list-heading、run-heading、loop-identity h2） |
| 字号 | 统一三级标尺：面板标题 13px、区块标题 11px、正文/列表 10-11px |
| 目录树 | `buildChangeTree` 聚合变更路径（单子目录链折叠）；per-phase 动作 chip 随选中 phase 切换，非当前 phase 文件弱化；deleted 文件名删除线 |
| Intervention | 从中栏独立 grid 行移入顶部横幅位（仅 hasIntervention 时出现），警告色卡片样式 |
| Run state | 从右栏黄金位置收为工具栏 `{}` 弹出层 |
| 折叠按钮 | 打开文件变化面板按钮仅在 ≤1180px 抽屉模式显示（桌面右栏常驻，按钮冗余） |
| 死代码 | 删除 CallInspector / Metric / Fact 组件及约 40 行死 CSS |

# AC Results

| AC | 结果 | 说明 |
|----|------|------|
| AC-024-N-4 | [PASS] | 断言更新为目录树节点（raw.json + created + size） |
| AC-024-N-5 | [PASS] | 树合并全部 phase 记录，显示最新动作与 size |
| AC-024-N-7 | [PASS] | SSE file_changes 实时追加到目录树 |
| AC-024-N-8 | [PASS] | 新增：树标记随选中 phase 切换（1024 B ↔ 1024 → 2048 B） |
| AC-024-B-6 | [PASS] | legacy run 空状态保持 |
| AC-024-B-7 | [PASS] | 无变化空状态保持 |
| AC-010 WebUI 场景 | [PASS] | 既有单测 + e2e 全部回归通过 |

# Verification Results

| 层 | 结果 |
|----|------|
| vitest | 21 passed（3 test files） |
| typecheck | clean |
| Playwright e2e | 10 passed, 2 skipped（chromium-390/1024/1440） |
| build | 成功，静态资源已同步 `presentation/web/static/` |
| Python | 未改动，无需重跑 |

# Notes

- 去重效果有测试佐证：`wf-review-a` 在页面上出现次数从 2 降为 1。
- 文件观察的 per-run working directory 与基线快照语义属后续迭代（ADR-0039 修订 + 新 ADR），不在本容器。
