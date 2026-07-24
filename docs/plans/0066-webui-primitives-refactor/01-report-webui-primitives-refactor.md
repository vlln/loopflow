---
title: WebUI Primitives Refactor Report
description: 记录 WebUI 基础组件与滚动区域整理结果
type: report
status: complete
created: 2026-07-24T01:52:56Z
---

# Summary

已完成 WebUI 基础组件与滚动区域整理。本轮没有改变后端接口、前端路由或业务行为，重点是让后续页面继续扩展时优先复用共享 primitives。

# Results

- 新增 `web/src/ui.tsx`，集中导出 `StatusBadge`、`IconButton`、`EmptyState`、`ScrollArea`、`Metric`、`Fact`。
- `web/src/App.tsx` 移除本地基础组件定义，改为复用共享 primitives。
- 新增 `.scroll-area` CSS utility，统一 scrollbar thumb、hover、overscroll 行为。
- runs、loops、calls、events、process log、backend table 与 intervention questions 改用统一滚动区域。
- 修正 `web/package.json` 中过期的 `test:browser:smoke` 脚本，使其指向当前存在的 `webui.spec.ts`。

# Verification

- `npm --prefix web run typecheck`：passed
- `npm --prefix web test -- --run`：15 passed
- `npm --prefix web run build`：passed
- `npm --prefix web run test:browser -- webui.spec.ts`：10 passed, 2 skipped
- `npm --prefix web run test:browser:smoke`：10 passed, 2 skipped
