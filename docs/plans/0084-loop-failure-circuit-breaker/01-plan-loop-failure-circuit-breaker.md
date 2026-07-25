---
title: Loop 失败熔断与 loop_state Plan
description: per-loop loop_state 存储 + 连续失败达阈值自动熔断 paused + dispatch deferred 留队 + 手动 unpause（CLI/Web）+ UI 失败与熔断呈现，AC-027 九场景
type: plan
status: done
created: 2026-07-25T06:20:00Z
---

# Context

无人值守循环下故障 loop 会被 cron 高频 dispatch 反复触发，反复消耗配额而无人知晓。现状没有 per-loop 跨 run 状态存储位：`state.json` 是 per-run 业务状态，runs 历史是只读事实。ADR-0045（accepted）决策独立 `~/.loopflow/loop_state/<loop>.json` 方案；Spec 已声明 Loop 状态数据模型（`docs/spec/0001-loopflow.md` §Loop 状态）、BR-050/BR-051 与 Web API 边界「暂停解除 / 恢复 Loop」行；AC-027 九场景（N-1~N-4 / B-1~B-3 / E-1 / F-1）为验收权威，scheduling manifest 中 TARGETS 已冻结（N-1/N-2/N-3/B-1/B-2/F-1 → `unit:loop-state`，N-4/E-1 → `process:cli-dispatch`，B-3 → `process:cli-run`），test_node 均为 `planned::` 占位。0082 已交付队列显式状态（`mark_status` 可复用）；0083 已落 run.json `error_category`/`error_summary`，读模型投影与 UI 渲染未补齐（`types.ts:15` 已定义 `error_summary` 但 App.tsx 未渲染）；`tests/recovery_support/fixtures.py` 已提供 `LoopStateFactory`/`QueueEntryFactory`。

契约来源：docs/adr/0045-loop-failure-circuit-breaker.md、docs/ac/0004-scheduling.md AC-027、docs/spec/0001-loopflow.md BR-050/BR-051 + §Loop 状态 + §Web API 边界。

# Request

实现 Loop 失败熔断：run 进入 failed 终态时该 loop 连续失败计数 +1，done 归零；达阈值自动置 paused；paused 的 loop 其队列任务在 dispatch 中标记 deferred 留队不计 errors；手动 run 不拦截；解除仅手动（CLI `unpause` / Web `POST /api/v1/loops/{name}/unpause`）；UI 呈现 paused 徽标、streak 计数与 Run 的 error_summary/error_category。AC-027 全部 9 场景自动化通过并登记 manifest 真实 test_node；既有 dispatch/queue/run/recover 行为零回归。

# Output Format

- 生产代码：
  - `src/loopflow/infrastructure/loop_state.py`（新）：`load(loop)` / `record_failure(loop, run_id)` / `record_success(loop)` / `unpause(loop)` / `failure_threshold(meta)`；目录遵循 `LOOPFLOW_HOME`（同 queue.py），原子写复用 `atomic_write_json`；损坏/缺失按初始状态（0/false）不抛错
  - `src/loopflow/application/execution.py`：run 终态收尾调用计数（failed → record_failure + 达阈值置 paused；done → record_success）；web 触发路径同样生效
  - `src/loopflow/infrastructure/dispatch.py`：消费前检查 paused → `mark_status(path, "deferred", reason=...)` 留队计 deferred 桶
  - `src/loopflow/presentation/cli.py`：`loopflow unpause <name>` 命令
  - `src/loopflow/application/web.py`：`unpause_loop(name)`（loop 不存在 → `loop_not_found`）
  - `src/loopflow/presentation/web/server.py`：`POST /api/v1/loops/{name}/unpause` 路由
  - `src/loopflow/infrastructure/web_resources.py`：Loop summary/detail 投影含 paused/paused_reason/consecutive_failures
  - `src/loopflow/infrastructure/web_storage.py`：Run summary 投影补 `error_category`
- 前端（web/）：Loops 工作区 paused 徽标 + 原因 + unpause 按钮；Run 列表/详情渲染 error_summary 与 error_category；streak 计数在 Loop 摘要聚合呈现
- 测试：`tests/unit/test_loop_state.py`（读写/阈值/损坏回退/unpause）+ `tests/e2e/test_scheduling_e2e.py`（AC-027 场景：dispatch paused 分支、手动 run 不拦截、unpause CLI）+ `tests/unit/test_web_application.py` 或 `tests/integration/test_web_api.py`（unpause API 404/成功）
- manifest：`tests/scheduling_support/manifest.py` TEST_NODES + `tests/system/scheduling_cases.json` 重新生成
- Report：`docs/plans/0084-loop-failure-circuit-breaker/01-report-loop-failure-circuit-breaker.md`

