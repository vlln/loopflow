---
title: loopflow Web API v1
description: 本地 WebUI 的 REST 与 SSE 接口契约，覆盖 Runs、恢复、停止、人工介入、Loops、Queue、Backends 和事件续传。
type: interface
status: active
created: 2026-07-18T22:00:00Z
---

# loopflow Web API v1

## 一、通用约定

- Base path：`/api/v1`
- JSON 请求和响应：`application/json; charset=utf-8`
- SSE：`text/event-stream; charset=utf-8`
- 时间：UTC ISO 8601 字符串
- 分页：`limit` 默认 50，范围 1..200；`cursor` 是服务端不透明字符串
- ID、路径和枚举值区分大小写
- 未声明的请求字段返回 422，不静默忽略

错误响应统一为：

```json
{
  "error": {
    "code": "run_not_found",
    "message": "Run 'abc' was not found",
    "details": {}
  }
}
```

| HTTP | code | 语义 |
|------|------|------|
| 400 | `invalid_json` | 请求体不是合法 JSON |
| 403 | `path_forbidden` | 文件路径越过允许根目录 |
| 404 | `loop_not_found` / `run_not_found` / `intervention_not_found` / `file_not_found` / `backend_not_found` | 资源不存在 |
| 409 | `invalid_run_transition` / `replay_diverged` / `continue_not_supported` / `intervention_already_answered` / `run_not_stale` / `process_alive` / `legacy_events_not_streamable` | 状态转换、恢复、人工介入或事件协议冲突 |
| 410 | `process_gone` / `cursor_out_of_range` | 执行进程或事件游标已不可用 |
| 413 | `request_too_large` | 请求体超过 1 MiB |
| 422 | `validation_failed` / `file_not_previewable` | 字段、参数或文件类型不合约 |
| 500 | `atomic_write_failed` / `internal_error` | 服务端持久化或未分类错误 |
| 503 | `diagnostic_start_failed` | Backend 诊断进程无法启动 |

## 二、公共数据类型

### RunSummary

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| run_id | string | 是 | 完整 Run ID |
| working_directory | string | 是 | `runs_index.jsonl` 中记录的真实绝对工作目录；旧 Run 缺少有效映射时回退为 `lf_<pwd-path>` 分组名 |
| loop | string/null | 是 | Loop 名；unreadable 时无法证明则为 null |
| status | string | 是 | `running/waiting_input/cancelling/cancelled/done/failed/stopped/stale/unreadable`；stopped 仅 legacy |
| current_phase | string/null | 是 | 最近聚合 Phase title |
| created | string/null | 是 | 创建时间；unreadable 时无法证明则为 null |
| started_at | string/null | 是 | 执行开始时间 |
| finished_at | string/null | 是 | 结束时间 |
| updated_at | string/null | 是 | 元数据更新时间；legacy 可为 null |
| duration_ms | integer/null | 是 | 服务端派生耗时 |
| iteration_count | integer | 是 | 聚合图最大回边次数 |
| error_summary | string/null | 是 | 错误摘要 |
| parse_error | string/null | 是 | status=unreadable 时为 JSON 解析异常摘要，格式 `line {line}, column {column}: {message}`；其他状态为 null |
| execution_epoch | integer/null | 是 | 当前执行 fencing token；legacy/unreadable 无法证明时为 null |
| allowed_actions | string[] | 是 | `stop/recover_retry/recover_continue/respond/rerun/reconcile` 的允许子集；`recover_retry` 是兼容 action 名，表示默认 recover/retry 入口，不对应单独能力字段 |

### RunDetail

`RunSummary` 的全部字段，加：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| args | object/null | 是 | 启动参数；unreadable 且无法解析时为 null |
| state | object/null | 是 | 当前 Run 级 state；缺失为 null |
| graph | PhaseGraph | 是 | 聚合 Phase 图 |
| occurrences | PhaseOccurrence[] | 是 | Phase 实际进入序列 |
| calls | AgentCallSummary[] | 是 | 可明确关联的 Calls |
| interventions | InterventionSummary[] | 是 | Run 的人工输入请求，按 created_at 升序 |
| unattributed_count | integer | 是 | legacy 无法证明归属的事件数 |
| malformed_count | integer | 是 | v2 不合约事件数 |

### PhaseGraph

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nodes | PhaseNode[] | 是 | 空图为空数组 |
| edges | PhaseEdge[] | 是 | 空图为空数组 |
| current_phase_id | string/null | 是 | 无当前 Phase 时为 null |

