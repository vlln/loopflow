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
| 409 | `invalid_run_transition` / `replay_diverged` / `continue_not_supported` / `intervention_already_answered` / `run_not_stale` / `run_in_grace` / `process_alive` / `legacy_events_not_streamable` | 状态转换、恢复、人工介入或事件协议冲突 |
| 410 | `process_gone` / `cursor_out_of_range` | 执行进程或事件游标已不可用 |
| 413 | `request_too_large` | 请求体超过 1 MiB |
| 422 | `validation_failed` / `file_not_previewable` | 字段、参数或文件类型不合约 |
| 500 | `atomic_write_failed` / `file_read_failed` / `internal_error` | 服务端持久化、已校验文件读取或未分类错误 |
| 503 | `diagnostic_start_failed` | Backend 诊断进程无法启动 |

`agent_intervention_not_supported` 是 Agent 输出处理期间产生的异步 Call/Run failure code，不是 HTTP error envelope code。对应 Run 进入 `failed`，`error_summary` 以该稳定 code 标识失败并附带改用 workflow `intervene()` 或可续接 backend 的行动提示；最初的 `POST /runs` 仍已返回 201。

## 二、公共数据类型

### RunSummary

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| run_id | string | 是 | 完整 Run ID |
| working_directory | string | 是 | `runs_index.jsonl` 中记录的真实绝对工作目录；旧 Run 缺少有效映射时回退为 `lf_<group-path>` 分组名 |
| loop | string/null | 是 | Loop 名；unreadable 时无法证明则为 null |
| status | string | 是 | `running/waiting_input/cancelling/cancelled/done/failed/stopped/stale/unreadable`；stopped 仅 legacy |
| created | string/null | 是 | 创建时间；unreadable 时无法证明则为 null |
| started_at | string/null | 是 | 执行开始时间 |
| finished_at | string/null | 是 | 结束时间 |
| updated_at | string/null | 是 | 元数据更新时间；legacy 可为 null |
| duration_ms | integer/null | 是 | 服务端派生耗时 |
| error_summary | string/null | 是 | 错误摘要 |
| error_category | string/null | 是 | `auth/quota/transient/task/unknown`；无分类时为 null |
| error_traceback | string/null | 是 | 可用的失败 traceback；无记录或 unreadable 时为 null |
| parse_error | string/null | 是 | status=unreadable 时为 JSON 解析异常摘要，格式 `line {line}, column {column}: {message}`；其他状态为 null |
| execution_epoch | integer/null | 是 | 当前执行 fencing token；legacy/unreadable 无法证明时为 null |
| stale_since | string/null | 是 | status=stale 时为首次判定 stale 的时间；其他状态为 null |
| stale_grace_remaining_seconds | number/null | 是 | status=stale 时为 24h 宽限期剩余秒数，最小 0；其他状态为 null |
| allowed_actions | string[] | 是 | `stop/recover_retry/recover_continue/respond/rerun/reconcile` 的允许子集；`recover_retry` 是兼容 action 名，表示默认 recover/retry 入口，不对应单独能力字段 |
| transport | string | 是 | `cli` 或 `acp`；默认 `cli`，旧 Run 缺失时回退为 `cli` |

### RunDetail

`RunSummary` 的全部字段，加：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| args | object/null | 是 | 启动参数；unreadable 且无法解析时为 null |
| state | object/null | 是 | 当前 Run 级 state；缺失为 null |
| agent_graph | AgentGraph | 是 | 由结构化 Agent 事件涌现的 Call 实例图 |
| calls | AgentCallSummary[] | 是 | 可明确关联的 Calls |
| events | RunEvent[] | 是 | 结构合法的 v2 事件及原始 legacy 时间线事件 |
| interventions | InterventionSummary[] | 是 | Run 的人工输入请求，按 created_at 升序 |
| unattributed | RunEvent[] | 是 | 结构合法但无法证明 Call 归属的 legacy 事件 |
| malformed | MalformedEvent[] | 是 | 不合约事件及可观测原因 |
| unattributed_count | integer | 是 | legacy 无法证明归属的事件数 |
| malformed_count | integer | 是 | invalid JSON、非 object、unsupported version 或 v2 不合约事件总数 |

`unattributed_count == len(unattributed)`，`malformed_count == len(malformed)`。Malformed event 不得同时出现在 `events`、`calls`、`agent_graph` 或 `unattributed`。

### AgentGraph

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nodes | AgentNode[] | 是 | 每个 call_id 至多一个节点；空图为空数组 |
| edges | AgentEdge[] | 是 | 空图为空数组 |
| current | string/null | 是 | 最近开始的 call_id；无 Agent Call 时为 null |

