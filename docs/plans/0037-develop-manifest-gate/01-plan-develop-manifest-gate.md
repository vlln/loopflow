---
title: DEVELOP manifest 门禁修复 Plan
description: 修复局部 DEVELOP feature 因未实现的其他 AC planned 节点而无法通过 MR 门禁的问题。
type: plan
status: done
created: 2026-07-19T06:00:00Z
---

# Context

ADR 0035 要求局部 DEVELOP Plan 只验证自己声明的 AC，进入 SYSTEM_TEST 前才要求 manifest 全集为真实节点；当前脚本在 DEVELOP 已启用严格模式，与 accepted ADR 冲突。

# Request

让 INIT、DESIGN、TEST_INFRA、DEVELOP 允许 planned 节点，SYSTEM_TEST 与 RELEASE 使用严格模式。

# Output Format

- `scripts/mr-gate.sh` 阶段判断修复。
- 基建测试证明 DEVELOP 宽松、SYSTEM_TEST 严格。

# Constraints

不修改 AC、Interface、Spec 或 accepted ADR。

# Checkpoint

测试通过且本地 manifest 在 DEVELOP 使用 `--allow-planned` 可通过。证据：`d824cfe`，基建测试 6 passed，manifest 60 scenarios。

# Steps

1. 添加失败测试。
2. 修正阶段判断。
3. 运行基建测试和 manifest 检查。

# Acceptance

- ADR 0035 第 7 节局部 DEVELOP Plan 门禁规则
