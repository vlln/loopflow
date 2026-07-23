---
title: Cancel Recovery Test Infrastructure Report
description: 记录取消恢复语义的 recovery manifest、fixture 和 contract 基础设施同步结果
type: report
status: complete
created: 2026-07-23T12:55:00Z
---

# Summary

0051 已完成 TEST_INFRA 同步。测试基础设施现在覆盖 AC-020..022 当前 37 个场景，并能表达 0050 新增的 cancelled recover/respond、waiting_input stop 后保留 pending request、atomic worker cancel 后 continue forbidden。

# Results

| 检查点 | 结果 | 证据 |
|--------|------|------|
| Manifest | PASS | `tests/system/recovery_cases.json` 重新生成，37 个场景全部覆盖 |
| Planned | PASS | 7 个新/变更产品语义保持 `planned::`，strict checker 会拦截未实现节点 |
| Contract | PASS | RunSummary schema 可表达 cancelled + recover/respond actions |
| Fixture | PASS | `recovery_boundary_metadata()` 表达 worker_running/no_worker_running、active_call_id 和 atomic continue boundary |
| Scope | PASS | 未修改 `src/` 产品代码或 Web 前端业务代码 |
| Tests | PASS | `pytest tests/infrastructure/test_recovery_manifest.py tests/infrastructure/test_recovery_support.py`：16 passed |

# Changes

- `tests/recovery_support/manifest.py`
  - 新增 AC-021-N-3、AC-021-B-3、AC-021-B-4、AC-022-N-5、AC-022-B-3 target/expectation。
  - 移除旧的 waiting_input stop closes request 与 cancelled stop/recover invalid transition test_node 证据映射，使其回到 planned。
- `tests/recovery_support/fixtures.py`
  - 新增 `recovery_boundary_metadata()`，统一表达取消点和 atomic worker 恢复边界。
- `tests/infrastructure/test_recovery_support.py`
  - 增加 cancelled Run allowed_actions contract 自证。
  - 增加 cancel point/atomic boundary fixture 自证。
- `tests/system/recovery_cases.json`
  - 由当前 AC-0011 重新生成，37 cases，7 planned nodes。

# Planned Nodes For DEVELOP

后续 DEVELOP 至少需要替换以下 planned 节点：

| AC | 语义 |
|----|------|
| AC-021-N-2 | waiting_input stop 后 pending request 保留且 allowed_actions 含 respond |
| AC-021-N-3 | cancelled recover mode=retry |
| AC-021-B-3 | atomic/isolated worker cancel 后 continue_not_supported |
| AC-021-B-4 | 非 atomic durable worker cancel 后 recover_continue |
| AC-021-E-2 | cancelled 无恢复边界时 recover/respond 返回明确错误 |
| AC-022-N-5 | cancelled + pending request 可 respond |
| AC-022-B-3 | cancelled + pending request 不自动关闭、不建模 abandon |

# Next

进入 DEVELOP，修改 Web Application、RunRepository/runtime cancel metadata、recover/respond 命令和前端动作展示，并逐项替换上述 planned 节点为真实测试。
