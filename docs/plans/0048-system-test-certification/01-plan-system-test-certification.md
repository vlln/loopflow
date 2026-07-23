---
title: System Test Certification Plan
description: 在 develop 上执行发布前系统级验证、失败分类和 RELEASE 入口判定
type: plan
status: pending
created: 2026-07-23T00:00:00Z
---

# Goal

证明当前 `develop` 满足 SYSTEM_TEST 阶段命题：系统级验证通过，无阻塞级缺陷，可进入 RELEASE。该 Plan 不实现新功能，只收集机器证据并进行失败原因分类。

# Acceptance

Report 必须记录以下结果：

1. 全量自动化测试与 MR gate 的真实命令输出摘要。
2. 全局 AC manifest 和 recovery strict manifest 均通过，且无 `planned::` 节点。
3. Web 前端单测、类型检查、生产构建和浏览器测试均通过。
4. wheel smoke 通过，确认包内 Web assets 可用。
5. 若有失败，逐项分类为基建缺陷、设计缺陷、局部 bug 或外部环境问题，并给出处置建议。
6. 明确结论：可进入 RELEASE，或退回 DEVELOP/TEST_INFRA/DESIGN 的具体理由。

# Steps

1. 确认 `develop` 工作区干净，记录当前 HEAD。
2. 运行 `python3 scripts/check-ac-manifest.py`。
3. 运行 `python3 scripts/check-ac-manifest.py --profile recovery`。
4. 运行 `./scripts/mr-gate.sh`，覆盖 Python、AC manifest、前端、浏览器和 wheel smoke。
5. 如 MR gate 失败，先不修复，记录失败层级和判断；只有局部 bug 且用户同意时才创建后续修复 Plan。
6. 审查 `docs/plans/` 已完成容器的 Report 状态，确认 DEVELOP 证据链完整。
7. 创建 `01-report-system-test-certification.md`，回填命令结果、失败分类、阻塞级缺陷判定和阶段建议。
8. 若全部通过，将本 Plan 和容器状态标记为 `done`，并准备后续 RELEASE 计划建议。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Workspace | `develop` 干净，HEAD 可追踪 | Report: PASS |
| AC manifest | 全局 60 scenarios 通过 | Report: PASS |
| Recovery manifest | recovery 32 scenarios 通过，无 planned | Report: PASS |
| MR gate | `./scripts/mr-gate.sh` 通过 | Report: PASS |
| Failure classification | 无失败，或失败均有明确分类和处置 | Report: PASS |
| Release readiness | 无阻塞级缺陷，有明确 RELEASE 入口建议 | Report: PASS |

# Review Points

1. 是否接受 SYSTEM_TEST 只做认证，不直接创建 release 分支。
2. 若出现仅由外部环境导致的失败，是否允许在 Report 中标记为非阻塞并附重试证据。
3. 若发现局部 bug，是否退回 DEVELOP 并创建新的 fix 执行容器。

# Exit

Report complete、Plan/container 状态为 done，并且给出明确阶段建议后，SYSTEM_TEST 执行完成。若结论为可发布，下一步进入 RELEASE：创建 release 执行容器、整理 CHANGELOG、建立 release 分支、打 tag 并执行发布冒烟。
