---
title: Hide Gork Backend Alias Plan
description: 修复 diagnostics/WebUI 将 gork 误拼写别名显示为独立 backend 的问题
type: plan
status: done
created: 2026-07-24T02:04:18Z
---

# Goal

让 backend 检测和 WebUI 只显示正式 backend `grok`，并删除误拼写 backend 名称 `gork`。

# Acceptance

1. `list_available_backends()` 不返回 `gork`。
2. Web backend repository 的 `list()` 不返回 `gork`。
3. 安装指南不展示 `gork`。
4. `_make_backend("gork")` 按 unknown backend 处理，不再创建 Grok backend。
5. 相关 Python/Web 测试通过。

# Steps

1. 删除 backend manager 和 diagnostics 中的 `gork` 注册。
2. 确认 Web resource list 只来自正式 backend 名称。
3. 增加/调整回归测试覆盖 `gork` 不再可用。
4. 运行 targeted tests。
5. 写 Report，标记 done。

# Exit

0067 已完成。WebUI backend 检测不会再显示 `gork`。
