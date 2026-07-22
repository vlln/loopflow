---
title: Deterministic Recovery Engine Report
description: 记录可校验重放、retry/continue、稳定 Call ID、API/CLI/WebUI 与 AC-020 验收结果
type: report
status: complete
created: 2026-07-22T10:00:00Z
---

# Summary

已实现 failed Run 的确定性恢复。恢复从 workflow `meta.state` 默认值重放，前序 Call 仅在稳定 `call_id`、SHA-256 `input_digest` 与已提交成功段同时匹配时命中；失败 Call 可选择 retry 新 session，或在 backend 同时声明可恢复且 session ID 持久时 continue 原 session。路径、输入或目标到达发生分歧时同步返回 `replay_diverged`，不静默执行错误调用。

# Acceptance Results

| AC | 结果 | 测试节点 | 提交 |
|----|------|----------|------|
| AC-020-N-1 | [PASS] | `tests/unit/test_runtime.py::TestAgent::test_recovery_replays_success_then_retries_failed_call` | `f4c72b9` |
| AC-020-N-2 | [PASS] | `tests/unit/test_runtime.py::TestAgent::test_recovery_continue_uses_failed_durable_session` | `f4c72b9` |
| AC-020-N-3 | [PASS] | `tests/unit/test_runtime.py::TestAgent::test_agent_writes_cache` | `f4c72b9` |
| AC-020-N-4 | [PASS] | `web/src/App.test.tsx::disables Continue when the failed backend has no durable session` | `f4c72b9` |
| AC-020-B-1 | [PASS] | `tests/unit/test_runtime.py::TestRunContext::test_parallel_namespaces_are_stable_by_input_position` | `f4c72b9` |
| AC-020-B-2 | [PASS] | `tests/unit/test_recovery.py::test_corrupt_tail_is_uncommitted_and_legacy_success_is_unverified` | `f4c72b9`, `be7f6f8` |
| AC-020-B-3 | [PASS] | `tests/integration/test_cli.py::TestResume::test_resume_is_deprecated_retry_alias_for_failed_run` | `f4c72b9`, `be7f6f8` |
| AC-020-E-1 | [PASS] | `tests/unit/test_web_execution.py::test_background_executor_surfaces_replay_divergence_before_return` | `f4c72b9` |
| AC-020-E-2 | [PASS] | `tests/unit/test_web_application.py::test_continue_requires_durable_session_and_concurrent_recovery_is_rejected` | `f4c72b9` |
| AC-020-E-3 | [PASS] | `tests/unit/test_recovery.py::test_call_digest_is_stable_and_tracks_workflow_and_prompt` | `f4c72b9` |
| AC-020-F-1 | [PASS] | `tests/unit/test_recovery.py::test_corrupt_tail_is_uncommitted_and_legacy_success_is_unverified` | `f4c72b9` |
| AC-020-F-2 | [PASS] | `tests/unit/test_web_execution.py::test_background_executor_rejects_second_worker_for_same_run` | `f4c72b9` |
| AC-020-F-3 | [PASS] | `tests/unit/test_web_execution.py::test_recovery_fails_when_workflow_ends_before_target` | `f4c72b9` |

# Checkpoint Results

| 检查点 | 结果 | 证据 |
|--------|------|------|
| Cache contract | PASS | lifecycle segment reader、损坏尾部与 retry 隔离测试通过 |
| Replay correctness | PASS | digest 漂移、提前结束和目标到达握手均有失败断言 |
| Session modes | PASS | retry 仅创建新 session；continue 仅恢复已持久化 durable session |
| Stable identity | PASS | 顺序、parallel 和 pipeline 使用预分配层级 Call ID |
| Concurrency | PASS | `.execution.lock` 拒绝并发 worker；`execution_epoch` 单调递增并保护终态写入 |
| Compatibility | PASS | legacy retry 写入 `recovery_verification=unverified` 并警告；CLI `resume` 已弃用；Web `/resume` 已移除 |
| UI/API | PASS | `/recover`、allowed actions、Retry/Continue 控件及不可用原因测试通过 |
| AC coverage | PASS | AC-020 的 13 项均为真实节点；recovery allow-planned manifest 32 项通过；scoped submission gate 通过 |
| Regression | PASS | MR gate、Python、Vitest、Playwright、Web 历史 manifest 与 wheel smoke 通过 |

# Changes

- 新增 Call lifecycle segment、规范化 digest、稳定层级 Call ID 与 replay selection。
- 扩展 backend capability 与 session callback，区分 retry 新 session 和 continue durable session。
- 执行器从 `meta.state` 默认值恢复，冻结 execution options，并以 Run lock、epoch 和恢复握手保护一致性。
- Web API 迁移到 `POST /runs/{run_id}/recover`；CLI 增加 `recover`，旧 `resume` 成为弃用 retry alias。
- WebUI 根据 Run 和 backend capability 提供 Retry/Continue 操作。
- AC-020 的 13 个 manifest 节点全部替换为真实 unit/integration/UI 测试。

# Verification

- Python full suite: 313 passed, 1 skipped；coverage 81.22%。
- Vitest: 9 passed；TypeScript typecheck: PASS。
- Playwright Chromium: 10 passed, 2 skipped。
- Recovery manifest: 32 scenarios；既有 Web manifest: 60 scenarios。
- `npm audit --audit-level=low`: 0 vulnerabilities。
- MR gate: PASS；wheel isolated smoke: PASS；scoped submission gate: PASS。

# Residual Risks

- 恢复是从确定性初始状态重放 workflow，不是 Python 调用栈快照；时间、随机数或外部读取改变语义输入时会拒绝恢复并返回 `replay_diverged`。
- `continue` 的可靠性受 backend 的 durable session 语义约束；能力或 session ID 不足时明确返回 `continue_not_supported`，不降级为 retry。
- 无 digest 的旧缓存仅允许 unverified retry，保持只读且不支持 continue。
- AC-021 可靠停止和 AC-022 阻塞介入仍为后续 Plan 范围；其 19 个 manifest 节点继续为 `planned::`。
