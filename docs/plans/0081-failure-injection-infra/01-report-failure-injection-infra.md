---
title: 失败注入测试基础设施 Report
description: SessionBackendFake 脚本化失败注入、结构化 error_category 通道、stale/loop_state/queue fixtures 与基建自证结果留档
type: report
status: done
created: 2026-07-25T05:10:00Z
---

# Summary

按 ADR-0048 完成 0.21.0 失败注入测试基建：`SessionBackendFake` 支持 per-attempt 脚本化结果（exit_code/stderr/error_category/behavior），可表达"transient 失败 2 次后成功"等序列且向后兼容；`agent_done_payload()` + 测试侧参考实现 `resolve_error_category()` 固化 ADR-0044 的结构化优先/stderr 兜底分类语义；run.json（stale_since 相对偏移、error_category）、loop_state、队列状态三类 fixture 工厂落地。生产代码（src/）零改动。13 条基建自证全部通过，既有测试零回归。

# Changes

| 层 | 内容 |
|----|------|
| `tests/recovery_support/fakes.py` | `AttemptResult` 值对象；`SessionBackendFake` 增加 `create_script`/`resume_script`（每次调用 pop 一项，耗尽回退固定字段）与 `results` 记录；`agent_done_payload()` 产出 ADR-0044 契约 payload（未上报时省略 error_category 键） |
| `tests/recovery_support/failure.py`（新） | `resolve_error_category()`：结构化上报优先 → stderr 模式兜底 → unknown；`TRANSIENT_PATTERNS` 为生产 runner 模式表拷贝（见 Notes 偏差 2） |
| `tests/recovery_support/fixtures.py` | `run_metadata()`/`RunFactory`（stale_since 秒偏移直接构造持久化时间戳，None 时不写键 = legacy 形态）；`LoopStateFactory`（consecutive_failures/paused/paused_reason/paused_at/last_run_id）；`QueueEntryFactory`（status/status_reason/superseded_by，默认 pending）；复用原子写 |
| `tests/recovery_support/__init__.py` | 导出新符号 |
| `tests/infrastructure/test_failure_injection_support.py`（新） | 13 条自证 |

# Self-Test Results（tests/infrastructure/test_failure_injection_support.py）

| 自证项 | 测试 | 结果 |
|--------|------|------|
| 脚本序列消费 + 耗尽回退 | test_scripted_attempts_consumed_in_order_then_fall_back_to_fixed_fields | [PASS] |
| transient 失败 2 次后成功序列 | test_scripted_transient_failures_then_success_sequence | [PASS] |
| 四类失败（auth/quota/transient/task）上报 | test_agent_done_payload_reports_all_four_failure_categories | [PASS] |
| 结构化-vs-stderr 冲突优先级 | test_structured_category_wins_over_conflicting_stderr | [PASS] |
| 未上报兜底 unknown + 非法类别拒绝 | test_unreported_and_unmatched_failure_resolves_to_unknown | [PASS] |
| 脚本 behavior 覆盖固定 behavior | test_script_behavior_overrides_fixed_behavior_per_attempt | [PASS] |
| resume/create 脚本独立 | test_resume_script_is_independent_of_create_script | [PASS] |
| stale_since 相对偏移工厂 | test_run_factory_stale_since_relative_offset | [PASS] |
| run.json error_category 携带 | test_run_metadata_carries_error_category_when_failed | [PASS] |
| loop_state fixture 往返 | test_loop_state_factory_roundtrip | [PASS] |
| queue fixture 状态往返 | test_queue_entry_factory_status_roundtrip | [PASS] |
| 模式表漂移守卫 | test_transient_patterns_copy_matches_production_runner | [PASS] |
| 既有 fake 行为回归 | test_existing_fake_behavior_regression | [PASS] |

# Verification Results

| 层 | 结果 |
|----|------|
| `uv run pytest tests/unit/ tests/infrastructure/ -v` | 356 passed, 1 skipped（343 → 356，零回归） |
| `check-ac-manifest.py --allow-planned` | AC manifest ok: 80 scenarios |
| `check-ac-manifest.py --profile recovery --allow-planned` | AC manifest ok: 69 scenarios |
| mr-gate：Python 全量 + 覆盖率 | 423 passed, 1 skipped；覆盖率 81.96%（门禁 59%） |
| mr-gate：双 profile manifest | 均 ok |
| mr-gate：前端 typecheck / vitest / build | clean / 36 passed / 成功 |
| mr-gate：npm audit | **失败（既有问题，见 Notes 偏差 3）** |
| mr-gate：Playwright 浏览器测试 | 10 passed, 2 skipped（单独补跑） |
| mr-gate：wheel-smoke | wheel assets ok: index.html + 2 hashed assets（单独补跑） |

