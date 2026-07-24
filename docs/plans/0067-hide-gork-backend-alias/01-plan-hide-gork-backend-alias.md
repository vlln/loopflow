---
title: Hide Gork Backend Alias Plan
description: 修复 diagnostics/WebUI 将 gork 误拼写别名显示为独立 backend 的问题
type: plan
status: pending
created: 2026-07-24T02:04:18Z
---

# Goal

让 backend 检测和 WebUI 只显示正式 backend `grok`，不再显示误拼写别名 `gork`。

# Acceptance

1. `list_available_backends()` 不返回 `gork`。
2. Web backend repository 的 `list()` 不返回 `gork`。
3. 安装指南不展示 `gork`。
4. `_make_backend("gork")` 兼容路径仍可创建 Grok backend，降低历史 workflow 破坏风险。
5. 相关 Python/Web 测试通过。

# Steps

1. 将公开 backend 名称与内部 backend alias 区分。
2. 更新 diagnostics 和 Web resource list 使用公开名称。
3. 增加/调整回归测试覆盖 `gork` 隐藏但内部 alias 可用。
4. 运行 targeted tests。
5. 写 Report，标记 done。

# Exit

0067 完成后，WebUI backend 检测不会再显示 `gork`。