AgentNode：`id:string`、`label:string`、`agent_def:string/null`、`status:string`，全部必填。`id` 是 call_id；label 缺失或 trim 后为空时回退为 id；status 为 `running/done/failed`。

AgentEdge：`from:string`、`to:string`、`kind:string`，全部必填；from/to 均引用现有 node id，kind 为 `sequential/fork/join`。

### RunEvent 与 MalformedEvent

RunEvent 的 v2 字段为 `version:2`、`event_id:integer >= 1`、`type:string`、`ts:string`、`run_id:string`、`payload:object`；Agent 关联事件还必须含非空 `call_id:string`。Agent 关联事件指 type 以 `agent_` 开头，或属于 `tool_call/tool_call_update/usage_update/message/retry`。Legacy event 保持原 object 字段，不补造 call_id。

MalformedEvent 固定为：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| reason | string | 是 | `invalid_json/non_object/unsupported_version/invalid_envelope/missing_call_id` |
| raw | any | 是 | 可解析行保留原 JSON 值；invalid_json 为 UTF-8 replacement 解码的原始行 |

### AgentCallSummary

| 字段 | 类型 | 必填 |
|------|------|------|
| call_id | string | 是 |
| session | string/null | 是 |
| status | string | 是 | `pending/running/succeeded/failed/retrying/waiting_input/blocked` |
| started_at | string/null | 是 |
| finished_at | string/null | 是 |
| exit_code | integer/null | 是 |
| backend | string/null | 是 |
| model | string/null | 是 |
| input_digest | string/null | 是；legacy Call 为 null |

### InterventionSummary

新写入 request 使用以下结构；read model 将 legacy 文件补齐兼容默认值后也统一返回该结构，因此不产生两套不可判别的响应类型：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| request_id | string | 是 | Run 内唯一请求 ID |
| source | string | 是 | `workflow` 或 `agent` |
| key | string | 是 | 稳定请求键；workflow source 下参与 replay 对齐 |
| prompt | string | 是 | 向用户展示的问题 |
| schema | object/null | 是 | 回答 JSON Schema；null 表示任意 JSON 值 |
| options | string[] | 是 | Agent/workflow 提供的预设选项；可为空 |
| allow_custom | boolean | 是 | false 时 response 必须属于 options；true 时可为任意非空 string |
| status | string | 是 | `pending/answered/closed` |
| request_group_id | string/null | 是 | 同一次 Agent 控制输出的稳定组 ID；workflow request 为 null |
| request_index | integer | 是 | 在 request_group_id 内的零基顺序；workflow request 为 0 |
| call_id | string/null | 是 | 关联 Agent Call；workflow source 为 null |
| session_id | string/null | 是 | Agent continue 使用的 durable backend session；workflow source 为 null |
| resume_mode | string | 是 | `replay` 或 `continue` |
| can_continue_session | boolean | 是 | session 和 backend capability 均满足 continue 条件 |
| response | any | 条件必填 | status=answered 时必填且 immutable；Agent source 时为 string，workflow source 时按 schema |
| created_at | string | 是 | 请求创建时间 |
| responded_at | string/null | 是 | 回答时间 |
| timeout_seconds | number/null | 是 | 仅 workflow request 可声明；null 表示无超时 |
| response_source | string | 条件必填 | status=answered 时为 `human/default/timeout_default`；legacy 缺省归一化为 `human` |

`response` 是由 `source` 判别的联合类型：`source=agent` 时必须是非空 string，并满足 options/allow_custom；`source=workflow` 时可以是任意 JSON 值，但 schema 非 null 时必须通过该 schema。`status!=answered` 时不得返回 response；`status=answered` 时必须返回，即使 workflow response 是 JSON null。

旧记录缺少 `source/options/allow_custom/timeout_seconds` 时按 Spec v18 的兼容默认值归一化。旧 Agent request 缺少 `request_group_id`/`request_index` 时，read model 以 `(call_id, session_id)` 派生 group，并按 `(created_at, request_id)` 给出稳定顺序；旧 workflow request 归一化为 `request_group_id=null`、`request_index=0`。legacy 恢复证据标记为 unverified，不改写旧文件。

### FilePreview

文本与 raw 预览共享字段 `path:string`、`media_type:string/null`、`size:integer`、`read_only:true`；raw 分支的 media_type 必须是 string：

| 分支 | content | encoding | raw_url |
|------|---------|----------|---------|
| UTF-8 文本（不超过 1 MiB） | string | 缺省 | 缺省 |
| png/jpg/jpeg/gif/svg/webp/bmp/ico/pdf（不超过 50 MiB） | null | 固定 `raw` | 同一资源 raw 端点的 URL |

