---
title: Cancel Recovery Implementation Report
description: 记录 cancelled recover/respond、waiting_input stop 保留 pending request 和 atomic continue boundary 的实现结果
type: report
status: complete
created: 2026-07-23T13:20:00Z
---

# Summary

0052 已实现取消恢复语义。`cancelled` 不再是只能 rerun 的终态；应用层现在根据取消边界、pending intervention 和 durable session 能力派生 recover/respond/continue actions。

# Changes

- `RunRepository`
  - `cancelled` 的 `allowed_actions` 可包含 `recover_retry`、`recover_continue`、`respond` 和 `rerun`。
  - `recover_continue` 在 `active_worker_atomic=true` 时不暴露。
  - pending intervention 会驱动 `respond` action。
- `WebApplication`
  - `stop waiting_input` 只取消当前 attempt，保留 pending request，并记录 `cancel_point=no_worker_running`。
  - `recover_run` 接受 failed 或有恢复边界的 cancelled Run。
  - `recover mode=continue` 在 durable session 缺失或 atomic boundary 时返回 `continue_not_supported`。
  - `respond_intervention` 接受 waiting_input 或 cancelled + pending request。
- `RunContext` / executor
  - Agent call 开始时发布 `active_call_id`。
  - 失败时记录 `active_call_id`；成功恢复后清理失败/取消边界 metadata。
- WebUI
  - cancelled + `respond` 时拉取并展示 intervention。
  - cancelled + recover actions 时展示 Retry/Continue controls。
- Tests
  - 0051 的 7 个 planned recovery nodes 已全部替换为真实 test node。
  - `tests/system/recovery_cases.json` 现在 37 cases，0 planned。

# Verification

| 检查 | 结果 |
|------|------|
| Python targeted | `pytest tests/unit/test_web_application.py tests/integration/test_web_api.py tests/infrastructure/test_recovery_manifest.py tests/infrastructure/test_recovery_support.py tests/unit/test_web_execution.py`：54 passed |
| Python full | `pytest`：340 passed, 1 skipped |
| Web unit | `npm test` in `web/`：11 passed |
| Web typecheck | `npm run typecheck` in `web/`：passed |
| Diff check | `git diff --check`：passed |

# Notes

- 本次实现使用现有 metadata 表达 atomic/isolated worker boundary，没有引入通用原子提交事务系统。
- 首次误跑了 `npm test -- --runInBand`，Vitest 不支持该参数；随后使用项目脚本 `npm test` 通过。

# Next

进入 SYSTEM_TEST，重新执行发布前系统认证。0049 release certification 仍保持 pending，需等 SYSTEM_TEST 通过后恢复发布流程。
