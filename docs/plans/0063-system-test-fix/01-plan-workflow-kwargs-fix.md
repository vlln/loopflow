---
title: Workflow Kwargs Compatibility Fix Plan
description: 修复 SYSTEM_TEST 发现的 workflow kwargs 兼容与 contract example 漏同步
type: plan
status: done
created: 2026-07-23T19:35:00Z
---

# Goal

修复 0062 SYSTEM_TEST MR gate 暴露的局部 bug，使 CLI/Web workflow executor 在注入 `intervene` 等框架能力时兼容严格签名 workflow，并同步 InterventionSummary contract example。

# Acceptance

1. 旧严格签名 workflow 不因新增 `intervene` 注入失败。
2. 接收 `intervene` 或 `**kwargs` 的 workflow 仍能获取该能力。
3. `tests/web_support/contracts.py::contract_examples()` 符合 vNext InterventionSummary。
4. 失败相关测试通过，并可回到 SYSTEM_TEST 重跑 MR gate。

# Steps

1. 增加共享的 workflow kwargs 过滤逻辑，优先保留 `**kwargs` 兼容。
2. CLI run/resume、Web executor、sub-workflow 调用使用该逻辑。
3. 更新 contract example。
4. 运行失败相关测试和 targeted regression。
5. 写 Report，标记 done。

# Exit

本 Plan 完成后，回到 SYSTEM_TEST 继续 0062 认证。
