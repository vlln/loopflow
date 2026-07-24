---
title: Recovery Controls Test Infrastructure Plan
description: 搭建恢复、永久停止和人工介入的 fixture、fake、故障注入、contract schema 与 AC manifest，并完成反向自证
type: plan
status: done
created: 2026-07-22T08:00:00Z
---

# 目标

依据 ADR 0037 搭建 AC-020..022 的一次性测试基础设施，使后续 DEVELOP 可以直接编写业务测试，并证明基建能够拒绝缓存串段、能力误报、epoch 迟到写、停止升级缺失、重复回答和接口漂移。

# Constraints

1. 不修改 `src/loopflow/runtime.py`、AgentRunner、Run application service、Web endpoint 或前端业务组件。
2. 不编写 recover/stop/intervene 产品断言；只测试 fixture、fake、schema 和 checker 自身。
3. 不调用真实 Backend，不操作非测试创建的进程，不读用户真实 Runs。
4. 不增加依赖；使用 pytest、标准库和现有 Web test support。
5. 文档与测试基建代码分开 commit。

# Steps

1. 建立 `tests/recovery_support/`，实现 CallCacheFactory、生命周期段独立 reader 和 InterventionFactory。
2. 实现 SessionBackendFake，覆盖 capability、session ID 暴露时机、create/resume 路由和失败模式。
3. 实现 AtomicWriterFake、RunLockFake、ProcessGroupFake、EpochWriterFake、ClockFake，并提供安全 process-group smoke helper。
4. 增加 v13 Run/Call/Intervention/Backend schema 与正反例 fixture，保持 legacy schema 可用。
5. 将 AC manifest parser 泛化为 profile，新增 AC-020..022 mapping 和 `tests/system/recovery_cases.json` planned manifest。
6. 编写基础设施自证测试，逐项证明 ADR 0037 的七类反例被拒绝。
7. 运行恢复专项、现有 infrastructure、Python 全量测试和 MR gate 的 Python 部分；修复仅由基建改动造成的回归。
8. 回填 ADR Verification 与 Report，将 Plan/README 标记 done。

# Checkpoint

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Cache | succeeded/failed/interrupted/segmented/corrupt/legacy fixture 可生成；跨段消息不串联 | Report：恢复专项测试通过 |
| Backend | durable/non-durable、ID timing、create/resume 调用可独立断言 | Report：恢复专项测试通过 |
| Fault injection | writer/lock/process/epoch/clock 正反例通过 | Report：恢复专项测试通过 |
| Process safety | smoke 只终止测试创建的进程组并完整清理 | Report：POSIX smoke 通过 |
| Contract | v13 schema 正例通过，缺字段/旧枚举/错误 capability 被拒绝 | Report：contract 正反例通过 |
| Manifest | AC-020..022 全覆盖；缺失、重复、`/resume`、错误状态码等反例失败 | Report：32 scenarios |
| Regression | 现有 infrastructure 与 Python 测试保持通过 | Report：33 passed, 1 skipped；全量 290 passed, 1 skipped |
| Scope | 产品目录无业务实现变更 | commits `dd85f55`、`caaf2ad` 仅修改 tests/scripts |

# Exit

全部 Checkpoint 通过、ADR 0037 Verification 有本地证据、Report complete 且分支合并到 develop 后，TEST_INFRA 才可推进到 DEVELOP。
