---
title: WebUI Primitives Refactor Plan
description: 整理 WebUI 基础组件与滚动区域样式，降低 runs/loops 页面局部重复
type: plan
status: done
created: 2026-07-24T01:52:56Z
---

# Goal

在不改变 WebUI 行为和后端接口的前提下，提取基础 UI primitives，并统一滚动区域样式，使 runs、loops、backends 与 intervention 相关视图使用一致的基础外观。

# Acceptance

1. `StatusBadge`、`IconButton`、`EmptyState` 等基础组件从主应用文件中抽出并复用。
2. 常见滚动区域使用统一 `.scroll-area` 样式，移除 runs/loops 中互相不一致的局部 scrollbar 规则。
3. `App.tsx` 保持现有业务流程和测试可见文本/aria label 稳定。
4. 前端 typecheck、单元测试和浏览器 smoke 通过。

# Steps

1. 创建 shared UI primitives 文件，迁移已有基础组件。
2. 更新 `App.tsx` 引用，保持页面结构和行为不变。
3. 添加统一 scrollbar CSS utility，并应用到现有滚动容器。
4. 运行前端验证。
5. 写 Report，标记 done。

# Exit

0066 已完成。WebUI 后续功能优先复用 primitives；更大范围页面拆分另起执行容器。