# Constraints

- TDD：先写 AC-027 九场景测试确认红，再实现转绿
- loop_state 文件损坏或缺失按初始状态处理，不阻塞 run 与 dispatch（AC-027-E-1）
- 手动 `loopflow run` 与 dispatch 触发的失败都计入 streak；手动 run 不被熔断拦截（AC-027-F-1 / B-3）
- 解除仅手动，不提供自动解除（ADR-0045 §4）
- unpause 命名决策：CLI `loopflow unpause <name>`，Web `POST /api/v1/loops/{name}/unpause`（本容器 Plan 冻结）
- Spec 补充：UI 约束新增「失败与熔断呈现」小节（DESIGN 遗漏补充，方向「自动暂停+UI 呈现」已经用户批准；Web API 边界行 Spec 已声明无需新增）
- commit 拆分：文档与代码分开；测试 `test(loop)`、实现 `feat(loop)`、manifest `test(infra)`、前端 `feat(web)`、Report `docs(plan)`、Spec 补充 `docs(spec)`
- uv.lock 有一处与本任务无关的未提交修改，不触碰、不提交
- 前端从简：信息可见 + 操作可用即可，视觉沿用现有组件风格

# Steps

1. 本容器文档（README + Plan）+ Spec UI 补充 commit 到 develop，拉分支 `feat/0084-loop-failure-circuit-breaker`
2. TDD 红：loop_state 单测（初始读/record_failure/record_success/阈值触发 paused/frontmatter 覆盖与非法值回退/损坏 JSON 回退/unpause 清除）+ AC-027 九场景（unit:loop-state 六场景走 execute_workflow；dispatch paused/deferred 与损坏回退走 process:cli-dispatch；手动 run 不拦截走 process:cli-run）+ unpause CLI/API 测试；运行确认红
3. 实现 loop_state 模块
4. 实现 execution 终态计数 + dispatch paused 分支
5. 实现 CLI unpause + WebApplication.unpause_loop + server 路由 + Loop/Run 投影
6. 前端：types/api/App.tsx 补 paused 徽标、unpause 操作、error_summary/error_category 渲染、streak 聚合；同步前端测试
7. 测试转绿：AC-027 九场景 + 既有测试零回归
8. manifest 落实：TEST_NODES 登记 9 个真实节点，`check-ac-manifest.py --profile scheduling --write` 重新生成；strict 应只剩 AC-010-N-2/E-2 两个 planned（BL-010 遗留）
9. 门禁：`uv run pytest tests/ -q` 全绿；scheduling/recovery/web 三 profile `--allow-planned` 通过；`cd web && npm run test:coverage` 与 `npm run build` 通过；npm audit 既有失败跳过并说明
10. Report（AC-027 逐场景 [PASS] + commit 引用）+ README 状态表 done，合并 develop（--no-ff），删分支，不 push

# Acceptance

- AC-027-N-1：run failed 后 loop_state/hello.json consecutive_failures=1、paused=false、last_run_id 为该 run
- AC-027-N-2：随后 run done 后 consecutive_failures=0、paused=false
- AC-027-N-3：连续 5 次失败后 paused=true、paused_reason 含 `failure_streak:5`、paused_at 非空
- AC-027-N-4：paused loop 的队列任务 dispatch 后 mark deferred 留队（status_reason 含暂停原因）、不计 errors
- AC-027-B-1：frontmatter `failure_threshold: 2` 时第 2 次失败即 paused（覆盖默认 5）
- AC-027-B-2：unpause 后 paused=false、consecutive_failures=0，dispatch 恢复消费
- AC-027-B-3：paused 时手动 `loopflow run hello` 正常执行不被拦截
- AC-027-E-1：loop_state 损坏（非法 JSON）或不存在时按初始状态处理，dispatch 正常不报错
- AC-027-F-1：手动触发的失败同样计入 consecutive_failures
- 门禁：全量 pytest 全绿；三 profile manifest `--allow-planned` 通过；前端 test:coverage 与 build 通过

# Checkpoint

- 步骤 2 完成后确认九场景相关测试全红（失败原因均为未实现，而非测试本身错误），再进入实现
- 步骤 4 后先跑既有 dispatch/queue 测试确认无回归
- 合入前 manifest 三 profile（scheduling/recovery/web）检查均通过

# Exit

全部 Acceptance 通过，Report 归档，合回 develop。
