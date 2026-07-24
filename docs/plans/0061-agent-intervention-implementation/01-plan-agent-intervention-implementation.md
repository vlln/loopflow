---
title: Agent Structured Intervention Implementation Plan
description: 实现 Agent requests/options、batch respond 和多问题 WebUI
type: plan
status: done
created: 2026-07-23T18:30:00Z
---

# Goal

替换 AC-023 的 planned 节点，实现 Agent structured intervention vNext，同时保持 AC-020..022 已有恢复/停止/介入语义不回归。

# Acceptance

1. Agent structured output 支持 `requests[]`，每个 request 持久化 source/options/allow_custom。
2. workflow `intervene()` 支持 options/allow_custom，并且 CLI run 与 Web executor 均注入一致。
3. response 统一为 string；options/custom 校验由框架层保证。
4. batch respond all-or-nothing，一次恢复 worker。
5. WebUI 支持多 pending requests 一次填写和提交。
6. AC-023 manifest planned nodes 被真实测试节点替换。

# Steps

1. 更新 intervention storage/read model 和校验。
2. 更新 runtime/runner/CLI/Web application/API。
3. 更新 Web types/API/UI/tests。
4. 增加/替换 AC-023 测试节点和 manifest。
5. 运行 Python/Web/manifest 相关验证。
6. 写 Report、标记 done 并提交。

# Exit

0061 done 后进入 SYSTEM_TEST 前置，准备全量回归。
