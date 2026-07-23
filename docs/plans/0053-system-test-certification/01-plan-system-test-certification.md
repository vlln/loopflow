---
title: System Test Certification Plan
description: 在取消恢复语义实现后重新执行 develop 系统级验证
type: plan
status: pending
created: 2026-07-23T13:30:00Z
---

# Goal

证明当前 `develop` 在 0050/0051/0052 后重新满足 SYSTEM_TEST 阶段命题：系统级验证通过，无阻塞级缺陷，可恢复 RELEASE 流程。

# Acceptance

1. 记录当前 HEAD 和测试前工作区状态。
2. `python3 scripts/check-ac-manifest.py` 通过。
3. `python3 scripts/check-ac-manifest.py --profile recovery` 通过，且 recovery manifest 无 planned 节点。
4. `./scripts/mr-gate.sh` 通过。
5. 对所有失败或警告进行分类。
6. 明确结论：可进入 RELEASE，或退回相应阶段。

# Steps

1. 确认当前 HEAD 与工作区状态。
2. 运行全局 AC manifest。
3. 运行 recovery strict manifest。
4. 运行 MR gate。
5. 汇总测试证据和非阻塞警告。
6. 写 Report，标记 Plan/container done。
7. 若通过，将 `docs/README.md` 当前阶段推进到 `RELEASE`。

# Exit

Report complete，Plan/container done，并给出 release readiness 结论。
