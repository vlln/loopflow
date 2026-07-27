---
title: 队列任务显式状态 Report
description: 队列条目 status/status_reason/superseded_by 状态机、enqueue --supersede、dispatch deferred/superseded 两桶、Web 投影透传的实现与 AC-028 验收留档
type: report
status: done
created: 2026-07-25T05:55:00Z
---

# Summary

按 ADR-0047 / BR-053 完成队列任务显式状态：队列条目 schema 增加 `status`（pending/deferred/superseded，默认 pending）、`status_reason`、`superseded_by`，缺失或未知 status 按 pending 处理（向后兼容）；`enqueue --supersede` 显式取代同 loop 的 pending/deferred 任务；dispatch 资源锁失败标记 deferred 留队（BR-019 语义不变仅显式化）、superseded 任务跳过并清理，summary 增加 deferred/superseded 两桶且均不计 errors；Web `QueueRepository` 投影透传三字段并同步接口契约。AC-028 全部 7 场景自动化通过并登记 manifest 真实节点（scheduling profile real 14→21 / planned 18→11）。

# Changes

| 层 | 内容 |
|----|------|
| `src/loopflow/infrastructure/queue.py` | `VALID_STATUSES`；`effective_status()`（缺失/未知回退 pending）；`mark_status()`（原地写状态保留其他字段）；`enqueue(..., supersede=False)`（新任务 uuid 先生成，同 loop pending/deferred 标记 superseded + superseded_by + status_reason）；新条目写入 `status: "pending"` |
| `src/loopflow/infrastructure/dispatch.py` | superseded 任务跳过 + 删文件计 superseded 桶；资源锁失败 `mark_status(deferred, reason=锁异常消息)` 留队计 deferred 桶；summary 增加 deferred/superseded，`skipped` 键保留（恒 0，兼容既有消费方） |
| `src/loopflow/presentation/cli.py` | `enqueue --supersede` 标志；dispatch 输出改报 processed/deferred/superseded/errors |
| `src/loopflow/infrastructure/web_resources.py` | `_project` 透传 status（复用 `effective_status` 回退）/status_reason/superseded_by；Web enqueue 写入 `status: "pending"` |
| `tests/web_support/contracts.py` | QUEUE_ITEM_SCHEMA 增加三字段（status enum、reason/superseded_by nullable）+ 示例同步 |
| `docs/interface/0001-web-api.md` | GET /queue item 字段表同步 |
| `tests/e2e/test_scheduling_e2e.py` | 新增 `TestQueueTaskStatus` 七场景；AC-012-B-1 断言由 skipped 桶改 deferred 桶（语义不变，见 Notes 偏差 2） |
| `tests/unit/test_queue.py` | `TestQueueStatus` 8 条状态机单测（默认 pending、effective_status 回退、mark_status 往返、supersede 各分支含未知 status 视为 pending） |
| `tests/unit/test_web_resources.py` | 投影透传单测（deferred/superseded/未知回退） |
| `tests/scheduling_support/manifest.py` + `tests/system/scheduling_cases.json` | AC-028 七场景登记真实 test_node，`--write` 重新生成 |
| `tests/infrastructure/test_scheduling_manifest.py` | 自证计数 14/18 → 21/11 |

# AC-028 验收（逐场景）

| 场景 | 测试 | 结果 |
|------|------|------|
| AC-028-N-1 | tests/e2e/test_scheduling_e2e.py::TestQueueTaskStatus::test_enqueue_writes_pending_status | [PASS] |
| AC-028-N-2 | ...::test_dispatch_defers_task_when_resource_locked | [PASS] |
| AC-028-N-3 | ...::test_enqueue_supersede_marks_existing_task | [PASS] |
| AC-028-N-4 | ...::test_dispatch_skips_and_cleans_superseded | [PASS] |
| AC-028-B-1 | ...::test_enqueue_supersede_without_existing_task | [PASS] |
| AC-028-E-1 | ...::test_dispatch_treats_unknown_or_missing_status_as_pending | [PASS] |
| AC-028-F-1 | ...::test_dispatch_deferred_and_superseded_not_counted_as_errors | [PASS] |