PhaseNode：`phase:string`、`occurrence_count:integer >= 1`、`is_current:boolean`，全部必填。

PhaseEdge：`from:string`、`to:string`、`count:integer >= 1`、`is_backedge:boolean`，全部必填。

### PhaseOccurrence

| 字段 | 类型 | 必填 |
|------|------|------|
| phase_id | string | 是 |
| phase | string | 是 |
| occurrence | integer | 是 |
| started_at | string/null | 是；legacy 无时间证据时为 null |
| ended_at | string/null | 是 |
| call_ids | string[] | 是 |

### AgentCallSummary

| 字段 | 类型 | 必填 |
|------|------|------|
| call_id | string | 是 |
| phase_id | string | 是 |
| session | string/null | 是 |
| status | string | 是 | `pending/running/succeeded/failed/retrying/waiting_input/blocked` |
| started_at | string/null | 是 |
| finished_at | string/null | 是 |
| exit_code | integer/null | 是 |
| backend | string/null | 是 |
| model | string/null | 是 |
| input_digest | string/null | 是；legacy Call 为 null |

### InterventionSummary

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| request_id | string | 是 | Run 内唯一请求 ID |
| key | string | 是 | workflow 稳定请求键 |
| prompt | string | 是 | 向用户展示的问题 |
| schema | object/null | 是 | 回答 JSON Schema；null 表示任意 JSON 值 |
| status | string | 是 | `pending/answered/closed` |
| call_id | string/null | 是 | 关联 Agent Call |
| resume_mode | string | 是 | `replay` 或 `continue` |
| can_continue_session | boolean | 是 | session 和 backend capability 均满足 continue 条件 |
| response | any | 条件必填 | status=answered 时必填；其他状态不返回该字段 |
| created_at | string | 是 | 请求创建时间 |
| responded_at | string/null | 是 | 回答时间 |

### InterventionSummary vNext

Agent structured intervention vNext 将替代 `schema`/任意 JSON response 形态。迁移完成后 read model 使用：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| request_id | string | 是 | Run 内唯一请求 ID |
| source | string | 是 | `workflow` 或 `agent` |
| key | string | 是 | 稳定请求键；workflow source 下参与 replay 对齐 |
| prompt | string | 是 | 向用户展示的问题 |
| options | string[] | 是 | Agent/workflow 提供的预设选项；可为空 |
| allow_custom | boolean | 是 | false 时 response 必须属于 options；true 时可为任意非空 string |
| status | string | 是 | `pending/answered/closed` |
| call_id | string/null | 是 | 关联 Agent Call；workflow source 为 null |
| resume_mode | string | 是 | `replay` 或 `continue` |
| can_continue_session | boolean | 是 | session 和 backend capability 均满足 continue 条件 |
| response | string | 条件必填 | status=answered 时必填；其他状态不返回该字段 |
| created_at | string | 是 | 请求创建时间 |
| responded_at | string/null | 是 | 回答时间 |

## 三、Runs

### `GET /runs`

Query：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string[] | 否 | 重复 query；Run status |
| loop | string | 否 | 精确 Loop 名 |
| q | string | 否 | 匹配 run_id 或 Loop 名 |
| limit | integer | 否 | 1..200 |
| cursor | string | 否 | 上页 next_cursor |

200：

```json
{"items": [], "next_cursor": null}
```

错误：422 `validation_failed`。

### `GET /runs/{run_id}`

输入：path `run_id`。200：`RunDetail`。错误：404 `run_not_found`。

### `POST /runs`

| 字段 | 类型 | 必填 | 默认 | 约束 |
|------|------|------|------|------|
| loop | string | 是 | — | 非空 Loop 名 |
| args | object | 否 | `{}` | JSON object |
| backend | string/null | 否 | null | 已知 Backend 名或 null=auto |
| model | string/null | 否 | null | 非空字符串或 null |
| mock | string/null | 否 | null | `bash/auto/null` |
| from_phase | string/null | 否 | null | 声明的 Phase title 或 null |
| only_phase | string/null | 否 | null | 声明的 Phase title 或 null；非 null 时服务端令有效 from_phase 等于该值；请求同时传非同值 from_phase 返回 422 |
| working_directory | string/null | 否 | null | run 的显式工作目录（ADR-0042）；非 null 时必须是已存在的目录的绝对路径，否则 422（details 指明 `not_absolute` / `not_found` / `not_a_directory`）；null 时为进程 cwd（向后兼容） |

201：`RunSummary`，同时设置 `Location: /api/v1/runs/{run_id}`。

