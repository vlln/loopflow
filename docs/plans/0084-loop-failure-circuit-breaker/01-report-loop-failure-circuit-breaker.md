---
title: Loop 失败熔断与 loop_state Report
description: per-loop loop_state 存储、连续失败达阈值自动熔断 paused、dispatch deferred 留队、手动 unpause（CLI/Web）与 UI 失败/熔断呈现的实现与 AC-027 验收留档
type: report
status: done
created: 2026-07-25T07:00:00Z
---

# Summary

按 ADR-0045 / BR-050 / BR-051 完成 Loop 失败熔断：新增 `infrastructure/loop_state.py`（`~/.loopflow/loop_state/<loop>.json`，损坏/缺失按初始状态不抛错）；run 进入 failed 终态时该 loop `consecutive_failures`+1 并记 `last_run_id`，done 归零（手动 `loopflow run` 与 dispatch 触发都计入，两条终态收尾路径都接线）；达阈值（默认 5，loop.md frontmatter `failure_threshold` 可覆盖，非法值按默认）置 `paused=true` + `paused_reason=failure_streak:<n>` + `paused_at`；paused 的 loop 其队列任务在 dispatch 中 mark deferred 留队（status_reason 含暂停原因），计 deferred 桶不计 errors；手动 run 不拦截；解除仅手动——CLI `loopflow unpause <name>` 与 Web `POST /api/v1/loops/{name}/unpause`（404 loop 不存在），清除 paused 与 streak。UI 补齐：Loops 工作区 paused 徽标 + 原因 + unpause 操作 + streak 计数聚合，Run 列表/详情渲染 `error_summary` 与 `error_category`（读模型投影同步补齐）。AC-027 全部 9 场景自动化通过并登记 manifest 真实节点（scheduling profile strict 只剩 AC-010-N-2/E-2 两个 BL-010 遗留 planned）。

# Changes

| 层 | 内容 |
|----|------|
| `src/loopflow/infrastructure/loop_state.py`（新） | `load`（损坏/缺失回退初始状态）、`record_failure`（+1、记 last_run_id、达阈值置 paused）、`record_success`（归零 streak、不动 paused）、`unpause`（清除 paused 与 streak）、`failure_threshold`（frontmatter 覆盖，非法值回退默认 5）；目录遵循 `LOOPFLOW_HOME`（同 queue.py），原子写复用 `atomic_write_json` |
| `src/loopflow/application/execution.py` | run 终态收尾：failed → `record_failure`（阈值取 loop.md meta），done → `record_success`（Web/executor 路径） |
| `src/loopflow/presentation/cli.py` | `run` 命令失败/成功终态同样计数（手动与 dispatch 子进程都走此路径）；新增 `loopflow unpause <name>` 命令（经 WebApplication.unpause_loop） |
| `src/loopflow/infrastructure/dispatch.py` | 消费前检查 paused → `mark_status(path, "deferred", reason="loop paused: <原因>")` 留队计 deferred |
| `src/loopflow/application/web.py` | `unpause_loop(name)`：loop 不存在 → `loop_not_found`；否则清除并返回 Loop 详情 |
| `src/loopflow/presentation/web/server.py` | `POST /api/v1/loops/{name}/unpause` 路由 |
| `src/loopflow/infrastructure/web_resources.py` | Loop summary/detail 投影 `consecutive_failures` / `paused` / `paused_reason` |
| `src/loopflow/infrastructure/web_storage.py` | Run summary 投影补 `error_category`（0083 落 run.json，读模型补齐） |
| `web/src/types.ts` / `api.ts` | RunSummary.error_category、Loop paused/streak 字段；`api.unpauseLoop` |
| `web/src/App.tsx` / `styles.css` | Run 列表行与详情横幅渲染 `[category] error_summary`；Loops 列表 streak 计数 + paused 徽标；Loop 详情 paused 徽标 + 原因 + Unpause 操作 |
| `tests/unit/test_loop_state.py`（新） | loop_state 单测 8 条（初始读/损坏回退/计数/归零/默认阈值/frontmatter 覆盖/非法值回退/unpause）+ AC-027-N-1/N-2/N-3/B-1/F-1（execute_workflow 真实终态路径）+ unpause CLI 2 条（含 AC-027-B-2 dispatch 恢复） |
| `tests/e2e/test_scheduling_e2e.py` | `TestLoopCircuitBreaker`：AC-027-N-4（paused deferred 留队）、E-1（损坏回退 dispatch 正常）、B-3（手动 run 不拦截） |
| `tests/unit/test_web_application.py` | unpause_loop 成功/404、Loop 投影、Run error_category 投影 |
| `tests/integration/test_web_api.py` | `POST /loops/{name}/unpause` 路由 200/404 |
| `web/src/App.test.tsx` + `test/fixtures.ts` | error_summary/category 渲染、paused 徽标 + unpause 操作两个用例 |
| `tests/scheduling_support/manifest.py` + `tests/system/scheduling_cases.json` | AC-027 九场景登记真实 test_node，`--write` 重新生成 |
| `docs/spec/0001-loopflow.md` | UI 约束新增「失败与熔断呈现」小节（DESIGN 遗漏补充，方向已经用户批准） |

