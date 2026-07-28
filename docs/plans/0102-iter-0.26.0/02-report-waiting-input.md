---
title: BL-044+045 waiting_input 生命周期 Report
description: intervene default/timeout、--unattended、CLI 内联应答、loopflow respond 实现完成，AC-031 全 11 场景通过
type: report
status: complete
created: 2026-07-28T11:50:00Z
---

# Report: BL-044+045 waiting_input 生命周期

## AC 验收结果

| AC | 结果 | 证据 |
|----|------|------|
| AC-031-N-1 | PASS | `tests/integration/test_cli.py::TestWaitingInput`（内联选择 → 同 run_id done、response_source=human） |
| AC-031-N-2 | PASS | 同上（`loopflow respond <run-id>` 交互应答恢复） |
| AC-031-N-3 | PASS | 同上（--unattended + default → response_source=default，不进 waiting_input） |
| AC-031-B-1 | PASS | `tests/unit/test_waiting_input.py`（created_at 过期 → 惰性 timeout_default） |
| AC-031-B-2 | PASS | 同上（倒计时到期取 default，patch select/时间） |
| AC-031-E-1 | PASS | 同上（default 未过校验 → ValueError，无 request） |
| AC-031-E-2 | PASS | 同上（timeout 无 default → ValueError） |
| AC-031-E-3 | PASS | CLI 集成（--unattended 无 default → failed intervention_unattended，无 request 文件） |
| AC-031-E-4 | PASS | CLI 集成（非 tty → 指引文本 + waiting_input 退出） |
| AC-031-F-1 | PASS | 单测（default/timeout 变更 → ReplayDiverged） |
| AC-031-F-2 | PASS | 单测（非法输入重问不落盘） |

测试：`uv run pytest tests/unit tests/integration -q` 454 passed（443 基线 + 11 新增，无回归）；`check-ac-manifest.py --profile recovery` 严格模式 AC-031 ×11 全部真实节点通过（仅剩改动前就存在的 AC-026 ×4 planned，见下文）；`tests/unit/test_web_application.py` 41 tests 零回归（web.py 改为单行委托 `application/respond.py::respond_and_recover`）。commit `a43bfde`（runtime/intervention）、`9790b5c`（cli/respond）。

## 与 Plan 的偏差（实现者记录，经确认合理）

1. 新单测集中于 `tests/unit/test_waiting_input.py`（6 个）而非散入 test_runtime；N-3/E-3 按 manifest 冻结的 `process:cli-run` 改为 CLI 集成测试。
2. unattended 以显式 keyword 参数传入 `request_or_answer`（runtime/runner 两个调用侧），避免 infrastructure 反向依赖 runtime context。
3. agent 结构化请求在 unattended 下同样以 intervention_unattended 失败（ADR-0056 §5：agent 侧本期无 default/timeout，unattended 遇之只能失败，语义自洽）。
4. CLI 内联恢复走 BackgroundRunExecutor 子进程 + 轮询 run.json，与 Web recover 完全同构。

## 遗留（非本轮引入）

- AC-026-E-2/N-5/B-3/E-3（BL-031 追加场景）在 recovery manifest 中为 planned::，SYSTEM_TEST 严格模式会拦截，需在 SYSTEM_TEST 前补测或处置（同 BL-048 一类）。