错误：404 `loop_not_found`；409 `invalid_run_transition`；422 `validation_failed`。

### `POST /runs/{run_id}/stop`

无 body。仅 `running` 或 `waiting_input` 可调用。200：status=`cancelled` 的 `RunSummary`。running Run 先持久化 cancelling，再终止已验证身份的进程组；waiting_input 不要求 PID，pending intervention request 保留，后续可通过 `respond` 恢复同一 Run。

错误：404 `run_not_found`；409 `invalid_run_transition`；500 `atomic_write_failed`。取消意图成功落盘后进程恰好消失，仍返回 200 cancelled，不返回半完成错误。

### `POST /runs/{run_id}/recover`

failed Run 或存在可重放取消边界的 cancelled Run 可调用。恢复沿用原 Run 的 loop、args、backend、model 和其他执行选项，不接受覆盖：

| 字段 | 类型 | 必填 | 默认 | 约束 |
|------|------|------|------|------|
| mode | string | 是 | — | `retry` 或 `continue`；retry 是默认恢复路径，continue 仅在 durable session 和取消/失败点都允许时可用 |

200：相同 run_id、status=running、execution_epoch 已递增的 `RunSummary`。

错误：404 `run_not_found`；409 `invalid_run_transition`、`replay_diverged` 或 `continue_not_supported`；422 `validation_failed`。对 atomic/isolated worker 取消点执行 `mode=continue` 返回 `continue_not_supported`；不得静默降级为 retry。

### `GET /runs/{run_id}/interventions`

200：`{"items": InterventionSummary[]}`。错误：404 `run_not_found`。

### `POST /runs/{run_id}/interventions/{request_id}/response`

Body：

```json
{"response": true}
```

只允许字段 `response`，其值按请求 schema 校验。成功后 response 不可修改，服务自动恢复相同 run_id。Run 为 `waiting_input`，或 Run 已 `cancelled` 但 request 仍为 pending 时均可提交；后者表示用户取消了等待中的 execution attempt，但没有关闭该人工输入请求。

200：status=running、execution_epoch 已递增的 `RunSummary`。

前置条件错误由 application command 保证副作用边界：

| 错误 | HTTP/code | 副作用边界 |
|------|-----------|------------|
| response 不符合 request schema 或 body 不合约 | 422 `validation_failed` | response 不落盘；不启动恢复 worker |
| request 不存在 | 404 `intervention_not_found` | Run 和 request 集合不变；不启动恢复 worker |
| request 已 answered | 409 `intervention_already_answered` | 原 response 不覆盖；不重复启动恢复 worker |
| Run 当前不允许 respond | 409 `invalid_run_transition` | request 不变；不启动恢复 worker |

response 持久化成功后，后续恢复 worker/agent 失败按普通 Run execution failure 表达，不作为 Intervention 特殊状态建模。

错误：404 `run_not_found` 或 `intervention_not_found`；409 `invalid_run_transition`、`intervention_already_answered`、`replay_diverged` 或 `continue_not_supported`；422 `validation_failed`。

### `POST /runs/{run_id}/interventions/responses` vNext

批量回答同一 Run 当前 pending requests。Body：

```json
{
  "responses": [
    {"request_id": "scope-1", "response": "扩大"},
    {"request_id": "note-1", "response": "重点看最近两年的资料"}
  ]
}
```

约束：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| responses | object[] | 是 | 非空数组；同一 request_id 不得重复 |
| responses[].request_id | string | 是 | Run 内 request ID |
| responses[].response | string | 是 | 非空 string；按 request options/allow_custom 校验 |

成功语义：all-or-nothing 持久化全部 response，追加对应 `intervention_responded` 事件，然后只启动一次恢复 worker。200：status=running、execution_epoch 已递增的 `RunSummary`。

前置条件错误由 application command 保证 all-or-nothing 副作用边界：

| 错误 | HTTP/code | 副作用边界 |
|------|-----------|------------|
| body 不合约、response 为空、response 不符合 options/allow_custom | 422 `validation_failed` | 所有 responses 均不落盘；不启动恢复 worker |
| 任一 request 不存在 | 404 `intervention_not_found` | 所有 responses 均不落盘；不启动恢复 worker |
| 任一 request 已 answered | 409 `intervention_already_answered` | 不覆盖既有 response；其他 responses 也不落盘；不启动恢复 worker |
| Run 当前不允许 respond | 409 `invalid_run_transition` | 所有 requests 不变；不启动恢复 worker |