# AC-027 验收（逐场景）

| 场景 | 测试 | 结果 |
|------|------|------|
| AC-027-N-1 | tests/unit/test_loop_state.py::TestCircuitBreakerScenarios::test_ac027_n1_failed_run_increments_streak | [PASS] |
| AC-027-N-2 | ...::test_ac027_n2_done_run_resets_streak | [PASS] |
| AC-027-N-3 | ...::test_ac027_n3_five_failures_pause_loop | [PASS] |
| AC-027-N-4 | tests/e2e/test_scheduling_e2e.py::TestLoopCircuitBreaker::test_ac027_n4_paused_loop_task_deferred_not_error | [PASS] |
| AC-027-B-1 | tests/unit/test_loop_state.py::TestCircuitBreakerScenarios::test_ac027_b1_threshold_frontmatter_override | [PASS] |
| AC-027-B-2 | tests/unit/test_loop_state.py::TestUnpauseCli::test_ac027_b2_unpause_clears_and_dispatch_resumes | [PASS] |
| AC-027-B-3 | tests/e2e/test_scheduling_e2e.py::TestLoopCircuitBreaker::test_ac027_b3_manual_run_not_blocked_by_pause | [PASS] |
| AC-027-E-1 | tests/e2e/test_scheduling_e2e.py::TestLoopCircuitBreaker::test_ac027_e1_corrupted_loop_state_treated_as_initial | [PASS] |
| AC-027-F-1 | tests/unit/test_loop_state.py::TestCircuitBreakerScenarios::test_ac027_f1_manual_run_failure_counts | [PASS] |

TDD 留痕：测试先行 commit `af3d713` 时 `tests/unit/test_loop_state.py` 因模块不存在 collection 失败（红），实现 commit `f393dff` 后全绿。

# Commits

| commit | 内容 |
|--------|------|
| `4102c6a` | docs(spec): UI 约束补失败与熔断呈现（develop） |
| `cf29b2a` | docs(plan): 0084 失败熔断容器（develop） |
| `af3d713` | test(loop): AC-027 失败熔断场景（TDD） |
| `f393dff` | feat(loop): AC-027 失败熔断与 unpause |
| `0cb4cf7` | feat(web): AC-027 失败与熔断呈现 |
| `a02b69c` | test(infra): AC-027 manifest 真实节点 |

# Verification Results

| 层 | 结果 |
|----|------|
| 全量 `uv run pytest tests/ -q` | 485 passed, 1 skipped（含本容器新增 23 条测试，零回归） |
| `check-ac-manifest.py --profile scheduling --allow-planned` | AC manifest ok: 32 scenarios（strict 只剩 AC-010-N-2/E-2 两个 planned，BL-010 遗留，符合 Plan 预期） |
| `check-ac-manifest.py --profile recovery --allow-planned` | AC manifest ok: 69 scenarios |
| `check-ac-manifest.py --profile web --allow-planned` | AC manifest ok: 80 scenarios |
| 前端 `npm run test:coverage` | 38 passed；覆盖率 Stmts 98.18% / Branch 85.54% |
| 前端 `npm run build` | 通过（chunk 大小警告为既有提示） |
| mr-gate npm audit | **跳过：既有失败**（brace-expansion 经 @vitest/coverage-v8 链，0081/0082/0083 Report 已记录，package-lock.json 本容器零改动） |

# Notes

- **计数落点双路径**：dispatch 触发的 run 经 `loop run` 子进程走 `presentation/cli.py` run 命令的内联执行路径，Web/executor 触发走 `application/execution.py`；两条终态收尾路径都接线计数，保证手动与 dispatch 失败都计入（AC-027-F-1），且同一 run 不会双计（一个 run 只走其中一条路径）。
- **done 不自动解除 paused**（ADR-0045 §4）：`record_success` 归零 streak 但保留 paused；paused 时手动 run 成功（AC-027-B-3）后 dispatch 仍 defer，直到显式 unpause。
- **目录解析**：loop_state 目录与 queue 同规则（`LOOPFLOW_HOME` → `<home>/loop_state`，否则 `~/.loopflow/loop_state`），测试隔离沿用既有 env 约定。
- **已 paused 后再次失败**：streak 继续累加但 `paused_reason`/`paused_at` 保持首次熔断值（AC 未规定更新语义，保留首次熔断事实）。
- **unpause 命名**：CLI `loopflow unpause <name>` / Web `POST /api/v1/loops/{name}/unpause`，Plan Constraints 冻结；CLI 复用 WebApplication 服务层（同 recover/stop 模式）。
- **Spec 补充**：「失败与熔断呈现」小节（error_summary/category 呈现、streak 聚合、paused 徽标）为 DESIGN 遗漏补充，方向已经用户批准，已在 Plan 注明；Web API 边界「暂停解除 / 恢复 Loop」行 Spec 既有，无需新增。
- uv.lock 的既有未提交修改未触碰、未提交。

# Exit

全部 Acceptance 通过，合回 develop（--no-ff），分支删除，不 push。
