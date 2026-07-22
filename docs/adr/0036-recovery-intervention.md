---
title: Reliable Recovery, Cancellation, and Intervention
description: 以可校验 Call 缓存支持 retry/continue 恢复，以终态取消和可重放输入支持可靠停止与人工介入
type: adr
status: accepted
created: 2026-07-22T06:35:57Z
---

# ADR 0036: Reliable Recovery, Cancellation, and Intervention

## Context

ADR 0004 以 `<seq>.jsonl` 和调用序号实现从头重放，已完成调用返回缓存，未完成调用重新执行。该机制适合透明恢复，但现有缓存命中只检查序号和 `agent_done.exit_code == 0`，不能证明恢复时的逻辑调用仍与原调用一致，也不能选择恢复失败 Agent 的 backend session。

当前 `resume` 还同时表达停止后继续、失败后重跑等不同意图。用户需要的控制面更窄且语义更严格：

1. 失败后恢复同一 Run，前序成功 Call 从缓存返回；失败 Call 可选择新 session 重跑或恢复原 session 上下文；
2. `stop` 表示永久结束 Run，不是暂停；
3. workflow 出现需要人类回答的阻塞时，持久化问题并释放执行进程，回答后恢复同一 Run；
4. 不引入 Python 调用栈序列化、数据库或预定义 DAG 状态机。

本 ADR 在保留序号重放和现有扁平 JSONL 缓存的前提下，收紧恢复正确性契约。ADR 被接受后替代 ADR 0004 的缓存命中和 Run 恢复语义、ADR 0012 的 state 恢复起点，以及 ADR 0034 中 stopped 可恢复的生命周期约束；ADR 0004 的“从头重放 workflow.py”决策继续有效。

## Decision

### 1. 恢复拆分为 `retry` 和 `continue`

失败 Run 使用相同 `run_id` 创建新一次执行，并从头重放 workflow：

| mode | 前序成功 Call | 目标失败 Call |
|------|---------------|---------------|
| `retry` | 校验后返回缓存结果 | 创建新的 backend session 重新执行 |
| `continue` | 校验后返回缓存结果 | 使用原 `session_id` 调用 backend `resume_session()` |

每次恢复都必须取得 Run 独占锁。首次执行时把自动选择后的有效 backend/model 与其他执行选项冻结到 Run；恢复沿用这些值，不接受覆盖，也不修改 loop、args 或已持久化响应。`done`、`cancelled` 和 legacy `stopped` Run 不允许恢复；`rerun` 仍创建新 Run。

`continue` 只有在目标 Call 已持久化非空 `session_id` 且 backend 声明支持 durable session resume 时可用。条件不满足时返回 `continue_not_supported`，不得静默降级为 `retry`。

### 2. `<call-id>.jsonl` 承载最小 Call 记录

不新增 Call 数据库或独立目录。顶层顺序 Call 的 call_id 仍为四位序号，因此路径与现有 `<seq>.jsonl` 相同；并行子 Call 使用层级 ID 和对应 `<call-id>.jsonl`。缓存必须包含以下最小事实：

| 字段 | 事件位置 | 语义 |
|------|----------|------|
| `call_id` | `agent_start`、`agent_done` | Run 内逻辑调用标识；顺序调用可使用零填充序号 |
| `input_digest` | `agent_start` | 本次调用规范化输入的 SHA-256 |
| `status` | `agent_done` | `succeeded`、`failed` 或 `waiting_input` |
| `session_id` | 获得时立即追加 `agent_session`，并在 `agent_done` 重复 | backend 可恢复 session；未知时为 null 或缺失 |

结果继续由现有 `agent_message_chunk`/`agent_message` 事件提取，不重复存储。`agent_done(status=succeeded, exit_code=0)` 是成功提交标记；没有该提交标记的部分文件不得作为成功缓存返回。

同一逻辑 Call 再次执行时继续追加到同一文件，以 `agent_start`（retry）或 `agent_resume`（continue）开始新的生命周期段。Reader 只在单个段内匹配 input_digest、提取输出和查找完成标记，不得把前一失败段的消息拼入后一段结果；不需要额外 attempt 文件或 attempt ID。

