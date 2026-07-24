---
title: System Test Certification Plan
description: 在 develop 上执行 0065-0067 后的系统级验证、失败分类和 RELEASE 入口判定
type: plan
status: done
created: 2026-07-24T02:28:37Z
---

# Goal

证明当前 `develop` 满足 SYSTEM_TEST 阶段命题：系统级验证通过，无阻塞级缺陷，可进入 RELEASE。该 Plan 不实现新功能，只收集机器证据并进行失败原因分类。

# Acceptance

Report 必须记录以下结果：

1. 当前 `develop` HEAD 和工作区状态。
2. 全局 AC manifest 与 recovery manifest 均通过。
3. Python 全量测试、覆盖率、前端 typecheck/unit/build/browser 和 wheel smoke 通过。
4. 0065/0066/0067 的行为风险已被测试覆盖或明确说明。
5. 若有失败，分类为基建缺陷、设计缺陷、局部 bug 或外部环境问题，并给出处置建议。
6. 明确结论：可进入 RELEASE，或退回 DEVELOP/TEST_INFRA/DESIGN 的具体理由。

# Steps

1. 确认 `develop` 工作区干净，记录当前 HEAD。
2. 运行或复用本轮 `./scripts/mr-gate.sh` 结果。
3. 复核 MR gate 输出中的 AC manifest、Python、前端、浏览器和 wheel smoke 结果。
4. 审查 0065/0066/0067 Report 状态，确认 DEVELOP 证据链完整。
5. 创建 `01-report-system-test-certification.md`，回填命令结果、失败分类、阻塞级缺陷判定和阶段建议。
6. 若全部通过，将本 Plan 和容器状态标记为 `done`，准备后续 RELEASE 建议。

# Exit

0068 已完成。Report complete、Plan/container 状态为 done，结论为可进入 RELEASE。
