---
title: Reliable Stop Plan
description: 实现 running/waiting_input Run 的永久取消、进程组终止、PID 身份保护和迟到 worker 终态写保护
type: plan
status: done
created: 2026-07-22T18:00:00Z
---

# Goal

依据 ADR 0036、Spec v13、Interface 0001 和 AC-021，实现可靠停止：`stop` 是不可恢复的永久终止，必须先持久化取消意图，再终止已验证身份的 worker 进程组；`waiting_input` 无存活 worker 时也能原子取消并关闭未回答请求；迟到 worker 不能把 `cancelling/cancelled` 覆盖为 `done/failed`。

# Acceptance

本 Plan 完整负责以下场景，Report 必须逐项记录真实测试节点、`[PASS]` 和提交：

`AC-021-N-1` `AC-021-N-2`

`AC-021-B-1` `AC-021-B-2`

`AC-021-E-1` `AC-021-E-2`

`AC-021-F-1` `AC-021-F-2`

# Constraints

1. 状态机固定为 `running -> cancelling -> cancelled`、`waiting_input -> cancelled`；`done/failed/cancelled/legacy stopped/stale` 的非法 stop 返回 `invalid_run_transition`，且不得修改 `run.json`。
2. `stop` 必须先在 Run lock 内原子写入 `cancelling` 或 `cancelled`，写入失败返回 `atomic_write_failed`，不得向任何进程发送信号。
3. running Run 只终止已验证身份的 worker 进程组：必须同时校验持久化 `pid`、`process_started_at` 或等价启动标识、当前 `execution_epoch`，避免 PID 复用误杀无关进程。
4. 进程终止顺序为 process group `SIGTERM`、短 grace period、仍存活则 `SIGKILL`；信号目标和等待逻辑要可注入，测试不得依赖真实长耗时 sleep。
5. 取消意图成功落盘后，如果 worker 恰好自然退出或身份校验发现进程已消失，仍返回 200 且最终 `cancelled`；记录 `process_gone` 摘要，不产生半完成状态。
6. worker 写终态前必须通过 execution epoch 和 terminal guard；旧 epoch 或当前 Run 已是 `cancelling/cancelled` 时，不得覆盖终态。
7. `waiting_input` stop 不要求 PID 存活；需要关闭 pending intervention request 的数据结构和事件，但不实现 AC-022 的 respond、schema 校验或自动恢复。
8. legacy `stopped` 只读兼容：可展示、可 rerun、不可 recover/stop；不得迁移或重写旧文件。
9. CLI `stop` 和 Web `stop` 必须调用同一个 application stop service，并使用同一份 Run metadata worker identity；presentation 层不得各自读取不同 PID 来源或自行发送信号。
10. 旧 CLI 写过的 `loop.pid` 仅作 legacy 读取线索，不作为新语义的权威 PID；当它与 `run.json` worker identity 不一致时，以 `run.json` 为准，无法验证则按 `process_gone` 收敛。
11. CLI 只保留与现有入口兼容的 `stop` 行为；不扩展已声明废弃的 CLI 生命周期能力。Web API 和 WebUI 以 Interface 0001 为准。
12. 产品代码不得依赖 `tests/recovery_support`；AC-022 manifest 节点继续保持 `planned::`。

# Design

## Run 状态和持久化

应用层 `stop_run(run_id)` 在读取 Run 后执行一次受锁保护的 compare-and-set：

| 当前状态 | 第一阶段落盘 | 进程处理 | 最终状态 |
|----------|--------------|----------|----------|
| `running` | `cancelling`，保留本次 worker identity | 终止验证通过的 process group | `cancelled`，清除 pid/process_started_at |
| `waiting_input` | `cancelled` | 不要求 worker | `cancelled`，关闭 pending request |
| terminal/legacy/stale/failed | 不修改 | 不处理 | 409 |

running 分两次写入是为了把“取消意图”先落盘，避免 kill 成功但 Run 仍显示 running。第二次写入 `cancelled` 时仍检查当前 epoch 和状态；若进程已不存在，也清除 worker 字段并记录摘要。

## Process identity

首次执行和恢复 worker 启动时补齐：

- `pid`: worker 入口进程 PID；
- `process_group_id`: worker process group ID；
- `process_started_at`: 从 OS 可观测的启动时间或启动 token；
- `execution_epoch`: 已由 0043 提供的单调 epoch。