`input_digest` 覆盖 workflow.py 内容摘要、最终发送给 backend 的 user/system prompt、输出 schema、backend、model、Agent 定义和影响调用语义的执行选项。序列化使用稳定 JSON key 顺序和 UTF-8 字节。密钥值和环境变量值不得进入 digest 原文或缓存。

缓存命中要求：

```text
call_id 相同
AND input_digest 相同
AND agent_done.status == succeeded
AND agent_done.exit_code == 0
```

同一位置的 `call_id` 相同但 digest 不同时，恢复以 `replay_diverged` 失败，不覆盖旧缓存，也不执行目标 Call。损坏或缺少完成标记的缓存视为未提交 Call，可由 `retry` 重跑；`continue` 还要求可用 session。

### 3. 并行 Call 预分配稳定 ID

`parallel()` 和 `pipeline()` 必须在启动线程前按输入位置预分配 Call 命名空间，禁止工作线程竞争全局 counter 决定逻辑身份。每个分支使用线程本地子序号；并行完成顺序不影响 `call_id`。例如父 combinator 位于 `0003`，分支 0 内第一个 Agent Call 为 `0003.0000.0001`，分支 1 内第一个为 `0003.0001.0001`。

### 4. backend 显式声明 session 恢复能力

Backend capabilities 增加：

| capability | 含义 |
|------------|------|
| `resume_session` | backend 接受已有 session ID 继续执行 |
| `durable_session_id` | session ID 可在失败或进程退出后继续使用，并能在恢复所需时机提供给 loopflow |

loopflow 一获得 session ID 就追加 `agent_session` 缓存事件。仅在命令结束后才能返回 session ID 的 backend，无法保证进程中途崩溃后的 `continue`，但仍支持 `retry`。能力展示必须反映这一限制。

### 5. 人工介入是持久化、可重放的输入

workflow 可以通过 `intervene(key, prompt, schema=None)` 请求人工输入。`key` 在一次确定性重放路径中稳定且唯一。Agent 需要提问时必须返回以下结构化控制结果；loopflow 不从自然语言输出猜测阻塞：

```json
{"__loopflow":{"status":"waiting_input","key":"approve","prompt":"Approve?","schema":{"type":"boolean"}}}
```

workflow 直接调用产生的请求使用 `resume_mode=replay`，回答通过确定性重放返回。Agent 产生的请求使用 `resume_mode=continue`，只有在 durable `session_id` 已持久化时才可进入 `waiting_input`；否则本次 Call 以 `continue_not_supported` 失败，不创建一个无法继续的人工请求。

首次遇到未回答请求时：

1. 原子写入 request，包含 `request_id`、`key`、`prompt`、可选 schema、关联 `call_id/session_id`；
2. 追加 `intervention_requested` 事件；
3. Run 进入 `waiting_input`，当前执行进程正常退出；
4. 释放 backend、Run 执行锁和资源锁。

提交回答时先校验 schema，再持久化 immutable response 并追加 `intervention_responded`。随后使用相同 `run_id` 自动开始一次恢复。重放再次到达相同 `key` 时直接返回已持久化 response；若请求关联可恢复 Agent session，则以回答作为新消息继续该 session。

同一 request 只接受一次回答。重复提交相同或不同值均返回 `intervention_already_answered`。`waiting_input` 不是 goal mode 的 `blocked`：前者等待外部输入且可继续，后者仍表示 Agent 无法推进。

### 6. `stop` 是不可恢复的终止

Run 状态扩展为 `running`、`waiting_input`、`cancelling`、`cancelled`、`done`、`failed`；`stopped` 仅作为 legacy 可读状态。状态转换为：

```text
running -> cancelling -> cancelled
waiting_input -> cancelled
failed -> running                 recover
waiting_input -> running          respond
running -> done | failed | waiting_input
stale -> failed                   reconcile
```

停止命令先在 Run 独占锁内持久化取消意图，再终止执行进程组。先发送 SIGTERM，超过 grace period 后发送 SIGKILL。执行进程退出时不得把 `cancelling/cancelled` 覆盖为 `done/failed`。

