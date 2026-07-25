---
title: stale 失联宽限期 Report
description: run.json stale_since 首次判定原子写入不刷新、默认 24h 宽限内 reconcile 返回 409 run_in_grace、期满后按 BR-032 转 failed、worker 终态写优先并清除 stale_since、UI 失联（宽限中）呈现的实现与 AC-029 验收留档
type: report
status: done
created: 2026-07-25T07:25:00Z
---

# Summary

按 ADR-0046 / BR-052 完成 stale 失联宽限期：读模型 `read_summary` 首次判定 stale 时把 `stale_since` 原子写入 run.json（复用 BR-031 机制，写入前重读校验收窄与 worker 终态写的竞态），只写一次不刷新；宽限期默认 24h（`STALE_GRACE_SECONDS` 常量，不可配置），宽限期内显式 reconcile 返回 409 `run_in_grace` 且 run.json 不修改，期满后按 BR-032 既有流程转 failed 并清除 `stale_since`；worker 恢复写终态以 worker 为准并清除 `stale_since`（execution.py 与 cli.py 两条终态路径）；读模型投影透出 `stale_since` 与 `stale_grace_remaining_seconds`，WebUI 宽限期内 stale 在列表行与详情呈现「Unreachable (grace period) · 剩余时间」（非警报化，muted 样式）。AC-029 全部 7 场景自动化通过并登记 recovery manifest 真实节点（strict 全绿，69 scenarios）。

# Changes

| 层 | 内容 |
|----|------|
| `src/loopflow/infrastructure/web_storage.py` | `STALE_GRACE_SECONDS = 24 * 60 * 60` 常量；`stale_grace_remaining()`（缺失/不可解析返回 None，期满钳到 0）；`read_summary` 首次判定 stale 时经 `_record_stale_since` 原子写入（重读校验：仍 running、无 stale_since、pid/process_started_at/execution_epoch 一致才写；他读已写入则返回既有值；worker 已写终态则放弃）；summary 投影补 `stale_since` / `stale_grace_remaining_seconds`（unreadable 形态同补 None）；`reconcile` 无 stale_since 按首次判定先记账再抛 `ValueError("run_in_grace")`，宽限内（含不可解析，fail-safe 不误杀）抛 `run_in_grace` 不改文件，期满后转 failed 并 `pop("stale_since")` |
| `src/loopflow/application/web.py` | `reconcile` 捕获 `run_in_grace` → `ApplicationError("run_in_grace")`；非 stale 仍 `run_not_stale`（不变） |
| `src/loopflow/presentation/web/server.py` | `ERROR_STATUS` 新增 `"run_in_grace": 409` |
| `src/loopflow/application/execution.py` | worker 终态写入路径 `pop("stale_since")`（recover 路径 `update(previous)` 可能带入，显式清除） |
| `src/loopflow/presentation/cli.py` | `_finish_run` 同样 `pop("stale_since")`（手动 run 终态路径） |
| `web/src/types.ts` / `App.tsx` / `styles.css` | RunSummary 补 `stale_since` / `stale_grace_remaining_seconds`；`graceLabel()` 在 run 列表行与详情 toolbar 呈现「Unreachable (grace period) · Xh Ym left」（`.row-grace` muted 样式，非警报化） |
| `tests/unit/test_stale_grace.py`（新） | AC-029-N-1（首次写入 + 投影透出）/ N-2（execute_workflow recover 终态路径清除 stale_since）/ E-1（两次读取不刷新）/ E-2（legacy run 按首次判定） |
| `tests/integration/test_web_api.py` | AC-029-B-1（宽限内 409 run_in_grace 且 run.json 字节不变）/ B-2（期满 200 转 failed、清 pid 与 stale_since）/ F-1（存活进程 409 run_not_stale）；生命周期回归用例的 stale fixture 补过期 stale_since |
| `tests/web_support/factories.py` | `create_run` 支持 `stale_since` 参数 |
| `tests/unit/test_web_storage.py` / `test_web_application.py` | 三处编码旧契约的既有测试对齐新语义（旧语义被 AC-029 显式取代，见 Notes） |
| `tests/recovery_support/manifest.py` + `tests/system/recovery_cases.json` | AC-029 七场景登记真实 test_node，`--write` 重新生成 |

# AC-029 验收（逐场景）

| 场景 | 测试 | 结果 |
|------|------|------|
| AC-029-N-1 | tests/unit/test_stale_grace.py::TestStaleGracePeriod::test_ac029_n1_first_stale_detection_writes_stale_since | [PASS] |
| AC-029-N-2 | ...::test_ac029_n2_worker_terminal_write_clears_stale_since | [PASS] |
| AC-029-B-1 | tests/integration/test_web_api.py::test_ac029_b1_reconcile_within_grace_returns_run_in_grace | [PASS] |
| AC-029-B-2 | ...::test_ac029_b2_reconcile_after_grace_fails_run_and_clears_stale_since | [PASS] |
| AC-029-E-1 | ...::test_ac029_e1_stale_since_is_not_refreshed | [PASS] |
| AC-029-E-2 | ...::test_ac029_e2_legacy_run_records_stale_since_on_first_detection | [PASS] |
| AC-029-F-1 | ...::test_ac029_f1_reconcile_live_run_returns_run_not_stale | [PASS] |