stop 只在上述身份与当前 OS 进程匹配时发送信号。身份不匹配按 `process_gone` 收敛到 `cancelled`，不报 500。

## Termination abstraction

新增小型 process control port，默认实现使用标准库 `os.killpg`、`signal.SIGTERM`、`signal.SIGKILL` 和短轮询等待；测试实现记录信号、模拟忽略 TERM、PID 复用和进程消失。该 port 只属于 infrastructure/application 边界，不暴露给 workflow。

## Race handling

自然完成和 stop 并发时以先持久化成功的合法状态为准：

- worker 先写 `done/failed`：随后 stop 看到 terminal，返回 409 且不修改文件；
- stop 先写 `cancelling/cancelled`：worker 终态写被 epoch/terminal guard 拒绝；
- stop 写 `cancelling` 后进程消失：stop 继续写 `cancelled`，返回 200。

# Steps

1. 建立 AC-021 的失败测试和 manifest 映射：unit 覆盖状态机、epoch guard、PID 身份；application/API 覆盖 200/409/500；system 或 integration 覆盖真实 process group TERM/KILL。
2. 扩展 Run metadata reader/writer：持久化 worker identity、process_group_id、stop 摘要和 pending request close hook；非法转换保持字节不变。
3. 在执行器启动 worker 时写入 process identity；终态写入前统一走 epoch/terminal guard。
4. 实现 `stop_run` 两阶段状态转换和 process control port；注入 fault double 覆盖 atomic write failure、PID reuse、TERM ignored、process gone。
5. 更新 Web API `POST /runs/{run_id}/stop` 与错误映射；确认 `/recover` 对 `cancelled/stopped` 仍返回 `invalid_run_transition`。
6. 重接 CLI `stop` 到同一个 application stop service，废弃 presentation 层直接读 `loop.pid` 和 `os.kill(pid)` 的路径；新增 CLI/Web PID 一致性回归测试。
7. 更新 WebUI allowed actions 和 Stop 控件：running/waiting_input 可 Stop，cancelled/legacy stopped 不提供 recover；保持 Retry/Continue 行为不回退。
8. 保留 CLI `stop` 入口但不扩展已废弃 resume 语义；新增必要 integration 测试即可。
9. 将 AC-021 的 8 个 manifest 节点替换为真实测试节点；AC-022 继续 planned。
10. 运行 targeted Python、recovery allow-planned checker、前端相关测试、MR gate 和 scoped submission gate，回填 Report。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| State machine | running/waiting_input 正确取消；terminal 非法 stop 字节不变 | Report: PASS |
| Process control | TERM、TERM ignored 后 KILL、process gone、PID reuse 均可验证 | Report: PASS |
| CLI/Web parity | CLI 和 Web stop 使用同一 service、同一 worker identity；`loop.pid` 不再分叉语义 | Report: PASS |
| Race guard | stop 与 worker done/failed 竞态不会覆盖 cancelled | Report: PASS |
| API/UI | Interface 0001 的 stop status/error/allowed_actions 一致 | Report: PASS |
| Legacy | legacy stopped 可读、不可 recover/stop、可 rerun | Report: PASS |
| AC coverage | AC-021 8 个场景均有真实节点；AC-022 planned 不变 | Report: PASS |
| Regression | AC-020、Web manifest、Python/前端/浏览器/wheel 门禁无回归 | Report: PASS |

# Review Points

需要审核的关键决策只有三处：

1. 是否接受 `running` stop 的两阶段落盘：先 `cancelling`，进程处理后 `cancelled`；`waiting_input` 直接 `cancelled`。
2. 是否接受 PID 复用保护以 `pid + process_group_id + process_started_at + execution_epoch` 为最小身份集合；若平台无法提供可靠 `process_started_at`，实现可退化为启动 token，并把无法验证视为 `process_gone`。
3. 是否接受本 Plan 只预留 pending request close hook，不实现 AC-022 的 request/response 产品行为。

# Exit

全部 AC-021 场景有机器证据且不再使用 planned node、Report complete、MR gate 与 scoped submission gate 通过后，才能 squash 合并到 `develop`。AC-022 planned nodes 保持不变，由后续 Plan 接管；全局 recovery strict manifest 留到 AC-022 完成后执行。
