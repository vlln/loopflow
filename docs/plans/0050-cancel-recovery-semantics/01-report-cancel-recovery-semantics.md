---
title: Cancel Recovery Semantics Report
description: 记录 cancelled/recover/respond/rerun 语义修订结果和后续实现范围
type: report
status: complete
created: 2026-07-23T12:32:11Z
---

# Summary

0050 已完成 DESIGN 文档修订。`cancelled` 现在表示当前 `execution_epoch` 被取消，不表示用户放弃 Run identity，也不是框架定义的不可恢复状态。恢复失败由具体 `recover` 或 `respond` 尝试返回错误。

# Changes

## ADR

- 修订 [ADR 0036](../../adr/0036-recovery-intervention.md)，将原“stop 是不可恢复的终止”替换为“stop 取消当前 execution attempt”。
- 保留历史语义变化说明：早期方案把 `cancelled` 建模为不可恢复终态并关闭未回答 Intervention，现改为不建模用户 abandon 意图。
- 明确 cancel point 只建模为 `worker_running` 和 `no_worker_running`。
- 明确 atomic/isolated worker 被取消时禁止 `continue`，只能通过 retry/replay 恢复。

## Spec

- 修订 [Spec v13](../../spec/0001-loopflow.md) 的 US-006、run metadata、Intervention status 说明、BR-027、BR-033、BR-034、BR-035、BR-039 和术语表。
- 增加恢复派生 metadata：`cancel_point`、`active_call_id`、`active_worker_atomic`。
- 明确 `retry` 是默认恢复路径，不需要建模 `retry: true` 或 `can_recover_retry`。
- 明确 `rerun` 是创建新 Run 的便利动作，不是旧 Run lifecycle transition。

## Interface

- 修订 [Interface 0001](../../interface/0001-web-api.md)：
  - `allowed_actions` 保留 `recover_retry` 作为兼容 action 名，但不作为单独能力字段。
  - `POST /runs/{run_id}/recover` 适用于 failed Run 和有可重放取消边界的 cancelled Run。
  - `POST /runs/{run_id}/stop` 对 waiting_input 不关闭 pending request。
  - `POST /runs/{run_id}/interventions/{request_id}/response` 允许 waiting_input 或保留 pending request 的 cancelled Run 提交回答。
  - `recover_continue` 需要 durable session，且不能跨 atomic/isolated worker 取消边界。

## AC

- 修订 [AC 0011](../../ac/0011-recovery-intervention.md)：
  - AC-021-N-2 覆盖 waiting_input stop 后 pending request 保留。
  - AC-021-N-3 覆盖 cancelled Run recover mode=retry。
  - AC-021-B-3 覆盖 atomic/isolated worker cancel 后 continue forbidden。
  - AC-021-B-4 覆盖非 atomic durable worker cancel 后 continue 可用。
  - AC-022-N-5 和 AC-022-B-3 覆盖 cancelled + pending intervention 的 respond/保持 pending 语义。

# Checkpoints

| 检查点 | 结果 | 证据 |
|--------|------|------|
| ADR | PASS | ADR 0036 已替换永久 stop 语义并保留历史说明 |
| Spec | PASS | BR-027/033/034/035/039 与 metadata 已同步 |
| Interface | PASS | Run actions、recover/respond 适用状态与错误说明已同步 |
| AC | PASS | cancelled recover、atomic continue forbidden、waiting_input cancel 后 respond 已覆盖 |
| Downstream | PASS | 下方列出 TEST_INFRA/DEVELOP 修改范围 |

# Downstream Plan

建议下一阶段进入 `TEST_INFRA`，先更新测试契约和夹具，再进入产品代码实现。后续 Plan 应覆盖：

| 层级 | 模块/测试节点 | 变更点 |
|------|---------------|--------|
| TEST_INFRA | `tests/application` recovery/stop/intervention fixtures | 增加 cancelled recover、pending intervention after stop、atomic continue forbidden 场景 |
| TEST_INFRA | Web API contract tests | 更新 `/recover`、`/stop`、`/interventions/{id}/response` 的状态约束和错误码断言 |
| DEVELOP | `src/loopflow/application/` | allowed_actions 派生、recover/respond 命令状态约束、cancel metadata 持久化 |
| DEVELOP | `src/loopflow/runtime.py` / Agent runner | active call、atomic/isolated worker 边界、cancel point 记录 |
| DEVELOP | `src/loopflow/presentation/web/` 和 `web/` | UI 操作展示：cancelled 可 recover/respond，continue 禁用原因 |
| DEVELOP | `src/loopflow/presentation/cli.py` | deprecated `resume` 兼容 failed/cancelled recover retry，legacy stopped 仍拒绝 |

# Risks

- 原子/隔离 worker 的定义需要在实现阶段落到清晰 API，否则 `active_worker_atomic` 只能作为内部推断，测试会不稳定。
- 保留 `recover_retry` action 名可以降低兼容风险，但 UI 文案应显示为 Retry 或 Recover，避免把它误读为框架能力字段。