`raw_url` 仅是只读内容 URL，不放入业务 schema、Run digest 或 Agent prompt。

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
| working_directory | string/null | 否 | null | run 的显式工作目录（ADR-0042）；非 null 时必须是已存在目录的绝对路径，否则 422（details 指明 `not_absolute` / `not_found` / `not_a_directory`）；null 时使用下述框架隔离目录 |
| transport | string | 否 | cli | `cli` 或 `acp`；`acp` 路由到 ACP 后端（AcpSdkBackend），加载可选依赖 agent-client-protocol，缺失时报错提示安装 extra `[acp]`（对应 422 `validation_failed` 或 503） |
| append_prompt | string | 否 | `""` | UTF-8 编码不超过 65536 bytes；空字符串等价于缺省；作为不受信任的用户 prompt 段冻结进 execution_options，参与 Call input_digest，不进入 system prompt |

`working_directory=null` 或缺省时，服务端先按 server cwd 确定 storage group/run_dir，再创建 `run_dir/work` 作为 actual working_directory；该实际路径写入 `run.json` 和 `runs_index.jsonl`。

201：`RunSummary`，同时设置 `Location: /api/v1/runs/{run_id}`。

错误：404 `loop_not_found`；409 `invalid_run_transition`；422 `validation_failed`。append_prompt 超限时 `error.details.field="append_prompt"`，且不创建 Run、不调用 backend。

### `POST /runs/{run_id}/stop`

无 body。仅 `running` 或 `waiting_input` 可调用。200：status=`cancelled` 的 `RunSummary`。running Run 先持久化 cancelling，再终止已验证身份的进程组；waiting_input 不要求 PID，pending intervention request 保留，后续可通过 `respond` 恢复同一 Run。

错误：404 `run_not_found`；409 `invalid_run_transition`；500 `atomic_write_failed`。取消意图成功落盘后进程恰好消失，仍返回 200 cancelled，不返回半完成错误。

### `POST /runs/{run_id}/recover`

failed Run 或存在可重放取消边界的 cancelled Run 可调用。恢复沿用原 Run 的 loop、args、backend、model、append_prompt 和其他执行选项，不接受覆盖：

| 字段 | 类型 | 必填 | 默认 | 约束 |
|------|------|------|------|------|
| mode | string | 是 | — | `retry` 或 `continue`；retry 是默认恢复路径，continue 仅在 durable session 和取消/失败点都允许时可用 |

body 只允许 `mode`；包括 `append_prompt` 在内的任何额外字段均返回 422 `validation_failed`，`error.details.fields` 列出额外字段，且不修改 execution_options、不启动恢复 worker。

200：相同 run_id、status=running、execution_epoch 已递增的 `RunSummary`。

错误：404 `run_not_found`；409 `invalid_run_transition`、`replay_diverged` 或 `continue_not_supported`；422 `validation_failed`。对 atomic/isolated worker 取消点执行 `mode=continue` 返回 `continue_not_supported`；不得静默降级为 retry。

### `GET /runs/{run_id}/interventions`

200：`{"items": InterventionSummary[]}`。错误：404 `run_not_found`。

### `POST /runs/{run_id}/interventions/{request_id}/response`

这是 legacy 兼容端点，仅当目标 request 是 Run 当前唯一 pending request 时可用；存在其他 pending request 时返回 422 `validation_failed`，所有 response 均不落盘且不启动恢复 worker。新客户端统一使用批量端点。

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

### `POST /runs/{run_id}/interventions/responses`

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
| responses[].response | any | 是 | Agent source 必须是非空 string 并按 options/allow_custom 校验；workflow source 按 schema 校验，schema=null 时接受任意 JSON 值 |

成功语义：请求必须恰好覆盖该 Run 当前全部 pending requests；all-or-nothing 持久化全部 response，追加对应 `intervention_responded` 事件，然后只启动一次恢复 worker。Agent requests 按 `request_group_id` 分组、`request_index` 排序，每组构造一个仅含 `key/response` 的 `input_received` 信封并继续其原 `call_id/session_id`；同一次 workflow 重放必须到达全部 continue targets。200：status=running、execution_epoch 已递增的 `RunSummary`。

前置条件错误由 application command 保证 all-or-nothing 副作用边界：

| 错误 | HTTP/code | 副作用边界 |
|------|-----------|------------|
| body 不合约或 response 字段缺失；Agent response 是空 string/不符合 options/allow_custom；workflow response 不符合非 null schema | 422 `validation_failed` | 所有 responses 均不落盘；不启动恢复 worker |
| request_id 重复，或未恰好覆盖 Run 当前全部 pending requests | 422 `validation_failed` | 所有 responses 均不落盘；不启动恢复 worker |
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

