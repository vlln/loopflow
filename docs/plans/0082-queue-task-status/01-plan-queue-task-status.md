---
title: 队列任务显式状态 Plan
description: 队列条目 status/status_reason/superseded_by 状态机 + enqueue --supersede + dispatch deferred/superseded 两桶 + Web 投影透传，AC-028 七场景
type: plan
status: in_progress
created: 2026-07-25T05:40:00Z
---

# Context

队列任务目前是"存在即 pending"的一次性文件：资源锁失败"跳过留队"无状态可查，同 loop 重复 enqueue 不去重，`skipped` 不落盘无法审计。ADR-0047（accepted）决策显式状态机；Spec v15 §队列条目数据模型已声明 status/status_reason/superseded_by 三字段；BR-053 定义行为契约。0081 已交付 `QueueEntryFactory`（status 三字段 fixture）与 scheduling manifest profile（AC-028 七场景为 `planned::` 占位）。

契约来源：docs/adr/0047-queue-task-status.md、docs/ac/0004-scheduling.md AC-028、docs/spec/0001-loopflow.md BR-053。

# Request

实现队列任务显式状态语义，使 AC-028 全部 7 场景（N-1~N-4 / B-1 / E-1 / F-1）自动化通过并登记 manifest 真实 test_node，既有 AC-012-B-1/F-1 语义不回归。

# Output Format

- 生产代码：`src/loopflow/infrastructure/queue.py`（状态机与文件操作）、`src/loopflow/infrastructure/dispatch.py`（消费决策）、`src/loopflow/presentation/cli.py`（`--supersede` 标志）、`src/loopflow/infrastructure/web_resources.py`（投影透传）
- 测试：`tests/e2e/test_scheduling_e2e.py`（AC-028 七场景）+ `tests/unit/test_queue.py`（状态机分支单测）
- 契约同步：`tests/web_support/contracts.py`（QUEUE_ITEM_SCHEMA + 示例）、`docs/interface/0001-web-api.md`（queue item 字段表）
- manifest：`tests/scheduling_support/manifest.py` TEST_NODES + `tests/system/scheduling_cases.json` 重新生成 + `tests/infrastructure/test_scheduling_manifest.py` 计数自证同步
- Report：`docs/plans/0082-queue-task-status/01-report-queue-task-status.md`

# Constraints

- TDD：先写 AC-028 七场景测试确认红，再实现转绿；单元测试覆盖 queue.py 状态机各分支（边界/异常维度）
- 向后兼容：缺 status 或未知 status 的既有条目按 pending 处理（AC-028-E-1），dispatch 不得因此阻塞
- AC-012-B-1（资源冲突留队）/ AC-012-F-1（失败任务移除不重试）语义不变；`summary["skipped"]` 键保留（兼容既有消费方），资源锁失败改计 deferred 桶，AC-012-B-1 的 e2e 断言同步调整为 deferred 计数（语义不变，仅桶显式化）
- deferred/superseded 均不计入 dispatch errors
- Web 侧只改后端投影与接口契约文档，不动前端展示
- **已知偏差（轻微约束冲突）**：ADR-0047 Consequences 提到"与 ADR-0045 衔接：paused loop 的队列任务经 dispatch 落入 deferred 桶"，但 loop_state/paused 生产代码尚不存在（AC-027 由 0084 熔断容器实现）。本容器 dispatch 的 deferred 只来源于资源锁失败；paused 衔接留 0084，届时补 AC-027-N-4
- commit 拆分：文档与代码分开；实现 `feat(queue)`、manifest 落实 `test(infra)`、Report `docs(plan)`
- uv.lock 有一处与本任务无关的未提交修改，不触碰、不提交

# Steps

1. 本容器文档（README + Plan）commit 到 develop，拉分支 `feat/0082-queue-task-status`
2. TDD 红：`tests/e2e/test_scheduling_e2e.py` 新增 `TestQueueTaskStatus` 七场景；`tests/unit/test_queue.py` 新增状态机单测（enqueue 默认 pending、supersede 各分支、effective_status 未知/缺失回退、mark_status 往返）；运行确认红
3. 实现 `queue.py`：`VALID_STATUSES`、`enqueue(..., supersede=False)`（新任务 uuid 先生成，同 loop pending/deferred 标记 superseded + superseded_by + status_reason）、`mark_status()`、`effective_status()`；`list_queue` 透传新字段
4. 实现 `dispatch.py`：superseded 跳过+删文件计 superseded 桶；锁失败 mark deferred + status_reason 留队计 deferred 桶；summary 增加 deferred/superseded（保留 skipped 键）；未知/缺失 status 按 pending 消费
5. CLI `enqueue --supersede` 标志 + dispatch 输出补 deferred/superseded
6. Web 投影 `_project` 透传三字段（未知 status 回退 pending）；contracts.py schema/示例与 docs/interface/0001-web-api.md 同步
7. 测试转绿：AC-028 七场景 + 单测 + 既有调度测试零回归
8. manifest 落实：TEST_NODES 登记 7 个真实节点，`check-ac-manifest.py --profile scheduling --write` 重新生成，自证计数 14/18 → 21/11
9. 门禁：`uv run pytest tests/unit tests/e2e tests/infrastructure -q` 全绿；`check-ac-manifest.py --profile scheduling`（strict 因 AC-027 仍 planned 失败时改 `--allow-planned` 并在 Report 说明）；全量 `uv run pytest tests/ -q` 无回归；mr-gate npm audit 既有失败（brace-expansion）跳过并说明
10. Report（AC-028 逐场景 [PASS] + commit 引用）+ README 状态表 done，合并 develop（--no-ff），删分支，不 push

# Acceptance

- AC-028-N-1：enqueue 后任务 JSON 含 status=pending
- AC-028-N-2：资源锁被持有 → dispatch 标记 deferred + status_reason 非空留队；锁释放后再 dispatch 正常执行
- AC-028-N-3：`enqueue --supersede` → 旧任务 superseded + superseded_by=新任务 uuid，新任务 pending
- AC-028-N-4：dispatch 跳过并清理 superseded，仅 pending 执行；superseded 计数且不计 errors
- AC-028-B-1：无同 loop 任务时 `--supersede` 与正常入队一致
- AC-028-E-1：未知/缺失 status 按 pending 正常消费，不阻塞 dispatch
- AC-028-F-1：deferred 与 superseded 同存时分别计数，均不计 errors
- 门禁：`tests/unit + tests/e2e + tests/infrastructure` 全绿；scheduling manifest AC-028 部分 strict 通过；全量 pytest 无回归

# Checkpoint

- 步骤 2 完成后确认七场景全红（失败原因均为未实现，而非测试本身错误），再进入实现
- 步骤 6 后先跑 `tests/unit/test_web_resources.py` 与 `tests/infrastructure/test_web_test_support.py` 确认契约同步无漂移
- 合入前 manifest 三 profile（web/recovery/scheduling）检查均通过

# Exit

全部 Acceptance 通过，Report 归档，合回 develop。