response 持久化成功后，后续恢复 worker/agent 失败按普通 Run execution failure 表达，不作为 Intervention 特殊状态建模。

错误：404 `run_not_found` 或 `intervention_not_found`；409 `invalid_run_transition`、`intervention_already_answered`、`replay_diverged` 或 `continue_not_supported`；422 `validation_failed`。

### `POST /runs/{run_id}/rerun`

无 body。201：新 run_id 的 `RunSummary`，设置新 Location。源 Run 不变。

错误：404 `run_not_found`；409 `invalid_run_transition`。

### `POST /runs/{run_id}/reconcile`

无 body。200：相同 run_id、status=failed 的 `RunSummary`。

错误：404 `run_not_found`；409 `run_not_stale` 或 `process_alive`；500 `atomic_write_failed`。

## 四、Run 事件

### `GET /runs/{run_id}/events`

Query：`last_event_id`，integer >= 0，默认 0。

正常响应为 SSE。每个 v2 事件使用：

```text
id: 12
event: run_event
data: {"version":2,"event_id":12,"type":"agent_done",...}

```

已结束 Run 完成重放后发送并关闭：

```text
id: 12
event: stream_end
data: {"last_event_id":12}

```

建立连接前错误使用通用 JSON 错误信封：404 `run_not_found`；409 `legacy_events_not_streamable`；410 `cursor_out_of_range`，`error.details.max_event_id` 为当前最大值；422 `validation_failed`。

连接建立后 reader 失败，发送并关闭：

```text
event: stream_error
data: {"code":"event_read_failed","last_event_id":12}

```

Legacy Run 请求本 SSE 端点时返回 409 `legacy_events_not_streamable`，`error.details.legacy_endpoint` 为 `/api/v1/runs/{run_id}/legacy-events`。Legacy Run 通过该端点一次性读取，不提供精确 SSE 游标。

### `GET /runs/{run_id}/legacy-events`

200：

```json
{"items": [], "unattributed_count": 0, "malformed_count": 0}
```

错误：404 `run_not_found`。

### `GET /runs/{run_id}/file-changes`

200：

```json
{"items": [{"seq": 1, "phase": "Plan", "phase_id": "plan-1", "ts": "...", "changes": [{"path": "data/raw.json", "action": "created", "size": 1024}]}], "count": 1}
```

按 seq 升序返回 run 的全部文件变化记录；无 `file_changes.jsonl` 的 legacy Run 返回空列表。

错误：404 `run_not_found`。

### `GET /runs/{run_id}/file?path={relative_path}`

读取 run 工作目录（ADR-0042）内单个文件的内容，供 WebUI 文件预览。

200：

```json
{
  "path": "src/main.py",
  "media_type": "text/x-python",
  "content": "...",
  "size": 1200,
  "read_only": true
}
```

限制：path 必须是相对 POSIX 路径；resolve 后仍在 run 的 working_directory 内；文本预览上限 1 MiB；只读。

错误：403 `path_forbidden`；404 `run_not_found`/`file_not_found`；422 `file_not_previewable`。

## 五、Loops 与文件

### `GET /loops`

Query：可选 `q`、`limit`、`cursor`。200：

```json
{
  "items": [{
    "name": "hello",
    "description": "Example",
    "agent_count": 1,
    "triggers": [],
    "valid": true,
    "error_summary": null
  }],
  "next_cursor": null
}
```

错误：422 `validation_failed`。

### `GET /loops/{loop_name}`

200 `LoopDetail`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | Loop 名 |
| description | string | 是 | loop.md description |
| valid | boolean | 是 | 声明是否可解析 |
| error_summary | string/null | 是 | valid=false 的解析摘要 |
| triggers | object[] | 是 | loop.md triggers 原始结构 |
| resources | object[] | 是 | loop.md resources 原始结构 |
| environment | string/null | 是 | 声明的环境文件相对路径 |
| files | LoopFileSummary[] | 是 | 允许预览的目录树平铺列表 |
| agents | AgentDefinitionSummary[] | 是 | Agent 摘要 |
| runs | RunSummary[] | 是 | 最近 20 个关联 Runs，按 created 降序 |
| declared_phases | object[] | 否 | loop.md `meta.phases` 声明（ADR-0040），`[{title, detail}]` |
| declared_args | object[] | 否 | loop.md `meta.args` 声明（BR-047），`[{name, default, description, required}]`；无声明时缺省或空列表 |

LoopSummary 在列表接口中同样携带 `declared_phases` / `declared_args`（可选字段），供 New Run 对话框预填。

