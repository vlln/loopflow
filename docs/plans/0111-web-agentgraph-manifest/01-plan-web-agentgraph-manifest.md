---
title: Web AgentGraph manifest 对齐
description: 将 Web strict manifest 增量对齐 Spec v19 和冻结后的 AC-0010/0012
type: plan
status: done
created: 2026-07-29T00:00:00Z
---

# Context

0110 已冻结 AgentGraph/call_id/label 契约，并将 Web AC 从 86 增至 89 个场景。当前 committed manifest 仍保留旧 Phase targets、旧场景文本和 28 个冻结前 TEST_NODES，allow-planned 因 source drift 与 3 个缺失 ID 正确失败。

# Request

1. 更新 TARGETS、HTTP error code 和 protocol expectations，覆盖 89 个 frozen Web 场景。
2. 逐个语义复核既有 TEST_NODES；仅保留对当前 AC oracle 完整成立的节点。
3. 重新生成 `tests/system/cases.json`，更新基础设施锁定测试。
4. 证明 allow-planned 全绿，strict 只拒绝真实 planned 缺口，并完成独立 subagent 审查。

# Constraints

- 不新增具体业务测试、不修改产品实现；这些属于 DEVELOP。
- 不把 partial 节点登记为完整映射，不以 arbitrary existing selector 绕过 strict。
- 不修改 active Spec/AC/Interface 或 accepted ADR。
- 仅执行本轮增量基础设施测试，不重复已经通过的 SYSTEM_TEST 层。
- 文档与测试基建代码分开提交。

# Checkpoint

- [x] 89 个场景均有 frozen targets/expectations
- [x] TEST_NODES 经当前 oracle 逐项复核
- [x] committed manifest 与 generator 一致
- [x] allow-planned 通过，strict 仅拒绝 planned
- [x] 增量 infrastructure tests 通过
- [x] 独立 subagent 最终审查 PASS