错误：404 `run_not_found`；409 `run_not_stale` 或 `process_alive`；500 `atomic_write_failed`。进程探活确认死亡即清理为 `failed`（ADR-0046 修订：宽限期不阻塞 reconcile，`run_in_grace` 保留于错误映射表仅为向后兼容，不再触发）。

## 四、Run 事件

### `GET /runs/{run_id}/events`

Query：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| last_event_id | integer >= 0 | 否 | 0 | `run_event` topic 最后收到的 event_id |
| last_file_changes_id | integer >= 0 | 否 | 0 | `file_changes` topic 最后收到的 seq |

正常响应为 SSE。每个 v2 事件使用：

```text
id: 12
event: run_event
data: {"version":2,"event_id":12,"type":"agent_done",...}

id: 7
event: file_changes
data: {"seq":7,"call_id":"call-3","label":"review","ts":"...","changes":[]}

```

已结束 Run 完成重放后发送并关闭：

```text
event: stream_end
data: {"last_event_id":12,"last_file_changes_id":7}

```

建立连接前错误使用通用 JSON 错误信封：404 `run_not_found`；409 `legacy_events_not_streamable`；410 `cursor_out_of_range`，run_event 游标越界时 `error.details.max_event_id` 为当前最大值；422 `validation_failed`。

连接建立后 reader 失败，发送并关闭：

```text
event: stream_error
data: {"code":"event_read_failed","last_event_id":12}

```

`file_changes` 游标越界只发送该 topic 的 `stream_error`，data 含 `topic="file_changes"`、`code="cursor_out_of_range"`、`max_file_changes_id`；不得关闭仍可继续的 run_event topic。任一 topic 的底层 reader 在连接建立后发生 I/O 失败时，发送不含 topic 的 `stream_error`，data 含 `code="event_read_failed"` 和当前 `last_event_id`，随后关闭整个连接；失败前已发送的数据不得重复。跨 topic 不承诺全局顺序。

Legacy Run 请求本 SSE 端点时返回 409 `legacy_events_not_streamable`，`error.details.legacy_endpoint` 为 `/api/v1/runs/{run_id}/legacy-events`。Legacy Run 通过该端点一次性读取，不提供精确 SSE 游标。

### `GET /runs/{run_id}/legacy-events`

200：

```json
{"items": [], "unattributed": [], "malformed": [], "unattributed_count": 0, "malformed_count": 0}
```

错误：404 `run_not_found`。

### `GET /runs/{run_id}/file-changes`

200：

```json
{"items": [{"seq": 1, "call_id": "call-1", "label": "planner", "ts": "...", "changes": [{"path": "data/raw.json", "action": "created", "size": 1024}]}], "count": 1}
```

按 seq 升序返回 run 的全部文件变化记录；无 `file_changes.jsonl` 的 legacy Run 返回空列表。

每条 FileChangeRecord 的 `seq:integer >= 1`、`call_id:string`、`label:string`、`ts:string`、`changes:FileChange[]` 均必填。label 只用于显示，不作为关联键；changes 元素含 `path:string`、`action:created/modified/deleted`，created/modified 时 `size:integer` 必填，modified/deleted 时 `prev_size:integer` 必填。

错误：404 `run_not_found`。

### `GET /runs/{run_id}/file?path={relative_path}`

读取 run 工作目录（ADR-0042）内单个文件的内容，供 WebUI 文件预览。

200：`FilePreview`。文本示例：

```json
{
  "path": "src/main.py",
  "media_type": "text/x-python",
  "content": "...",
  "size": 1200,
  "read_only": true
}
```

raw 示例：

```json
{
  "path": "figures/chart.png",
  "media_type": "image/png",
  "content": null,
  "encoding": "raw",
  "raw_url": "/api/v1/runs/abc/file/raw?path=figures/chart.png",
  "size": 2048,
  "read_only": true
}
```

限制：path 必须是相对 POSIX 路径；resolve 后仍在 run 的 working_directory 内；文本预览上限 1 MiB；只读。

错误：403 `path_forbidden`；404 `run_not_found`/`file_not_found`；422 `file_not_previewable`；500 `file_read_failed`。

### `GET /runs/{run_id}/file/raw?path={relative_path}`

只读返回 Run actual working_directory 内允许预览的图片或 PDF bytes。`path` 采用与 preview 端点相同的相对 POSIX 路径和 resolve 边界；允许扩展名为 png/jpg/jpeg/gif/svg/webp/bmp/ico/pdf，大小不超过 50 MiB。