每次执行获得递增的 `execution_epoch`。worker 写 Run 终态前必须验证自己仍持有当前 epoch；旧 worker 的迟到写入被拒绝。停止 `waiting_input` Run 不需要进程存在，直接进入 `cancelled` 并关闭未回答请求。

### 7. State 从初始值参与重放

恢复从 `meta.state` 默认值重新执行 workflow，不把上次执行结束时的 `state.json` 作为重放起点。成功缓存结果驱动 workflow 重新计算 state。`state.json` 是当前投影视图，不是恢复检查点。

workflow 必须满足确定性重放契约：Call 顺序和控制流只能稳定依赖 args、缓存的 Agent 结果、已持久化 Intervention 回答和确定性 Python 逻辑。`random`、当前时间、变化的环境变量或实时外部读取不得直接决定 Call 路径。recover 必须重放到预期的失败 Call 或 Intervention；workflow 在到达目标前提前结束同样视为 `replay_diverged`，不得把 Run 标记 done。

loopflow 仍不保证任意 Python 或外部系统副作用 exactly-once。需要可靠重试的文件修改应使用 worktree 隔离或由 workflow 使用幂等键；直接作用于共享外部系统的失败 Call 只有 at-least-once 语义。

首版不提供 checkpoint 或通用持久化 `memo()`。当真实 workflow 出现昂贵本地计算或必须捕获时间、随机数、外部读取的需求时，再通过独立 ADR 引入持久化输入原语，不扩展为 Python 调用栈序列化。

### 8. Legacy 兼容

旧 `<seq>.jsonl` 没有 `input_digest/status` 时继续按 ADR 0004 只读识别，但只允许 legacy `retry`，并在 UI/CLI 标记为 unverified recovery。旧 `stopped` Run 保持可读且不可恢复。现有 CLI `resume` 命令在兼容期作为 failed Run 的 `recover --mode retry` deprecated alias；不再接受 stopped Run。Web API 不保留 `/resume`，调用方直接迁移到 `/recover`。新写入缓存一律使用本 ADR 契约，不原地迁移旧文件。

## Alternatives

### 只持久化 `session_id`

`session_id` 只能让 backend 找回对话，不能证明它对应哪个 workflow Call、该 Call 是否成功，也不能为前序成功调用返回结果或检测 workflow 输入变化，因此不足以承担恢复正确性。

### 新增完整 Call/Attempt 数据库

可以表达更丰富的尝试历史，但增加存储模型和迁移成本。当前需求可由扩展现有扁平缓存满足；Attempt 一等模型留待出现审计或多次回退需求时引入。

### 保持 worker 阻塞等待回答

实现直观，但占用进程和资源锁，服务重启后仍丢失 Python 调用栈。持久化请求后退出并重放与现有恢复模型一致。

### `stop` 继续允许 resume

这会把永久终止和暂停混为一谈，使用户无法确信运行已结束。当前范围不提供 pause；未来如需要应新增独立状态和命令。

## Consequences

### Positive

- 继续复用现有 JSONL 和从头重放架构，新增概念受控。
- `retry` 与 `continue` 行为可预测，能力不足时明确失败。
- digest 防止位置相同但调用语义已变化时错误命中缓存。
- 阻塞不长期占用进程，服务重启后仍可回答。
- 取消意图和 execution epoch 防止停止状态被迟到 worker 覆盖。

### Negative

- backend session ID 的提供时机决定 `continue` 的可用范围。
- 每次恢复需要重新执行 workflow 中的普通 Python 代码。
- digest 规范、并行稳定 ID 和 legacy 路径增加测试矩阵。
- 外部副作用仍要求 workflow/Agent 自己提供幂等性或隔离。

## Architecture Boundary

本 ADR 约束 runtime 的 Call 分配和重放、AgentRunner 的 session 生命周期、Run repository 的状态转换与 epoch 校验、backend capabilities、CLI/Web application commands、事件投影以及 intervention 持久化。

Presentation adapter 不得自行判断缓存命中、降级 `continue`、覆盖 terminal state 或从 Agent 文本推断 intervention。

## Verification

不需要外部技术选型 spike。进入 TEST_INFRA 后通过缓存契约、并行确定性、故障注入、进程竞态和 API 契约测试验证；所有场景以 AC-020 至 AC-022 为准。