# Notes

- **契约偏差 1（AC-027/028 未登记 manifest）**：30 个 AC 场景中只有 AC-026（7）与 AC-029（7）以 `planned::` 登记在 tests/system/recovery_cases.json；AC-027（9）与 AC-028（7）在 docs/ac/0004-scheduling.md，而 check-ac-manifest 的 web/recovery 两个 profile 分别只覆盖 0010/0011，0004 无 profile 承接。DEVELOP 实现 AC-027/028 前需为其补 manifest profile 或扩展既有 profile，否则这 16 个场景无 manifest 门禁保护。本容器未改动 manifest（TEST_INFRA 不背 AC 场景实现）。
- **契约偏差 2（模式表拷贝而非复用）**：`failure.py` 理想上应复用生产 `_TRANSIENT_PATTERNS`，但 `tests/recovery_support/__init__.py` 会被 `scripts/check-ac-manifest.py` 以裸 python3 导入（无 loopflow 包可导入），模块级导入生产代码会炸 manifest 门禁。改为拷贝 + 漂移守卫自证（test_transient_patterns_copy_matches_production_runner）。DEVELOP 扩充 `_TRANSIENT_PATTERNS` 时守卫会失败提示同步。
- **契约偏差 3（mr-gate npm audit 既有失败）**：`npm audit --audit-level=low` 报 5 high（brace-expansion 经 @vitest/coverage-v8 链），与本次改动无关（web/ 与 package-lock.json 零改动，develop 上同样失败）。门禁在 audit 处中断，其后的浏览器测试与 wheel-smoke 单独补跑（结果见上表）。
- 注入 seam 说明：fake 经 `loopflow.runtime._make_backend` patch 注入（与 tests/unit/test_runtime.py 同模式），本次未验证端到端注入路径——DEVELOP 业务测试首次使用时若发现 seam 缺口，回本容器扩展。
- 未发现必须依赖的生产代码改动；Plan Constraints 无遗留业务改动事项。

# 补记（2026-07-25）：scheduling profile 落地，偏差 1 关闭

新增第三个 manifest profile `scheduling` 承接 docs/ac/0004-scheduling.md 全部 32 个场景，偏差 1 关闭：

- `tests/scheduling_support/manifest.py`（新 profile 模块）+ `tests/system/scheduling_cases.json`（32 cases）；`scripts/check-ac-manifest.py` 重构为 PROFILES 表（web/recovery/scheduling）
- **登记统计：real 14 / planned 18**。real 节点来自既有测试（test_discovery/test_queue/test_dispatch/test_resource_lock/test_cli/test_scheduling_e2e，已逐条实证存在且通过）；planned 18 = AC-027（9）+ AC-028（7）待 DEVELOP + AC-010-N-2/E-2（见下）
- **新发现契约冲突**：AC-010-N-2/E-2 的 AC 文本期望 loop.md 缺失/损坏时 fallback 到 workflow.py meta，但 ADR-0031 后现行行为是 loop.md 强制、缺失即跳过（`test_no_loop_md_not_discoverable`、`test_loop_md_bad_yaml` 均断言跳过）。两者矛盾，不猜测映射，登记 `planned::` 占位，留 DESIGN 裁决（改 AC 文本或恢复 fallback）
- `scripts/mr-gate.sh` 接入：与 recovery 相同的阶段门槛——allow-planned 分支（INIT/DESIGN/TEST_INFRA/DEVELOP）与 strict 分支各加一行 `--profile scheduling`
- CONTRIBUTING.md 测试命令表补两行 scheduling 检查命令
- 验证：`--profile scheduling --allow-planned` ok（32 scenarios），strict 模式正确拒绝 18 个 planned；web（80）/recovery（69）不回归；`tests/infrastructure/` 56 passed（含新增 test_scheduling_manifest.py 5 条自证）
- commits：`4e03fad`（profile 代码）、`fa7052f`（CONTRIBUTING）
