---
title: ADR 0041 — SSE 多 topic 传输层
description: 将 SSE 从 events.jsonl 管道重构为多路复用 transport，支持 run_event 和 file_changes 等 topic 各自独立游标，解耦传输与存储
type: adr
status: proposed
created: 2026-07-23T14:00:00Z
---

# ADR 0041: SSE 多 topic 传输层

## Context

当前 SSE 是 `events.jsonl` 的直接管道延伸：

- `server.py` 的 `_events()` handler 调用 `app.replay_events(run_id, last_event_id)`，直接读 events.jsonl
- `event_id` 既是 events.jsonl 的存储序号，也是 SSE 断线恢复游标
- SSE 只推送 `run_event` 一种业务事件（外加 `stream_end`/`stream_error` 控制信号）
- 前端 `api.ts` 的 `connectRunEvents()` 只监听 `run_event` topic

这造成一个架构耦合：**任何新的实时数据源要么进 events.jsonl（污染确定性重放契约），要么不能用 SSE（被迫 REST 轮询）。**

ADR-0039（文件变化观察层）暴露了这个限制。文件变化是实时数据，适合 SSE 推送，但不应进入 events.jsonl（不参与重放）。如果 SSE 只能传输 events.jsonl 的内容，文件变化就只能走 REST 轮询——体验差且不符合实时性需求。

需要将 SSE 从"events.jsonl 管道"重构为"多路复用 transport"，使多种实时数据源可以共享同一 SSE 连接，各自独立游标，互不污染。

## Decision

### 1. SSE 是 transport，不是某个文件的管道

SSE 连接承载多个 topic，每个 topic 有独立的数据源和游标语义。SSE 协议的 `event:` 字段用于区分 topic，`id:` 字段用于 per-topic 游标。

```text
event: run_event
id: 5
data: {"version":2,"event_id":5,"type":"phase",...}

event: file_changes
id: 2
data: {"phase":"采集","phase_id":"phase-1","changes":[...]}
```

### 2. Topic 注册

| Topic | 数据源 | 游标类型 | 游标语义 | 参与重放 |
|-------|--------|---------|---------|---------|
| `run_event` | events.jsonl | event_id（整数，严格递增） | Run 内事件序号，断线后从 last_event_id 重放 | 是 |
| `file_changes` | file_changes.jsonl | seq（整数，严格递增） | Run 内文件变化记录序号，断线后从 last_file_changes_id 重放 | 否 |

未来新增实时数据源时，注册新 topic 并定义其数据源和游标语义。不需要修改 SSE 连接机制。

### 3. 连接建立与游标传递

客户端建立 SSE 连接时，通过查询参数传递每个 topic 的游标：

```
GET /api/v1/runs/<run_id>/events?last_event_id=5&last_file_changes_id=2
```

- 未提供游标的 topic 从头重放（游标 = 0）
- 服务端为每个 topic 独立 replay，按时间序交错推送
- 每个 topic 的 `id:` 字段是该 topic 的独立游标，不与其他 topic 混用

### 4. 断线重连

客户端断线重连时，分别携带每个 topic 的最后收到的 `id:`：

```
GET /api/v1/runs/<run_id>/events?last_event_id=7&last_file_changes_id=3
```

服务端：
1. 对 `run_event` topic：从 events.jsonl 重放 `event_id > 7` 的事件
2. 对 `file_changes` topic：从 file_changes.jsonl 重放序号 `> 3` 的记录
3. 继续推送两个 topic 的新增数据

游标超出可恢复范围时，该 topic 返回明确的不可恢复响应（`stream_error` 带 topic 和 code），不影响其他 topic。

### 5. 服务端实现

`_events()` handler 从单源读取改为多源合并：

```python
def _events(self, run_id, last_event_id=0, last_file_changes_id=0):
    # 初始化各 topic 的 replay 状态
    event_state = self.app.replay_events(run_id, last_event_id)
    file_state = self.app.replay_file_changes(run_id, last_file_changes_id)

    while True:
        # 推送各 topic 的 pending 数据
        for event in event_state.pending:
            self._sse("run_event", event, event["event_id"])
        for change in file_state.pending:
            self._sse("file_changes", change, change["seq"])

        if event_state.terminal and file_state.terminal:
            self._sse("stream_end", {...})
            return

        time.sleep(poll_interval)
        event_state = self.app.replay_events(run_id, event_state.cursor)
        file_state = self.app.replay_file_changes(run_id, file_state.cursor)
```

每个 topic 有独立的 cursor、terminal 状态和 replay 调用。`stream_end` 在所有 topic 都 terminal 时才发送。

### 6. 前端实现

前端 `connectRunEvents()` 扩展为多 topic 监听：

```typescript
function connectRunEvents(
  runId: string,
  cursors: { lastEventId: number; lastFileChangesId: number },
  handlers: {
    onEvent: (event: RunEvent) => void;
    onFileChanges: (change: FileChangeRecord) => void;
    onState: (state: 'live' | 'closed' | 'error') => void;
  }
): () => void {
  const url = `/api/v1/runs/${encodeURIComponent(runId)}/events`
    + `?last_event_id=${cursors.lastEventId}`
    + `&last_file_changes_id=${cursors.lastFileChangesId}`;
  const source = new EventSource(url);
  source.addEventListener('run_event', (msg) => handlers.onEvent(JSON.parse(msg.data)));
  source.addEventListener('file_changes', (msg) => handlers.onFileChanges(JSON.parse(msg.data)));
  // ...
}
```

