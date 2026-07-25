---
title: Agent 失败分类与重试/续接策略 Plan
description: 失败五分类（auth/quota/transient/task/unknown）+ 结构化上报优先/stderr 兜底 + transient 既有退避不变、其余不重试 + agent_done/run.json 携带 error_category，AC-026 七场景
type: plan
status: done
created: 2026-07-25T06:10:00Z
---

# Context

现状对 agent 失败是无差别重试：`application/runner.py` 仅 6 个 `_TRANSIENT_PATTERNS` stderr substring，auth/quota 失败也被照着 3/9/27s 退避重试（浪费配额、延迟失败反馈）；`backends/manager.py:185-197` 异常分支把后端异常吞成 `exit_code=1`，类型信息丢失；`AgentError` 无 `category` 字段。ADR-0044（accepted）决策五分类策略；Spec v15 §run.json 数据模型已声明 `error_category` 字段；BR-049 定义行为契约。0081 已交付脚本化 fake（`SessionBackendFake` per-attempt 脚本 + `AttemptResult.error_category` + `agent_done_payload()`）与测试侧参考实现 `tests/recovery_support/failure.py`；recovery manifest 中 AC-026 七场景为 `planned::` 占位，TARGETS 已冻结（N-1~E-1 → `unit:failure-classification`，F-1 → `POST /api/v1/runs/{run_id}/recover`）。

契约来源：docs/adr/0044-failure-classification.md、docs/ac/0011-recovery-intervention.md AC-026、docs/spec/0001-loopflow.md BR-049 + §run.json error_category。

# Request

实现失败分类驱动的重试/续接策略，使 AC-026 全部 7 场景（N-1~N-3 / B-1 / B-2 / E-1 / F-1）自动化通过并登记 manifest 真实 test_node；既有 transient 重试行为、recover 边界（BR-033）、goal 模式 exit code 3/6 不回归。

# Output Format

- 生产代码：
  - `src/loopflow/domain/agent_def.py`：`ERROR_CATEGORIES` 五分类常量 + `AgentError.category` 字段
  - `src/loopflow/application/runner.py`：`_classify_error(reported, stderr)` 分类函数（结构化优先 > auth/quota 模式表 > 既有 transient 模式表 > unknown）+ 重试循环按分类决策 + 失败时 `ctx.failed_error_category` 落上下文
  - `src/loopflow/infrastructure/backends/manager.py`：agent_done payload 携带 `error_category`（后端实例上报时）；异常分支映射异常类型为分类
  - `src/loopflow/application/execution.py`：run.json 失败路径写 `error_category`
- 测试：`tests/unit/test_failure_classification.py`（分类函数单测 + AC-026 六场景）+ `tests/unit/test_web_application.py`（AC-026-F-1 recover continue 边界）
- 测试基建：`tests/recovery_support/fakes.py`（fake 暴露 `_transport.stderr_text` / `error_category` / `close()`，供 manager 真实链路消费）
- manifest：`tests/recovery_support/manifest.py` TEST_NODES + `tests/system/recovery_cases.json` 重新生成
- Report：`docs/plans/0083-failure-classification/01-report-failure-classification.md`

# Constraints

- TDD：先写 AC-026 七场景测试确认红，再实现转绿；单测覆盖分类函数五类 + 冲突优先级 + 模式表边界
- 完全向后兼容：既有 transient 重试（退避参数、次数、agent_retry 事件形态、recover 语义）、goal exit code 3/6 均不变
- 模式表扩充保守：宁可 unknown 不可误判 transient；auth/quota 模式先于 transient 模式匹配
- `tests/recovery_support/failure.py` 的 `TRANSIENT_PATTERNS` 拷贝与生产 `_TRANSIENT_PATTERNS` 保持一致（既有漂移守卫不破坏——本容器不改 `_TRANSIENT_PATTERNS`，另立 auth/quota 模式表）
- commit 拆分：文档与代码分开；测试 `test(agent)`、实现 `feat(agent)`、manifest `test(infra)`、Report `docs(plan)`
- uv.lock 有一处与本任务无关的未提交修改，不触碰、不提交

# Steps

1. 本容器文档（README + Plan）commit 到 develop，拉分支 `feat/0083-failure-classification`
2. TDD 红：`tests/unit/test_failure_classification.py` 新增分类函数单测（五类/优先级/边界）与 AC-026-N-1~E-1 六场景（agent 级：patch `_run_subagent`/`_make_backend` + `time.sleep`；run 级：execute_workflow + SessionBackendFake 走 manager 真实链路，断言 run.json/events.jsonl）；`tests/unit/test_web_application.py` 新增 AC-026-F-1（quota 失败 run recover --mode continue 按既有边界续接）；运行确认红
3. 实现 domain：`ERROR_CATEGORIES` + `AgentError.category`
4. 实现 runner：`_classify_error` + auth/quota 模式表 + 重试循环按分类决策 + `ctx.failed_error_category` + AgentError 携带 category
5. 实现 manager：payload 结构化 `error_category` + 异常分支映射（ConnectionError/TimeoutError → transient，其余 → unknown）；fake 暴露消费协议
6. 实现 execution：run.json 失败路径写 `error_category`，done 时清理
7. 测试转绿：AC-026 七场景 + 分类单测 + 既有测试零回归
8. manifest 落实：TEST_NODES 登记 7 个真实节点，`check-ac-manifest.py --profile recovery --write` 重新生成
9. 门禁：`uv run pytest tests/ -q` 全绿；`check-ac-manifest.py --profile recovery --allow-planned`（AC-029 仍 planned 属 0085）与 `--profile scheduling --allow-planned`（AC-027 仍 planned 属 0084）通过；npm audit 既有失败跳过并说明
10. Report（AC-026 逐场景 [PASS] + commit 引用）+ README 状态表 done，合并 develop（--no-ff），删分支，不 push

# Acceptance

- AC-026-N-1：第 1 次 transient 失败（stderr 含 "rate_limit"）第 2 次成功 → 退避重试后成功；events.jsonl 含 agent_retry（attempt/reason/delay）；agent_done 的 error_category 缺省或 transient
- AC-026-N-2：结构化上报 quota + stderr 含 "timeout" → 不自动重试（无 agent_retry），结构化优先于模式匹配
- AC-026-N-3：run.json 的 error_category 与 agent_done payload 分类一致，值为五分类之一
- AC-026-B-1：auth 失败 → 不自动重试，run 直接 failed，error_category=auth
- AC-026-B-2：无法匹配的失败 → error_category=unknown，按 task 处理不重试
- AC-026-E-1：transient 连续失败 → AgentError（category=transient），run failed；agent_retry 共 3 条，退避 3/9/27s
- AC-026-F-1：quota 失败后 recover --mode continue → 按既有 continue 规则处理，分类不改变恢复边界
- 门禁：全量 pytest 全绿；recovery/scheduling manifest `--allow-planned` 通过

# Checkpoint

- 步骤 2 完成后确认七场景全红（失败原因均为未实现，而非测试本身错误），再进入实现
- 步骤 5 后先跑 `tests/infrastructure/test_failure_injection_support.py` 确认 fake 扩展无回归（含模式表漂移守卫）
- 合入前 manifest 两 profile（recovery/scheduling）检查均通过

# Exit

全部 Acceptance 通过，Report 归档，合回 develop。
