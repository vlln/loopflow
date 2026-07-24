---
title: Intervention WebUI Implementation Plan
description: 按 0056/0057 对齐用户回答问题的 WebUI 优先级、history 和错误展示
type: plan
status: done
created: 2026-07-23T17:00:00Z
---

# Goal

让 WebUI 的 Intervention panel 与冻结契约一致：pending response 是主操作，recover retry 是次要动作；answered/history 可读；submit error 贴在 panel 内并保留输入。

# Acceptance

1. `cancelled + pending request` 时 Intervention panel 承载主操作，toolbar 的 retry 不再使用 primary 样式。
2. 多个 request 时最早 pending 为主，其余 pending/answered/closed 只读折叠展示。
3. answered request 显示 response 摘要和 responded_at，不显示再次提交控件。
4. respond API error 同时保留 toast 和 panel-level error，输入内容不丢失。
5. 回答成功后刷新 Run detail 和 intervention read model。
6. Web unit tests 覆盖主操作层级、history/answered/error。

# Steps

1. 更新 App state 刷新逻辑，保存最新 interventions。
2. 重构 `InterventionPanel` 的 pending/history/error 渲染。
3. 调整 toolbar recovery button 样式优先级。
4. 补充 Web unit tests。
5. 运行 Web typecheck/unit tests 和相关 Python contract tests。
6. 写 Report、标记 done 并提交。

# Exit

验收通过后进入 SYSTEM_TEST 前置状态，准备跑更大范围回归。
