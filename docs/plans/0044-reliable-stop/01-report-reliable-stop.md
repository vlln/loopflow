---
title: Reliable Stop Report
description: 记录 AC-021 可靠停止实现、验证结果和剩余边界
type: report
status: complete
created: 2026-07-22T18:45:00Z
---

# Summary

实现 AC-021 可靠停止。`stop` 现在对 `running` Run 先落盘 `cancelling`，再按持久化 worker identity 终止进程组，最终写 `cancelled` 并清除 worker 字段；`waiting_input` Run 不要求 PID，直接取消并关闭现有 pending intervention 文件。CLI `stop` 与 Web `stop` 已收敛到同一个 application service，不再从 presentation 层读取 `loop.pid` 或直接发信号。

# Acceptance

| 场景 | 结果 | 证据 | 提交 |
|------|------|------|------|
| AC-021-N-1 | [PASS] | `tests/unit/test_web_application.py::test_create_stop_recover_rerun_and_invalid_transition` | `9a6c6a3` |
| AC-021-N-2 | [PASS] | `tests/unit/test_web_application.py::test_stop_waiting_input_cancels_without_worker_and_closes_pending_request` | `9a6c6a3` |
| AC-021-B-1 | [PASS] | `tests/unit/test_web_application.py::test_stop_escalates_to_kill_result_and_legacy_stopped_has_only_rerun` | `9a6c6a3` |
| AC-021-B-2 | [PASS] | `tests/unit/test_web_application.py::test_stop_escalates_to_kill_result_and_legacy_stopped_has_only_rerun` | `9a6c6a3` |
| AC-021-E-1 | [PASS] | `tests/unit/test_web_execution.py::test_execute_workflow_terminal_guard_does_not_overwrite_cancelled` | `9a6c6a3` |
| AC-021-E-2 | [PASS] | `tests/unit/test_web_application.py::test_stop_rejects_cancelled_without_modifying_run` | `9a6c6a3` |
| AC-021-F-1 | [PASS] | `tests/unit/test_web_application.py::test_stop_does_not_signal_when_cancelling_write_fails` | `9a6c6a3` |
| AC-021-F-2 | [PASS] | `tests/unit/test_web_application.py::test_stop_pid_reuse_does_not_signal_and_records_process_gone` | `9a6c6a3` |

# Checkpoints

| 检查点 | 结果 | 证据 |
|--------|------|------|
| State machine | PASS | running -> cancelling -> cancelled；waiting_input -> cancelled；cancelled stop 返回 409 且字节不变 |
| Process control | PASS | `process_group_id` 持久化；TERM/KILL/process_gone/PID reuse 均由 process port 测试覆盖 |
| CLI/Web parity | PASS | CLI `stop` 调用同一 WebApplication service；回归测试证明 `loop.pid` 不再作为权威 PID |
| Race guard | PASS | worker 终态写入要求当前 status 仍为 running 且 epoch 匹配 |
| API/UI | PASS | Web API 返回 `cancelled`；WebUI 支持 waiting_input/cancelled 状态筛选和 cancelled badge |
| Legacy | PASS | legacy `stopped` 可读、只提供 rerun，不提供 stop/recover |
| AC coverage | PASS | AC-021 8 个 manifest 节点已替换为真实测试；AC-022 planned 保持不变 |
| Regression | PASS | Python、frontend、browser、audit、wheel smoke 和 MR gate 均通过 |

# Verification

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/unit/test_web_application.py tests/unit/test_web_execution.py tests/unit/test_web_storage.py tests/integration/test_web_api.py tests/integration/test_cli.py -q` | PASS: 52 passed |
| `uv run pytest tests/unit tests/integration -q` | PASS: 274 passed |
| `uv run pytest tests/ -q --cov=src/loopflow --cov-report=term` | PASS: 320 passed, 1 skipped; coverage 81.00% |
| `python3 scripts/check-ac-manifest.py --profile recovery --allow-planned` | PASS: 32 scenarios |
| `npm test -- --run` | PASS: 9 passed |
| `npm run typecheck` | PASS |
| `npm run build` | PASS |
| `npm run test:browser` | PASS: 10 passed, 2 skipped |
| `./scripts/mr-gate.sh` | PASS |

# Notes

- `stop` no longer returns legacy `stopped` for new runs; `stopped` remains a readable legacy terminal status.
- `waiting_input` request close is intentionally a compatibility hook for existing `interventions/*.json` pending files. AC-022 request/response creation, validation and replay remain planned.
- Full strict recovery manifest still fails until AC-022 replaces its planned nodes; this is expected in DEVELOP and covered by `--allow-planned`.
