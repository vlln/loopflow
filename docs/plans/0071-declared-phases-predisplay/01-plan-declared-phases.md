---
title: Declared Phases Predisplay Implementation Plan
description: 实现 meta.phases 声明预显示与运行时合并语义
type: plan
status: done
created: 2026-07-23T15:00:00Z
---

# Goal

实现 ADR-0040 的 declared phases 预显示。Run 创建时从 `meta.phases` 生成占位节点，运行时按 title 匹合并。替换 AC-009/015 declared phases 场景的 planned 节点。

# Acceptance

1. Loop discovery 提取 `meta.phases`（含 title/detail），存入 Loop metadata。
2. 终端 graph renderer 在 Run 启动时预显示 declared phases 占位节点序列。
3. WebUI phase graph 在 Run 创建时预显示 pending 占位节点（低对比度/虚线）。
4. 运行时 phase 事件按 title 匹配替换占位节点为实际节点。
5. undeclared phase 出现时作为新节点出现，带 "undeclared" badge。
6. 无 `meta.phases` 声明时退化为现有涌现行为，不报错。
7. 无效声明（空 title/缺 title）跳过，不崩溃。
8. AC-009-N-4/N-5/N-6/B-4/B-5/B-6/E-3/E-4/F-3 和 AC-015-N-6/N-7/N-8/B-3/B-4/E-3/F-3 manifest planned 节点被真实测试替换。

# Steps

1. discovery 提取 meta.phases，存入 Loop summary 的 metadata。
2. terminal graph renderer 增加 declared phases 占位节点渲染。
3. WebUI types/api 增加 declared phases 字段。
4. WebUI phase graph 组件增加占位节点渲染和合并逻辑。
5. 运行时 phase 事件按 title 匹配替换占位节点。
6. undeclared phase badge 渲染。
7. 替换 AC-009/015 declared phases manifest planned 节点。
8. 运行 Python/Web/manifest 验证。
9. 写 Report、标记 done 并提交。

# Exit

0071 done 后，declared phases 预显示功能可用。
