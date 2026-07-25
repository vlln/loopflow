---
title: stale 失联宽限期 Plan
description: run.json 新增 stale_since，读模型首次判定 stale 原子写入不刷新；默认 24h 宽限内 reconcile 返回 409 run_in_grace，期满后按 BR-032 转 failed；宽限内 worker 恢复写终态优先并清除 stale_since；UI 呈现失联（宽限中）与剩余时间，AC-029 七场景
type: plan
status: done
created: 2026-07-25T07:05:00Z
---

# Context

现状 stale 是纯读时投影：`web_storage.py` 的 `read_summary` 实时 PID 探活（:268-270），失联即 stale、reconcile 即 failed（:330-349 直接转 failed），没有时间维度。笔记本睡眠后 PID 探活失败导致仍存活的 run 被误判失败，是本地单用户场景的高频误伤。ADR-0046（accepted）决策 stale 宽限期形态；Spec 已声明 run.json `stale_since` 字段（§Run 数据模型 :229）、BR-052（对 BR-032 的补充约束）与 Web API 边界「修复 stale Run（宽限期约束）」行；AC-029 七场景（N-1~N-2 / B-1~B-2 / E-1~E-2 / F-1）为验收权威，recovery manifest 中 TARGETS 已冻结（N-1/N-2/E-1/E-2 → `GET /api/v1/runs/{run_id}`，B-1/B-2/F-1 → `POST /api/v1/runs/{run_id}/reconcile`）、HTTP_STATUS_BY_CODE 已含 `run_in_grace: 409`，test_node 均为 `planned::` 占位。`tests/recovery_support/fixtures.py` 已提供 RunFactory（`stale_since_offset` 秒偏移构造持久化时间戳，None 不写键 = legacy 形态）。

契约来源：docs/adr/0046-stale-grace-period.md、docs/ac/0011-recovery-intervention.md AC-029、docs/spec/0001-loopflow.md BR-052 + §Run 数据模型 + §Web API 边界。

# Request

实现 stale 失联宽限期：读模型首次判定 stale 时把 `stale_since` 原子写入 run.json（只写一次，已存在不刷新）；宽限期（默认 24h 常量）内显式 reconcile 返回 409 `run_in_grace` 且 run.json 不修改，期满后按 BR-032 既有流程转 failed 并清除 `stale_since`；宽限期内 worker 恢复并写入终态时以 worker 写入为准、清除 `stale_since`（execution.py 与 cli.py 两条终态路径）；读模型投影透出 `stale_since` 与宽限剩余秒数，WebUI 宽限期内 stale 呈现「失联（宽限中）」与剩余时间。AC-029 全部 7 场景自动化通过并登记 manifest 真实 test_node；既有行为不变（非 stale reconcile 仍 409 `run_not_stale`，reconcile 后 recover 边界不变），零回归。

# Output Format

- 生产代码：
  - `src/loopflow/infrastructure/web_storage.py`：`STALE_GRACE_SECONDS` 常量（24h）；`read_summary` 首次判定 stale 时原子写入 `stale_since`（写入前重读校验：仍为 running、无 stale_since、pid/process_started_at/execution_epoch 一致，收窄与 worker 终态写的竞态窗口；已存在不刷新）；summary 投影补 `stale_since` 与 `stale_grace_remaining_seconds`；`reconcile` 宽限期内抛 `ValueError("run_in_grace")`（无 stale_since 按首次判定先记账再拒绝），期满后转 failed 并 `pop("stale_since")`
  - `src/loopflow/application/web.py`：`reconcile` 捕获 `run_in_grace` → `ApplicationError("run_in_grace")`
  - `src/loopflow/presentation/web/server.py`：`ERROR_STATUS` 新增 `"run_in_grace": 409`
  - `src/loopflow/application/execution.py`：worker 终态写入路径 `pop("stale_since")`（recover 路径 `update(previous)` 可能带入，显式清除）
  - `src/loopflow/presentation/cli.py`：`_finish_run` 同样 `pop("stale_since")`（手动 run 终态路径）
- 前端（web/）：`types.ts` RunSummary 补 `stale_since` / `stale_grace_remaining_seconds`；App.tsx 宽限期内 stale 行与详情呈现「失联（宽限中）」+ 剩余时间（非警报化，沿用 row-meta 样式）；App.test.tsx 补呈现用例
- 测试：`tests/unit/test_stale_grace.py`（新，AC-029-N-1/N-2/E-1/E-2：首次写入/worker 终态清除/不刷新/legacy）+ `tests/integration/test_web_api.py`（AC-029-B-1/B-2/F-1：run_in_grace 409/期满转 failed/run_not_stale 409）；更新三处编码旧契约的既有测试（test_web_storage 两条 + test_web_application 一条）对齐新语义
- manifest：`tests/recovery_support/manifest.py` TEST_NODES + `tests/system/recovery_cases.json` 重新生成
- Report：`docs/plans/0085-stale-grace-period/01-report-stale-grace-period.md`

