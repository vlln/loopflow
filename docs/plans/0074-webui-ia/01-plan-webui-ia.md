---
title: WebUI 信息架构收敛 Plan
description: Runs 视图信息架构收敛、面板头部抽象、文件变化目录树
type: plan
status: done
created: 2026-07-24T05:10:00Z
---

# Goal

修复人工验收发现的 Runs 视图呈现层缺陷：信息在多个粒度重复表达、面板头部五六套手写结构、文件变化展示粗糙、布局是数据驱动堆积而非任务驱动。

# Scope

1. 去重：事件展示只保留中栏时间线；删除 Inspector 面板（call facts 是 Calls 列表子集）与 metrics 行（有效信息并入工具栏 meta）
2. 三栏任务分工：左栏 run 列表精简（去掉 working_directory 噪声）；中栏 = 工具栏 + intervention 横幅（仅 pending 时）+ phase graph + 事件主区；右栏 File changes 独占全高
3. 抽象复用：`ui.tsx` 新增 `PanelHeader` / `SectionHeader` 组件，全部面板套用；字号收敛为三级标尺（面板标题 13 / 区块标题 11 / 正文 10-11）
4. 文件变化目录树：`buildChangeTree` 按目录聚合变更路径（单子目录链折叠），per-phase 动作标记随选中 phase 切换，非当前 phase 文件弱化
5. Call facts 内联到 Calls 列表选中行；Run state JSON 收为工具栏弹出层
6. 折叠按钮（打开文件变化面板）仅在抽屉模式（≤1180px）显示

# Acceptance

- AC-024-N-4 / N-5 / N-7：断言随目录树设计更新（路径分节点渲染）
- AC-024-N-8（新增）：树标记随选中 phase 切换
- AC-024-B-6 / B-7：空状态保持可见
- AC-010 WebUI 既有场景全部回归通过

# Exit

前端全量测试 + typecheck + build 通过，Playwright e2e 通过，静态资源同步至 `presentation/web/static/`。