LoopFileSummary：`path:string`、`media_type:string/null`、`size:integer`、`previewable:boolean`，全部必填。

AgentDefinitionSummary：`name:string`、`description:string`、`path:string`，全部必填。

错误：404 `loop_not_found`。

### `GET /loops/{loop_name}/file?path={relative_path}`

200：

```json
{
  "path": "workflow.py",
  "media_type": "text/x-python",
  "content": "def run(...): ...",
  "size": 1200,
  "read_only": true
}
```

限制：path 必须是相对 POSIX 路径；resolve 后仍在 Loop 根目录；文本预览上限 1 MiB。

错误：403 `path_forbidden`；404 `loop_not_found/file_not_found`；422 `file_not_previewable`。

## 六、Queue

### `GET /queue`

Query：`limit` integer 1..200、`cursor` string，均可选。200：分页 queue items，字段为 `task_id:string`、`loop:string`、`args:object`、`resources:object`、`priority:integer`、`created:string`、`status:string`（pending/deferred/superseded）、`status_reason:string|null`、`superseded_by:string|null`、`blocked_resources:string[]`，全部必填；外层为 `items` 和 `next_cursor`。

错误：422 `validation_failed`。

### `POST /queue`

| 字段 | 类型 | 必填 | 默认 | 约束 |
|------|------|------|------|------|
| loop | string | 是 | — | 非空且已发现的 Loop 名 |
| args | object | 否 | `{}` | JSON object |
| resources | object | 否 | `{}` | key/value 均为非空字符串 |
| priority | integer | 否 | 5 | 0..100 |

201：完整 queue item 和 Location。错误：404 `loop_not_found`；422 `validation_failed`。

## 七、Backends

### `GET /backends`

200：

```json
{
  "items": [{
    "name": "kimi",
    "status": "available",
    "reason": null,
    "cli_path": "/usr/local/bin/kimi",
    "version": "1.0.0",
    "transport": "cli",
    "capabilities": {
      "native_goal": true,
      "structured_output": false,
      "native_skills": true,
      "resume_session": true,
      "durable_session_id": true
    },
    "diagnosed_at": null
  }]
}
```

`version` 无法探测时必须为 null，UI 表示由前端规范决定。

`resume_session` 表示 backend 接受已有 session ID；`durable_session_id` 表示该 ID 可在失败或进程退出后继续使用，并能在 loopflow 恢复所需时机获得。只有两者均为 true、目标 Call 已持久化 session_id，且失败/取消点未处于原子或隔离 worker 禁止边界时，Run 才允许 `recover_continue`。

### `POST /backends/{backend_name}/diagnostics`

Body：`{"timeout_ms":5000}`，范围 100..30000。

200：

```json
{
  "name": "kimi",
  "status": "unavailable",
  "reason": "timeout",
  "exit_code": null,
  "stdout": "",
  "stderr": "diagnostic timed out after 5000ms",
  "diagnosed_at": "2026-07-18T22:00:00Z"
}
```

stdout/stderr 在响应前执行最小 secret redaction：对大小写不敏感的键 `token|password|secret|api_key`，匹配 `KEY` 后可选空白、分隔符 `=` 或 `:`、可选空白，以及连续到空白/分号/逗号/行尾的非空值；保留原键和分隔符，将值替换为固定文本 `[REDACTED]`。例如 `token=lf-secret-123; connection failed` 必须变为 `token=[REDACTED]; connection failed`。其他脱敏规则可扩展，但不得改变该最小规则的输出。

错误：404 `backend_not_found`；422 `validation_failed`；503 `diagnostic_start_failed`。

### `GET /system/meta`

200：`{"version": "0.20.0"}`——与 `loopflow.__version__` 一致，供 WebUI 显示运行中 server 的版本。

### `POST /system/pick-directory`

在 server 所在机器上调起操作系统原生目录选择器（供 WebUI New Run 对话框的 Browse 按钮使用，ADR-0042）。

200（选中）：`{"path": "/absolute/dir", "cancelled": false}`（返回绝对路径）
200（取消）：`{"path": null, "cancelled": true}`

平台支持：macOS（osascript `choose folder`）；其他平台返回 501 `not_supported`，前端回退为手动输入。

错误：501 `not_supported`。

## 八、服务启动约束

`loopflow web` 默认 `host=127.0.0.1`。非 loopback host 必须同时设置 `allow_remote=true`，否则 CLI 非零退出且不创建监听 socket。远程绑定成功时 stderr 必须输出远程暴露警告。该约束属于启动接口，不通过 HTTP 修改。
