# 执行容器 0104 — executor 锁释放竞态修复（SYSTEM_TEST CI 失败）

| 子任务 | 状态 |
|--------|------|
| `_wait_terminal` 等待 `.execution.lock` 释放 | done |

## 分支

`fix/0104-executor-lock-race`（从 `develop` 拉出）

## 失败原因分类

**基建缺陷（测试设施竞态），非本轮业务代码引入**：PR #18 CI（python 3.10/3.14）中 `test_recover_reuses_persisted_working_directory` 失败 `invalid_run_transition`。根因：`execute_workflow` 先写 run.json 终态、后在子进程 finally 中释放 `.execution.lock`；测试的 `_wait_terminal` 只看 run.json，CI 机器慢（coverage 追踪）时 recover `start()` 的 O_EXCL 抢在锁释放前。本地 3/3 复现不出（子进程 teardown 快）。该竞态自 ADR-0042 引入此测试起存在。

## 修复

`_wait_terminal` 在终态可见后同时等待 `.execution.lock` 消失（执行完全结束的定义）。不动引擎行为。并发锁契约测试（`test_background_executor_rejects_second_worker_for_same_run`）不经过该 helper，不受影响。

## 验证

- `test_web_execution.py` ×5 全过（16 passed）
- `tests/unit + tests/integration` 459 passed
