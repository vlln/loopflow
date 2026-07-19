---
title: WebUI System And Visual Test Plan
description: 在 develop 成品上验证服务集成、CLI/API/UI 黑盒、视觉布局、wheel 与兼容性。
type: plan
status: done
created: 2026-07-19T07:10:00Z
---

# Context

0036、0038、0039 已合并且 DEVELOP 提测门禁通过。

# Request

按 SYSTEM_TEST 层级执行集成、严格契约、CLI E2E、wheel、Vitest、production build 与 Chromium 三视口测试，并人工复查截图。

# Output Format

独立 Report，记录通过数、覆盖率、视觉证据和失败分类。

# Constraints

仅在 `develop` 验证成品；不新增功能，不修改 Spec/ADR。

# Checkpoint

所有功能/视觉/兼容性检查通过，无阻塞缺陷。

# Steps

1. 运行集成与严格 manifest。
2. 运行 CLI E2E、wheel 与前端全套。
3. 复查 1440/1024/390 截图与 trace。
