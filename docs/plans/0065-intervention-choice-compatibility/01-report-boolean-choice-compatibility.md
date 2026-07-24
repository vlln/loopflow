---
title: Boolean Choice Compatibility Fix Report
description: 记录旧 boolean schema intervention choices 兼容修复结果
type: report
status: complete
created: 2026-07-23T20:45:00Z
---

# Summary

已修复旧 boolean schema intervention 在 vNext WebUI 中不显示 choices 的兼容问题。`manual-approval` 这类仍调用 `intervene(schema={"type":"boolean"})` 的 workflow，现在会在 summary 中暴露 `options=["true","false"]`、`allow_custom=false`；用户提交字符串后，持久化与 replay 仍保持 boolean 语义。

# Results

- `src/loopflow/infrastructure/intervention.py` 新增 effective options/allow_custom 计算，空 `options` 时可 fallback 到 boolean schema。
- legacy workflow boolean request 接受 bool 或字符串 `"true"/"false"`，并将字符串 normalize 为 boolean 存储。
- 新增 Web application 回归测试覆盖已持久化 `options: []` 的旧 request。
- 新增 workflow execution 回归测试覆盖 `intervene(schema={"type":"boolean"})` 创建 request 后的 summary choices。

# Verification

- `pytest tests/unit/test_web_application.py tests/unit/test_web_execution.py tests/integration/test_web_api.py -q`：47 passed
- `npm --prefix web run typecheck`：passed
- `npm --prefix web test -- --run`：15 passed