前端维护 per-topic 的最后 `id:`，断线重连时分别传递。

### 7. file_changes.jsonl 增加序号字段

为支持 SSE 游标，`file_changes.jsonl` 每行增加 `seq` 字段（Run 内从 1 开始严格递增），与 `events.jsonl` 的 `event_id` 同理但独立计数：

```jsonl
{"seq":1,"phase":"采集","phase_id":"phase-1","ts":"...","changes":[...]}
{"seq":2,"phase":"处理","phase_id":"phase-2","ts":"...","changes":[...]}
```

`seq` 由 runtime 在追加时分配，是 file_changes topic 的 SSE 游标。不参与重放、不参与缓存命中。

## Alternatives

### 方案 A：多 topic SSE transport（采用）

- 优点：单连接多路复用，不消耗额外连接预算；SSE 协议原生 `event:` 字段支持；解耦传输与存储；未来可扩展新 topic。
- 缺点：服务端多源合并逻辑增加复杂度；per-topic 游标管理；前端需要维护多游标。

### 方案 B：双 SSE 连接（拒绝）

- 优点：实现简单，各连接独立。
- 缺点：消耗两个 HTTP 连接预算；断线重连逻辑 ×2；两连接之间无序保证；浏览器同源连接上限（HTTP/1.1 约 6 个）会被快速消耗。

### 方案 C：file_changes 进 events.jsonl（拒绝）

- 优点：无需改 SSE。
- 缺点：污染确定性重放契约（ADR-0036）；event_id 被文件变化记录消耗；SSE 游标语义混乱；大 payload 影响实时事件延迟。详见 ADR-0039 方案 A。

### 方案 D：file_changes 走 REST 轮询（拒绝）

- 优点：不动 SSE。
- 缺点：非实时，前端需要轮询或 phase 事件触发拉取；体验差；不符合"文件变化是实时数据"的定位。

### 方案 E：SSE 推送轻量信号 + REST 拉取数据（拒绝）

- 优点：SSE 只推信号不推数据，payload 小。
- 缺点：信号仍需进入 events.jsonl 才能通过现有 SSE 推送，变相污染事件流；前端需要二次请求，延迟和复杂度增加；本质是绕路而非解决问题。

## Consequences

### 正面

- SSE 成为通用实时 transport，不再绑定 events.jsonl。
- file_changes 通过 SSE 实时推送，无需轮询。
- events.jsonl 的重放契约完全不受影响。
- 未来新增实时数据源只需注册 topic，不需要新连接或改 transport。

### 负面

- 服务端 SSE handler 从单源读取改为多源合并，复杂度增加。
- 前端需要维护 per-topic 游标和多个 event handler。
- 断线重连参数从单一 `last_event_id` 扩展为多游标。
- ADR-0034 §5 的"event_id 是 SSE 断线恢复游标"需要修订为"event_id 是 run_event topic 的游标"。

### 不做的

- 不用 WebSocket 替代 SSE（ADR-0033 已决策，SSE 满足单向追加事件需求）。
- 不引入消息队列或 pub/sub 框架。
- 不承诺跨 topic 的事件顺序保证（各 topic 独立游标，按各自数据源顺序推送）。
- 不为 topic 注册引入插件机制（首版硬编码 run_event + file_changes，未来按需扩展）。

## Architecture Boundary

本 ADR 约束 `src/loopflow/presentation/web/server.py` 的 SSE handler、`src/loopflow/application/` 的 replay 查询、`web/src/api.ts` 的 EventSource 订阅，以及 `file_changes.jsonl` 的 `seq` 字段。

- server.py 的 SSE handler 支持多 topic 多游标；
- application service 为每个 topic 提供独立的 replay 查询；
- 前端按 `event:` 字段分发到各 topic handler，维护 per-topic 游标；
- file_changes.jsonl 增加 `seq` 字段作为 SSE 游标；
- events.jsonl 的 event_id 语义不变（仍是 run_event topic 的游标和重放序号）。

## Verification

不需要外部技术选型 spike。SSE 协议原生支持 `event:` 和 `id:` 字段，标准库 HTTP server 已在用。在 TEST_INFRA/DEVELOP 阶段通过以下测试验证：

| 验证项 | 复现步骤 | 预期结论 |
|--------|---------|---------|
| 多 topic 单连接 | 建立 SSE 连接，events.jsonl 和 file_changes.jsonl 各有数据 | 同一连接收到 `event: run_event` 和 `event: file_changes`，各自 `id:` 独立递增 |
| per-topic 断线重连 | 收到 run_event id=5、file_changes id=2 后断线，以 last_event_id=5&last_file_changes_id=2 重连 | run_event 只推 id>5，file_changes 只推 id>2 |
| 单 topic 游标超出 | last_file_changes_id=99 但 file_changes.jsonl 只有 2 条 | file_changes topic 返回 stream_error（topic=file_changes, code=cursor_unrecoverable）；run_event topic 不受影响 |
| run_event terminal 但 file_changes 仍活跃 | Run done 但 file_changes.jsonl 仍有未推送数据 | stream_end 不发送，直到所有 topic 都 terminal |
| file_changes 不进 events.jsonl | SSE 推送 file_changes 后检查 events.jsonl | events.jsonl 中无 file_changes 相关事件 |
| 前端多 topic 分发 | 前端建立 SSE 连接 | run_event 和 file_changes 各自进入对应 handler，不串线 |
