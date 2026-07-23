---
title: Cancel Recovery Semantics Plan
description: 修订 cancelled/recover/respond/rerun 的语义边界，解除 cancelled 不可恢复假设
type: plan
status: pending
created: 2026-07-23T00:00:00Z
---

# Goal

完成取消恢复语义的 DESIGN 修订，使文档契约表达以下结论：

1. `cancelled` 表示当前 execution attempt 被取消，不表达用户放弃整个 Run identity。
2. 框架不定义“不可恢复”用户意图；无法恢复时由 recover 尝试返回具体错误。
3. `retry` 是恢复默认路径，不作为永远为 true 的能力字段建模。
4. `recover_continue` 与 `respond` 都恢复同一个 Run，但动作语义不同：前者继续 backend durable session，后者提交 intervention input 后恢复 workflow。
5. cancel 点只建模为 `worker_running` 与 `no_worker_running`；是否允许 continue 取决于 active worker 的原子提交/隔离属性和 durable session 能力。
6. `rerun` 是基于原始输入创建新 Run 的用户便利动作，不是旧 Run 的状态转换。

# Acceptance

Report 必须记录：

1. ADR 0036 已修订并保留历史语义变化说明。
2. Spec v13 中 BR-027、BR-034、BR-035 及相关状态/metadata 描述已同步。
3. Interface 0001 的 Run actions、recover/respond 错误码与 response schema 已同步。
4. AC 0011 中 AC-021/022 相关场景已修改或新增，覆盖 cancelled recover、worker running atomic continue 禁止、waiting_input cancel 后 respond/recover 语义。
5. 明确后续实现 Plan 需要修改的代码模块和测试节点。

# Design Decisions To Encode

## Run status

`cancelled` 不再表示不可恢复终态，只表示当前 execution epoch 被用户或框架取消。

## Recovery baseline

只要 Run 有可重放边界，`recover` 默认按 retry/replay 执行；不需要 `can_recover_retry` 或 `retry: true` 字段。

## Continue capability

`recover_continue` 是可选增强，只在以下条件同时满足时暴露：

1. 存在 backend durable session。
2. cancel/fail 点允许恢复该 session。
3. active worker 未处于原子提交/隔离导致的 session continuation 禁止边界。

## Respond capability

`respond` 仅由 pending intervention request 决定。它与 `recover_continue` 都会恢复同一个 Run，但 `respond` 的用户动作是提交外部输入，不是选择 backend session continuation。

## Rerun

`rerun` 创建新 `run_id`，不是原 Run lifecycle transition；文档和 UI 可继续保留该便利动作，但不得作为 cancelled/done/failed 的状态语义依据。

# Steps

1. 修订 ADR 0036：替换“stop 是不可恢复的终止”章节，定义 cancel attempt 语义和恢复能力边界。
2. 修订 Spec v13：更新 BR-027、BR-034、BR-035、状态转换图和 recovery metadata 描述。
3. 修订 Interface 0001：更新 allowed actions、recover 请求适用状态、cancelled response 行为和错误码说明。
4. 修订 AC 0011：调整 AC-021 中 cancelled 只能 rerun 的预期，新增/修改 cancelled recover 与 atomic continue 禁止场景。
5. 写 Report，列出文档变更摘要、风险、后续 TEST_INFRA/DEVELOP 计划建议。
6. 将本 Plan/container 标记 done；若设计审查通过，更新 `docs/README.md` 当前阶段到 `TEST_INFRA` 或 `DEVELOP` 的下一步建议。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| ADR | 取消恢复语义清晰且无不可恢复状态建模 | Report: PASS |
| Spec | 状态、动作、metadata 语义一致 | Report: PASS |
| Interface | API 行为与 Spec 一致 | Report: PASS |
| AC | 新语义有可自动化验收场景 | Report: PASS |
| Downstream | 后续实现模块与测试节点明确 | Report: PASS |

# Review Points

1. 是否接受 `cancelled` 可 recover，失败由 recover 尝试返回错误。
2. 是否接受不建模 `can_recover_retry`，把 retry 作为 recover 默认行为。
3. 是否接受 waiting_input cancel 后 pending request 保留，并由 `respond` 或 recover 继续同一 Run。
4. 是否需要把 `recover_retry` action 名称在接口层改为更通用的 `recover`，UI 仍显示 Retry。

# Exit

ADR/Spec/Interface/AC 修订完成并通过审查后，本设计容器完成。后续按影响范围创建 TEST_INFRA/DEVELOP 容器，实现 cancelled recovery 和对应测试迁移。
