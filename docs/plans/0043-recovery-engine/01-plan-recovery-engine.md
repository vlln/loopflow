---
title: Deterministic Recovery Engine Plan
description: 实现可校验 Call 重放、失败 Agent retry/continue、稳定并行身份、恢复应用/API/CLI 与 WebUI 操作
type: plan
status: done
created: 2026-07-22T10:00:00Z
---

# Goal

依据 ADR 0036、Spec v13 和 Interface 0001，实现 failed Run 的确定性恢复：前序 succeeded Call 只有在 call_id、input_digest 和提交标记同时匹配时返回缓存；目标失败 Call 显式 retry 新 session 或 continue 原 durable session；重放分歧必须失败，不能执行错误调用或静默降级。

# Acceptance

本 Plan 完整负责以下场景，Report 必须逐项记录真实测试节点、`[PASS]` 和提交：

`AC-020-N-1` `AC-020-N-2` `AC-020-N-3` `AC-020-N-4`

`AC-020-B-1` `AC-020-B-2` `AC-020-B-3`

`AC-020-E-1` `AC-020-E-2` `AC-020-E-3`

`AC-020-F-1` `AC-020-F-2` `AC-020-F-3`

# Constraints

1. 恢复保持原 `run_id`，冻结首次执行的 args、backend、model、mock、phase 范围等 `execution_options`；recover 不接受覆盖。
2. 重放从 workflow `meta.state` 默认值开始，只注入已校验 Agent 输出和已持久化 Intervention 回答；不得以旧 `state.json` 作为起点。
3. 新缓存最少持久化 `call_id`、`input_digest`、`status`、`session_id`；同一 Call 的 retry/continue 追加生命周期段，不创建 attempt 文件。
4. `continue` 同时要求目标段有非空 session ID、backend 声明 `resume_session=true` 和 `durable_session_id=true`；条件不足返回 `continue_not_supported`，不得执行 retry。
5. digest 覆盖 ADR 0036 冻结的语义输入，使用稳定 JSON/UTF-8/SHA-256；密钥和环境变量值不得进入原文或缓存。
6. parallel/pipeline 在线程启动前按输入位置预分配层级 Call ID；线程完成顺序不得影响身份。
7. 每次首次执行或恢复递增 `execution_epoch`，Run lock 阻止同一 Run 并发 worker；旧 epoch 不得提交终态。
8. Web 不保留 `/resume`；CLI `resume` 仅为 deprecated `recover --mode retry` alias，且 stopped/cancelled Run 不可恢复。
9. 不实现 AC-021 的永久停止或 AC-022 的 Intervention 产品行为；只保留后续所需的 epoch、状态和接口扩展点。
10. 产品代码不得依赖 `tests/recovery_support`；测试通过公开 port 和独立 fixture 验证。

# Steps

1. 先为 AC-020 的 13 个场景建立失败的 unit/integration/API/CLI/UI 测试，并逐项将 recovery manifest 节点替换为真实测试节点；AC-021/022 保持 `planned::`。
2. 扩展 `RunContext` 和 cache I/O：稳定 Call ID 命名空间、规范化 input digest、`agent_start/agent_session/agent_resume/agent_done` 事件、单段 reader、legacy unverified reader。
3. 重构 `AgentRunner` backend 生命周期：session ID 获得时立即写入，succeeded/failed/interrupted 段正确收口；retry 创建 session，continue 仅调用 `resume_session`。
4. 修改 runtime 的 `parallel()`/`pipeline()`，在线程启动前为各输入位置分配子命名空间，并在线程局部继续分配 Call ID。
5. 修改共享执行器：首次运行冻结 `execution_options` 并建立 epoch；recover 从默认 state 重放到记录的目标 Call，校验 digest/目标到达，拒绝提前结束或路径漂移。
6. 在应用层增加 `recover_run(run_id, mode)`，使用 Run lock 原子校验 failed/legacy 状态、能力和 epoch；统一映射 `replay_diverged`、`continue_not_supported`、`invalid_run_transition`。
7. 将 Web API 从 `/resume` 迁移到 `POST /runs/{run_id}/recover`，输出 v13 Run/Call/Backend capability 和 `recover_retry/recover_continue` allowed actions。
8. 增加 CLI `recover --mode retry|continue`；将旧 `resume` 改为打印弃用提示并委托 retry，拒绝 stopped/cancelled。
9. 更新 WebUI Runs 操作：failed Run 显示 Retry；只有 durable 条件成立时启用 Continue，并显示不可用原因；移除 Resume 文案与 action。
10. 验证 AC-020 不再包含 planned node，运行全局 recovery allow-planned checker、Python/前端/浏览器测试、MR gate 和本 Plan 的 scoped submission gate，回填 Report；全局 strict checker 留到 AC-021/022 完成后执行。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Cache contract | 新段字段完整；损坏/未提交段不命中；跨段不串消息 | Report: PASS |
| Replay correctness | 相同 digest 命中，digest/路径/提前结束分歧失败 | Report: PASS |
| Session modes | retry 只 create；continue 只 resume；能力不足不降级 | Report: PASS |
| Stable identity | 顺序与 parallel/pipeline ID 不受完成顺序影响 | Report: PASS |
| Concurrency | Run lock 拒绝第二 worker；execution epoch 单调递增 | Report: PASS |
| Compatibility | legacy retry 标记 unverified；CLI resume 弃用 alias；Web `/resume` 不存在 | Report: PASS |
| UI/API | Retry/Continue availability 与 Interface v13 一致 | Report: PASS |
| AC coverage | AC-020 13 个场景均有真实节点，scoped submission gate 与全局 allow-planned checker 通过 | Report: PASS |
| Regression | Python、frontend、browser、wheel 与既有 60 场景无回归 | Report: PASS |

# Exit

全部 AC-020 场景有机器证据且不再使用 planned node、Report complete、MR gate 与 scoped submission gate 通过后，才能 squash 合并到 `develop`。AC-021/022 的 planned nodes 保持不变并由后续 Plan 接管；全局 recovery strict manifest 是三组功能全部完成后的 SYSTEM_TEST 门禁。
