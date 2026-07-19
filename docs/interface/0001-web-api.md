---
title: loopflow Web API v1
description: 本地 WebUI 的 REST 与 SSE 接口契约，覆盖 Runs、Loops、Queue、Backends、Run 命令和事件续传。
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
| 404 | `loop_not_found` / `run_not_found` / `file_not_found` / `backend_not_found` | 资源不存在 |
| 409 | `invalid_run_transition` / `run_not_stale` / `process_alive` / `legacy_events_not_streamable` | 状态转换或事件协议冲突 |
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
| status | string | 是 | `running/done/failed/stopped/stale/unreadable` |
| current_phase | string/null | 是 | 最近聚合 Phase title |
| created | string/null | 是 | 创建时间；unreadable 时无法证明则为 null |
| started_at | string/null | 是 | 执行开始时间 |
| finished_at | string/null | 是 | 结束时间 |
| updated_at | string/null | 是 | 元数据更新时间；legacy 可为 null |
| duration_ms | integer/null | 是 | 服务端派生耗时 |
| iteration_count | integer | 是 | 聚合图最大回边次数 |
| error_summary | string/null | 是 | 错误摘要 |
| parse_error | string/null | 是 | status=unreadable 时为 JSON 解析异常摘要，格式 `line {line}, column {column}: {message}`；其他状态为 null |
| allowed_actions | string[] | 是 | `stop/resume/rerun/reconcile` 的允许子集 |

### RunDetail

`RunSummary` 的全部字段，加：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| args | object/null | 是 | 启动参数；unreadable 且无法解析时为 null |
| state | object/null | 是 | 当前 Run 级 state；缺失为 null |
| graph | PhaseGraph | 是 | 聚合 Phase 图 |
| occurrences | PhaseOccurrence[] | 是 | Phase 实际进入序列 |
| calls | AgentCallSummary[] | 是 | 可明确关联的 Calls |
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
| status | string | 是 | `pending/running/done/failed/retrying/blocked` |
| started_at | string/null | 是 |
| finished_at | string/null | 是 |
| exit_code | integer/null | 是 |
| backend | string/null | 是 |
| model | string/null | 是 |

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

201：`RunSummary`，同时设置 `Location: /api/v1/runs/{run_id}`。

错误：404 `loop_not_found`；409 `invalid_run_transition`；422 `validation_failed`。

### `POST /runs/{run_id}/stop`

无 body。200：更新后的 `RunSummary`。

错误：404 `run_not_found`；409 `invalid_run_transition`；410 `process_gone`。

### `POST /runs/{run_id}/resume`

Body 可选覆盖执行选项，不允许修改 loop/args：

| 字段 | 类型 | 必填 | 默认 | 约束 |
|------|------|------|------|------|
| backend | string/null | 否 | null | 已知 Backend 名或 null=auto |
| model | string/null | 否 | null | 非空字符串或 null |
| mock | string/null | 否 | null | `bash/auto/null` |

200：相同 run_id、status=running 的 `RunSummary`。

错误：404 `run_not_found`；409 `invalid_run_transition`；422 `validation_failed`。

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

Query：`limit` integer 1..200、`cursor` string，均可选。200：分页 queue items，字段为 `task_id:string`、`loop:string`、`args:object`、`resources:object`、`priority:integer`、`created:string`、`blocked_resources:string[]`，全部必填；外层为 `items` 和 `next_cursor`。

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
      "native_skills": true
    },
    "diagnosed_at": null
  }]
}
```

`version` 无法探测时必须为 null，UI 表示由前端规范决定。

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

## 八、服务启动约束

`loop web` 默认 `host=127.0.0.1`。非 loopback host 必须同时设置 `allow_remote=true`，否则 CLI 非零退出且不创建监听 socket。远程绑定成功时 stderr 必须输出远程暴露警告。该约束属于启动接口，不通过 HTTP 修改。