TDD 留痕：测试先行 commit `171aeb3` 时 15 条相关测试全红（失败原因均为未实现），实现 commit `5c44687` 后全绿。

# Commits

| commit | 内容 |
|--------|------|
| `968b01c` | docs(plan): 0082 队列任务显式状态容器（develop） |
| `171aeb3` | test(queue): AC-028 场景与状态机测试（TDD 红） |
| `5c44687` | feat(queue): AC-028 队列任务显式状态 |
| `2c7effd` | docs(interface): queue item 增加状态字段 |
| `16ff888` | test(infra): AC-028 manifest 真实节点 |

# Verification Results

| 层 | 结果 |
|----|------|
| `uv run pytest tests/unit tests/e2e tests/infrastructure -q` | 390 passed, 1 skipped |
| `check-ac-manifest.py --profile scheduling`（strict） | AC-028 七场景全部通过；整体仍失败——剩余 11 个 planned（AC-027×9 属 0084、AC-010-N-2/E-2 为 0081 遗留 DESIGN 裁决项），按 Plan 预期用 `--allow-planned` |
| `check-ac-manifest.py --profile scheduling --allow-planned` | AC manifest ok: 32 scenarios |
| `check-ac-manifest.py --allow-planned`（web）/ `--profile recovery --allow-planned` | ok: 80 / 69 scenarios（不回归） |
| 全量 `uv run pytest tests/ -q` | 444 passed, 1 skipped（含本容器新增 16 条测试：e2e 7 + queue 单测 8 + 投影单测 1，零回归） |
| 覆盖率（`--cov=src/loopflow`） | TOTAL 82%（门禁 59%）；queue.py 89%、dispatch.py 80%、web_resources.py 89% |
| mr-gate npm audit | **跳过：既有失败**（brace-expansion 经 @vitest/coverage-v8 链，0081 Report 偏差 3 已记录，web/ 与 package-lock.json 本容器零改动） |

# Notes

- **契约偏差 1（ADR-0047 ↔ 现状：paused 衔接留 0084）**：ADR-0047 Consequences 提到"与 ADR-0045 衔接：paused loop 的队列任务经 dispatch 落入 deferred 桶"，但 loop_state/paused 生产代码尚不存在（AC-027 由 0084 熔断容器实现）。本容器 dispatch 的 deferred 只来源于资源锁失败；paused → deferred 衔接与 AC-027-N-4 留 0084，届时只需在 dispatch 锁检查前补 paused 判定并复用 `mark_status`。Plan Constraints 已预告。
- **契约偏差 2（AC-012-B-1 测试断言调整）**：资源锁失败从 skipped 桶改计 deferred 桶（ADR-0047 §4 桶显式化），AC-012-B-1 的 e2e 断言同步改为 `summary["deferred"] == 1`；留队语义、AC-012-F-1（失败任务移除不重试）均未变。`summary["skipped"]` 键保留恒 0，避免既有消费方 KeyError。
- **dispatch 输出变更**：CLI dispatch 摘要行由 "X processed, Y skipped, Z errors" 改为 "X processed, Y deferred, Z superseded, W errors"；无测试或脚本解析该行（已全仓 grep 确认）。
- **Web 投影契约**：QUEUE_ITEM_SCHEMA 为 `additionalProperties: False`，三字段为必出键（reason/superseded_by 可为 null），前端展示不在本容器范围；web/src 前端类型未动，TS 端不受影响（typecheck 未跑，属 mr-gate 前端段，本容器 web/ 零改动）。
- uv.lock 的既有未提交修改未触碰、未提交。

# Exit

全部 Acceptance 通过，合回 develop（--no-ff），分支删除，不 push。
