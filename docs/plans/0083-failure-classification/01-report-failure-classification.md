---
title: Agent 失败分类与重试/续接策略 Report
description: 失败五分类（auth/quota/transient/task/unknown）、结构化上报优先/stderr 兜底、transient 既有退避不变、agent_done/run.json 携带 error_category 的实现与 AC-026 验收留档
type: report
status: done
created: 2026-07-25T06:30:00Z
---

# Summary

按 ADR-0044 / BR-049 完成 Agent 失败分类与重试/续接策略：失败统一分类为 auth/quota/transient/task/unknown 五类，来源优先级为后端结构化上报（agent_done payload `error_category`）> stderr 模式匹配兜底 > unknown；transient 保持既有 3/9/27s 退避重试（最多 3 次）行为完全不变，auth/quota/task/unknown 不自动重试直接失败；manager 异常分支不再纯吞（连接/超时类 → transient，其余 → unknown）；`AgentError` 携带 `category`；run.json 失败路径写 `error_category`。AC-026 全部 7 场景自动化通过并登记 manifest 真实节点（recovery profile AC-026 七场景 planned → real）。

# Changes

| 层 | 内容 |
|----|------|
| `src/loopflow/domain/agent_def.py` | `ERROR_CATEGORIES` 五分类常量；`AgentError(message, category=None)` 增加 `category` 字段（仅携带不做决策） |
| `src/loopflow/application/runner.py` | `_AUTH_QUOTA_PATTERNS`（401/unauthorized/invalid api key/authentication failed → auth；insufficient_quota/quota exceeded/quota → quota，先于 transient 匹配）；`_classify_error(reported, stderr)`（结构化优先 > auth/quota > 既有 `_TRANSIENT_PATTERNS` > unknown）；`_extract_error_category`；重试循环改按分类决策（仅 transient 退避重试）；失败时 `ctx.failed_error_category` 落上下文、AgentError 携带 category |
| `src/loopflow/infrastructure/backends/manager.py` | agent_done payload 在后端实例上报合法 `error_category` 时原样携带（尽力而为通道）；异常分支映射 ConnectionError/TimeoutError → transient、其余 → unknown 并写入 payload |
| `src/loopflow/infrastructure/context.py` | RunContext 增加 `failed_error_category` |
| `src/loopflow/application/execution.py` | run.json 失败路径写 `error_category`（与 error_summary 并列），done 时清理 |
| `tests/recovery_support/fakes.py` | SessionBackendFake 增加 `close()`、`error_category` property（最近一次调用分类）、`_transport` property（stderr_text 契约桩），供 manager 真实链路消费 |
| `tests/unit/test_failure_classification.py` | 新增：`_classify_error` 单测 8 条（五类/冲突优先级/非法上报回退/模式表边界）+ AC-026 六场景 + manager 异常映射 3 条 |
| `tests/unit/test_web_application.py` | AC-026-F-1：quota 失败 run 的 recover continue 边界不变 |
| `tests/recovery_support/manifest.py` + `tests/system/recovery_cases.json` | AC-026 七场景登记真实 test_node，`--write` 重新生成 |

# AC-026 验收（逐场景）

| 场景 | 测试 | 结果 |
|------|------|------|
| AC-026-N-1 | tests/unit/test_failure_classification.py::TestFailureClassificationScenarios::test_ac026_n1_transient_retries_then_succeeds | [PASS] |
| AC-026-N-2 | ...::test_ac026_n2_structured_quota_beats_transient_stderr | [PASS] |
| AC-026-N-3 | ...::test_ac026_n3_run_json_matches_agent_done_category | [PASS] |
| AC-026-B-1 | ...::test_ac026_b1_auth_failure_fails_without_retry | [PASS] |
| AC-026-B-2 | ...::test_ac026_b2_unmatched_failure_is_unknown_no_retry | [PASS] |
| AC-026-E-1 | ...::test_ac026_e1_transient_exhausts_backoff_then_fails | [PASS] |
| AC-026-F-1 | tests/unit/test_web_application.py::test_quota_failure_recover_continue_keeps_existing_boundaries | [PASS] |

TDD 留痕：测试先行 commit `b651522` 时 16 条新测试红（失败原因均为未实现；N-1 与 F-1 为既有行为验证先行转绿，属预期），实现 commit `6975fa0` 后全绿。

# Commits

| commit | 内容 |
|--------|------|
| `9e61ae3` | docs(plan): 0083 失败分类容器（develop） |
| `b651522` | test(agent): AC-026 失败分类场景（TDD） |
| `6975fa0` | feat(agent): AC-026 失败分类与重试策略 |
| `bf590c6` | test(infra): AC-026 manifest 真实节点 |

# Verification Results

| 层 | 结果 |
|----|------|
| 全量 `uv run pytest tests/ -q` | 462 passed, 1 skipped（含本容器新增 18 条测试，零回归） |
| `check-ac-manifest.py --profile recovery --allow-planned` | AC manifest ok: 69 scenarios（strict 仍失败：AC-029 七场景 planned 属 0085，按 Plan 预期） |
| `check-ac-manifest.py --profile scheduling --allow-planned` | AC manifest ok: 32 scenarios（AC-027 仍 planned 属 0084，不回归） |
| mr-gate npm audit | **跳过：既有失败**（brace-expansion 经 @vitest/coverage-v8 链，0081/0082 Report 已记录，web/ 与 package-lock.json 本容器零改动） |

# Notes

- **分类函数落点**：`_classify_error` 放在 `application/runner.py`（模式匹配兜底 + 策略执行为应用层职责，符合 ADR-0044 Architecture Boundary）；五分类常量 `ERROR_CATEGORIES` 放 domain（taxonomy 声明，供 application 与 infrastructure 共享且避免层间倒置）；manager（infrastructure）只负责结构化上报透传与异常类型映射，不做策略判断。
- **结构化上报协议**：后端实例在 create/resume 后暴露 `error_category` 属性（五分类之一）即完成上报；现有真实后端均未实现该属性，走 stderr 兜底或 unknown，行为按 ADR-0044 Consequences 预期（mock 后端 → unknown → 按 task 不重试）。
- **行为变化点（ADR 已决策）**：auth/quota 失败从"重试 3 次后失败"变为"立即失败"；stderr 同时命中 quota/auth 与 transient 模式时按 quota/auth 处理（保守原则：宁可 unknown 不可误判 transient）。既有纯 transient 场景的退避参数、次数、agent_retry 事件形态完全不变（AC-026-E-1 与既有 test_agent_retry_writes_events 等测试双重验证）。
- **错误消息微调**：非 transient 失败在最后一次 attempt 时不再加 "after N infra retries" 前缀（此前缀仅 transient 退避耗尽时出现）；`tests/unit/test_runtime.py::test_agent_raises_after_infra_retries_exhausted`（match="infra retries"）为全 transient 场景，不受影响。
- **`_TRANSIENT_PATTERNS` 未改动**：`tests/recovery_support/failure.py` 的拷贝与漂移守卫（test_transient_patterns_copy_matches_production_runner）不受影响；auth/quota 另立 `_AUTH_QUOTA_PATTERNS`。
- uv.lock 的既有未提交修改未触碰、未提交。

# Exit

全部 Acceptance 通过，合回 develop（--no-ff），分支删除，不 push。