# Constraints

- TDD：先写 AC-029 七场景测试确认红，再实现转绿
- `stale_since` 只写一次：已存在时读操作不得刷新（避免宽限期被读操作无限续命，AC-029-E-1）
- 宽限期内 reconcile 不得修改 run.json（AC-029-B-1）
- 宽限期 24h 为常量，不做可配置入口（ADR-0046 §2）；测试用 fixtures 的 stale_since 偏移构造时间窗口，不做生产代码时钟注入
- 既有行为不变：非 stale run reconcile 仍 409 `run_not_stale`（AC-029-F-1）；reconcile 后 recover 边界不变
- commit 拆分：文档与代码分开；测试 `test(run)`、实现 `feat(run)`、前端 `feat(web)`、manifest `test(infra)`、Report `docs(plan)`
- uv.lock 有一处与本任务无关的未提交修改，不触碰、不提交
- 前端从简：信息可见即可，视觉沿用现有组件风格

# Steps

1. 本容器文档（README + Plan）+ plans/README 索引 commit 到 develop，拉分支 `feat/0085-stale-grace-period`
2. TDD 红：`tests/unit/test_stale_grace.py`（N-1 首次写入/N-2 worker 终态清除/E-1 不刷新/E-2 legacy）+ `tests/integration/test_web_api.py`（B-1 宽限内 409 run_in_grace 且不修改 run.json/B-2 期满转 failed 清 stale_since/F-1 非 stale 409 run_not_stale）；运行确认红
3. 实现 web_storage（常量/首次写入/投影/reconcile 分支）+ application/web + server ERROR_STATUS
4. 实现 execution.py / cli.py 终态清除 stale_since
5. 更新三处旧契约既有测试对齐新语义（旧语义被 AC-029 显式取代）
6. 前端：types/api/App.tsx 补宽限中呈现；同步前端测试
7. 测试转绿：AC-029 七场景 + 既有测试零回归
8. manifest 落实：TEST_NODES 登记 7 个真实节点，`check-ac-manifest.py --profile recovery --write` 重新生成；strict 应全绿
9. 门禁：`uv run pytest tests/ -q` 全绿；scheduling/recovery/web 三 profile 按现状验证（scheduling strict 仍剩 AC-010-N-2/E-2 两个 planned 属 BL-010 遗留）；`cd web && npm run test:coverage` 与 `npm run build` 通过；npm audit 既有失败跳过并说明
10. Report（AC-029 逐场景 [PASS] + commit 引用）+ README 状态表 done，合并 develop（--no-ff），删分支，不 push

# Acceptance

- AC-029-N-1：running run 探活失败首次判定 stale，读模型返回 stale，run.json 原子写入 stale_since（首次判定时间）
- AC-029-N-2：宽限期内 worker 恢复写入终态（done/failed），以 worker 写入为准，stale_since 已清除
- AC-029-B-1：stale_since 距今不足 24h 时 reconcile 返回 409 run_in_grace，run.json 未被修改
- AC-029-B-2：stale_since 距今超过 24h 时 reconcile 按既有流程转 failed、写 error_summary、清除 pid 字段与 stale_since
- AC-029-E-1：run.json 已含 stale_since，连续两次读取仍 stale 时 stale_since 保持首次值不被刷新
- AC-029-E-2：legacy run（无 stale_since）判定 stale 按首次判定处理，写入 stale_since，行为同 AC-029-N-1
- AC-029-F-1：非 stale run（进程存活）reconcile 返回 409 run_not_stale（既有行为不变）
- 门禁：全量 pytest 全绿；三 profile manifest 按现状通过；前端 test:coverage 与 build 通过

# Checkpoint

- 步骤 2 完成后确认七场景相关测试全红（失败原因均为未实现，而非测试本身错误），再进入实现
- 步骤 5 后先跑既有 web_storage/web_application/web_api 测试确认语义对齐无遗漏
- 合入前 manifest 三 profile（scheduling/recovery/web）检查均通过

# Exit

全部 Acceptance 通过，Report 归档，合回 develop。
