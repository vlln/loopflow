---
title: Agent Structured Intervention Test Infrastructure Plan
description: 固化 Agent structured requests/options/batch respond 的 AC、接口和测试契约
type: plan
status: done
created: 2026-07-23T18:00:00Z
---

# Goal

让 Agent structured intervention vNext 有明确的验收场景、接口契约和 planned manifest 节点，为 DEVELOP 实现提供严格目标。

# Acceptance

1. AC 覆盖 Agent 单 turn 多 requests、options/allow_custom 校验、batch respond all-or-nothing、workflow `intervene()` routing gate、CLI/Web intervene 注入一致性。
2. Interface 0001 声明 vNext `InterventionSummary` 字段：`source/options/allow_custom/response:string`。
3. Interface 0001 声明 batch respond endpoint，且明确 all-or-nothing 副作用边界。
4. Test support 新增 vNext contract schema 和 negative shape tests。
5. Recovery manifest 覆盖新增 AC，新增实现节点保持 `planned::`。
6. 测试基建自证通过，不修改产品代码。

# Steps

1. 补 AC-023 Agent structured intervention vNext。
2. 补 Web API vNext read model 和 batch respond command。
3. 在 recovery test support 增加 vNext schema/examples/negative tests。
4. 更新 recovery manifest mapping 和 `tests/system/recovery_cases.json`。
5. 运行 infrastructure tests、manifest checker 和 `git diff --check`。
6. 写 Report、标记 done 并提交。

# Exit

本容器 done 后进入 DEVELOP，逐项替换 planned 节点为真实实现测试。