TDD 留痕：测试先行 commit `55d7957` 时 `tests/unit/test_stale_grace.py` 因 `STALE_GRACE_SECONDS` 不存在 collection 失败（红），B-1（期望 409 实得 200）、B-2（stale_since 未清除）与两处对齐新语义的旧测试失败；实现 commit `ddb1d5a` 后全绿。

# Commits

| commit | 内容 |
|--------|------|
| `f3230c7` | docs(plan): 0085 stale 宽限期容器（develop） |
| `55d7957` | test(run): AC-029 stale 宽限期场景（TDD） |
| `ddb1d5a` | feat(run): AC-029 stale 失联宽限期 |
| `5509771` | feat(web): AC-029 stale 宽限期呈现 |
| `818d979` | test(infra): AC-029 manifest 真实节点 |

# Verification Results

| 层 | 结果 |
|----|------|
| 全量 `uv run pytest tests/ -q` | 492 passed, 1 skipped（含本容器新增 8 条测试，零回归） |
| `check-ac-manifest.py --profile recovery`（strict） | AC manifest ok: 69 scenarios（AC-029 全部转 real，无 planned） |
| `check-ac-manifest.py --profile recovery --allow-planned` | AC manifest ok: 69 scenarios |
| `check-ac-manifest.py --profile scheduling`（strict） | 仍剩 AC-010-N-2/E-2 两个 planned（BL-010 遗留，符合现状预期） |
| `check-ac-manifest.py --profile scheduling --allow-planned` | AC manifest ok: 32 scenarios |
| `check-ac-manifest.py --profile web --allow-planned` | AC manifest ok: 80 scenarios |
| 前端 `npm run test:coverage` | 39 passed（含 stale 宽限呈现用例）；覆盖率 Stmts 98.19% / Branch 85.59% |
| 前端 `npm run build` | 通过（chunk 大小警告为既有提示） |
| mr-gate npm audit | **跳过：既有失败**（audit endpoint 400 / 链问题，0081–0084 Report 已记录，package-lock.json 本容器零改动） |

# Notes

- **stale_since 写入点并发安全性**：读路径（`read_summary` → `_record_stale_since`）基于读到的 metadata 判定 stale 后，写入前重读 run.json，仅在「仍为 running、尚无 stale_since、pid/process_started_at/execution_epoch 与判定依据一致」时才原子写——worker 已写终态则 status 非 running，放弃写入，以 worker 为准；另一读者先写则返回既有值（不刷新，AC-029-E-1）。worker 侧终态写走 epoch+status 乐观锁（仅 current.status == running 且 epoch 一致才写）并显式 `pop("stale_since")`，两条终态路径（execution.py / cli.py `_finish_run`）都接线。**残余 TOCTOU**：重读校验与原子写之间仍有微秒级窗口（读路径理论上可覆盖 worker 刚写的终态）；本地单用户场景下二者极少并发，且下一轮读取以文件为准自愈，ADR-0046 接受该形态（复用 BR-031 原子写，不引入新锁）。
- **reconcile 首次判定语义**：reconcile 时无 stale_since（从未被读过）按首次判定处理——先记账、宽限期从此时起算、返回 409 `run_in_grace`（ADR-0046 §2「失联先记账，给一段宽限期再宣判」的直接推论）；stale_since 不可解析时 fail-safe 按宽限内处理（不误杀存活可能）。
- **旧契约测试对齐**：`test_stale_is_derived_without_modifying_run_json`（断言读取不改文件）等三处既有测试编码的是 BR-032 原语义，AC-029-N-1/E-2 显式取代（读模型首次 stale 写 stale_since），已对齐为新语义的回归测试。
- **UI 文案语言**：ADR-0046 §4 的「失联（宽限中）」在 UI 呈现为英文 `Unreachable (grace period) · Xh Ym left`——WebUI 既有文案全英文，属呈现层语言惯例，语义（非警报化 + 剩余时间）与 ADR 一致，非契约偏差。
- **宽限期常量**：24h 硬编码 `STALE_GRACE_SECONDS`，不做可配置入口（ADR-0046 §2 / Plan Constraints）；测试用 fixtures 的 stale_since 偏移构造时间窗口，未引入生产代码时钟注入。
- uv.lock 的既有未提交修改未触碰、未提交。

# Exit

全部 Acceptance 通过，合回 develop（--no-ff），分支删除，不 push。