media type 映射固定为：png=`image/png`；jpg/jpeg=`image/jpeg`；gif=`image/gif`；svg=`image/svg+xml`；webp=`image/webp`；bmp=`image/bmp`；ico=`image/x-icon`；pdf=`application/pdf`。不得依赖平台 MIME 数据库产生不同结果。

200：body 为完整原始 bytes；`Content-Type` 使用上述固定映射，`Content-Length` 为完整长度，`Cache-Control: no-store`。服务端必须在发送 200 header 前完成读取；读取失败不得返回部分 bytes。

错误：403 `path_forbidden`；404 `run_not_found`/`file_not_found`；422 `file_not_previewable`；500 `file_read_failed`。

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
| declared_args | object[] | 否 | loop.md 顶层 `args` 声明（BR-047），`[{name, default, description, required}]`；仅在 loop.md 不存在时回退读取 workflow.py `meta.args`；无声明时缺省或空列表 |

LoopSummary 在列表接口中同样携带 `declared_args`（可选字段），供 New Run 对话框预填。LoopSummary 与 LoopDetail 均不得返回 `declared_phases`；legacy `meta.phases` 不参与 API 投影。

DeclaredArg：

| 字段 | 类型 | 必填 | 缺省 | 说明 |
|------|------|------|------|------|
| name | string | 是 | — | trim 后非空的参数名 |
| default | any | 否 | 缺省 | JSON 可表示的预填值；false、0、空字符串和 object 不得因 truthiness 丢失 |
| description | string | 否 | `""` | 参数说明 |
| required | boolean | 否 | false | 仅作为 UI 提示；空值是否提交沿用 args 编辑器规则 |

loop.md 顶层 `args` 不是数组时 `declared_args=[]`，且不得回退到 workflow.py。数组中的非 object、name 非 string 或 trim 后为空的条目静默忽略，其他合法条目保序返回；仅当 loop.md 不存在时才读取 workflow.py `meta.args` 并应用同一归一化规则。

LoopFileSummary：`path:string`、`media_type:string/null`、`size:integer`、`previewable:boolean`，全部必填。

AgentDefinitionSummary：`name:string`、`description:string`、`path:string`，全部必填。

错误：404 `loop_not_found`。

### `GET /loops/{loop_name}/file?path={relative_path}`

200：`FilePreview`，文本与 raw 分支同 Run preview 端点。文本示例：

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

错误：403 `path_forbidden`；404 `loop_not_found/file_not_found`；422 `file_not_previewable`；500 `file_read_failed`。

### `GET /loops/{loop_name}/file/raw?path={relative_path}`

只读返回 Loop 根目录内允许预览的图片或 PDF bytes。路径、允许扩展名、50 MiB 上限、200 headers 和“读取完成后才发送 header”的原子响应语义与 Run raw 端点相同。

错误：403 `path_forbidden`；404 `loop_not_found/file_not_found`；422 `file_not_previewable`；500 `file_read_failed`。

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

> 已废弃（ADR-0053）。前端不再调用此端点，改用 `GET /system/list-directory` + Web 模态目录浏览器。macOS 本地场景仍可用。

在 server 所在机器上调起操作系统原生目录选择器（供 WebUI New Run 对话框的 Browse 按钮使用，ADR-0042）。

200（选中）：`{"path": "/absolute/dir", "cancelled": false}`（返回绝对路径）
200（取消）：`{"path": null, "cancelled": true}`

平台支持：macOS（osascript `choose folder`）；其他平台返回 501 `not_supported`。

错误：501 `not_supported`。

### `GET /system/list-directory`

列出 server 端指定路径下的子目录（供 WebUI New Run 对话框的 Web 目录浏览器使用，ADR-0053）。跨平台，使用 `os.scandir`。

参数：`path`（可选，绝对路径；缺省 = server cwd）

200：`{"path": "/absolute/dir", "parent": "/absolute", "entries": [{"name": "subdir", "path": "/absolute/dir/subdir"}, ...]}`
- `entries` 只包含子目录（不含文件），按名称排序
- `parent` 为父目录绝对路径；已是根目录时为 `null`

错误：404 `file_not_found`（路径不存在）；422 `validation_failed`（相对路径 / 非目录）。

## 八、服务启动约束

`loopflow web` 默认 `host=127.0.0.1`。非 loopback host 必须同时设置 `allow_remote=true`，否则 CLI 非零退出且不创建监听 socket。远程绑定成功时 stderr 必须输出远程暴露警告。该约束属于启动接口，不通过 HTTP 修改。
