---
title: Boolean Choice Compatibility Fix Plan
description: 修复旧 boolean schema intervention 在 vNext WebUI 中不显示 choices 的兼容问题
type: plan
status: pending
created: 2026-07-23T20:45:00Z
---

# Goal

修复旧 `intervene(schema={"type":"boolean"})` 在 InterventionSummary vNext 中被错误投影成 `options=[]/allow_custom=true` 的问题，使 `manual-approval` 这类旧 workflow 在 WebUI 中显示 `true/false` choices。

# Acceptance

1. 已持久化为 `options: []` 的 workflow boolean request，summary 暴露 `options=["true","false"]` 与 `allow_custom=false`。
2. batch/single respond 提交字符串 `"true"` 或 `"false"` 后，持久化和 replay 仍保持 boolean 语义。
3. Agent request 的 options/custom 语义不回退。
4. 相关 Python/Web 测试通过。

# Steps

1. 修正 intervention read model 的 effective options/allow_custom。
2. 修正 legacy boolean response validation 和 normalize。
3. 增加 Web application 与 workflow execution 回归测试。
4. 运行 targeted tests。
5. 写 Report，标记 done。

# Exit

0065 完成后，决定是否发布 `0.19.1` patch。
