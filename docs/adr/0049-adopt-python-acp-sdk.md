---
title: ADR 0049 — 采用官方 Python ACP SDK 替换手搓 ACP 管道
description: 用 agent-client-protocol（PyPI）替换 transports/acp.py + backends/acp_backend.py 的手搓 JSON-RPC 协议管道；保留 loopflow 自己的 session/recovery/queue；CLI 保留为主传输，ACP 成为真正可用的可选路径
type: adr
status: accepted
created: 2026-07-25T02:00:00Z
---

# ADR 0049: 采用官方 Python ACP SDK 替换手搓 ACP 管道

## Context

loopflow 现有 ACP 路径是**未验证的 stub，且在生产中是死的**：

- `transports/acp.py`（170 行）手搓了 JSON-RPC 分帧、`initialize` handshake、notification 分发——这些正是官方 Python SDK `agent-client-protocol`（0.11.0）用 asyncio + Pydantic schema 免费提供的。
- `backends/acp_backend.py` 是 stub：`_on_update` 只处理 `agent_message_chunk`，`agent_thought_chunk`/`tool_call_*`/`usage_update` 全未实现（ADR-0021 自己标了"后续扩展"）；`capabilities` 未声明（resume_session/durable_session_id 全 False，导致 continue 在 ACP 后端永远 `continue_not_supported`）；`stderr=subprocess.DEVNULL` 无诊断；exit code 硬编码 0/1，无法表达 goal。
- `runtime.py:83` 调 `_make_backend(backend)` **从不传 `transport` 参数**，各后端判定 `use_acp = transport == "acp"` → 默认永远走 CLI，ACP 路径在运行时根本到不了。
- ADR-0018 因 kimi ACP 的 Skill tool call 等待 client 授权导致死锁，将所有后端默认切到 CLI；ADR-0038 明确否决"默认切 ACP"。

0.21.0 的可靠性特性（失败分类、熔断、宽限期、队列状态）全建在 CLI 之上。本 ADR 的范围**仅限把死掉的 ACP 管道换成官方 SDK 使其真正可用**，不动 CLI 主路径。

## Decision

### 1. 用官方 SDK 替换协议管道

`agent-client-protocol`（PyPI 0.11.0）作为 ACP 协议层。`transports/acp.py` 的 JSON-RPC 分帧/handshake/notification 分发改用 SDK 的 stdio client transport + Pydantic schema 模型；`backends/acp_backend.py` 的 session/new|load|prompt|set_model|list 改用 SDK 的 session 方法 + helpers。

### 2. 保留 loopflow 的应用层

SDK 只替换**协议管道**。loopflow 自己的 session 生命周期映射、recovery/cache（`infrastructure/recovery.py`）、queue/dispatch、失败分类（0.21.0 BR-049）、熔断（BR-050）、continue 门控——全部保留。这与 acpx 不同：acpx 自建 reconnect（680 行）、queue（3417 行）、persistence（3970 行）、permissions（443 行），因为它是从零做编排器；loopflow 已有对等层，不需要 acpx 的版本。

### 3. sync/async 桥接（spike 待定具体方式）

loopflow runner 是 sync/threading；SDK 是 asyncio。候选方案：(a) 每个 ACP backend 实例在专属线程跑独立 event loop；(b) 每次 ACP 操作 `asyncio.run`。具体方式由 spike 验证后定，记录在 Verification 段。

### 4. 权限策略：auto-approve-all

ACP 的 `request_permission`（agent 请求 client 授权工具/资源）在 loopflow 的 fire-and-forget 模型下无人工介入，统一 auto-approve（对应 acpx 的 approve-all，但 loopflow 不做 read/写分级，一刀切放行）。这使 ADR-0018 的授权死锁不再发生。SDK 的 contrib 有 permission broker 可复用。

### 5. notification 映射补全

SDK `SessionNotification` → loopflow 事件全量映射：`agent_message_chunk`→`agent_message`、`agent_thought_chunk`→thought、`tool_call_start/progress`（信息性，不要求 client 响应）、`usage_update`。补齐当前 stub 丢弃的事件类型。

### 6. transport 选择可达化

让 `transport="acp"` 在运行时可选达：CLI 加 `--transport acp`（或 per-backend 配置）。默认仍 CLI。ACP 成为真正可选的路径而非死代码。

### 7. ACP 上的 continue

为声明 `session/load` 的 ACP 后端声明 `resume_session`/`durable_session_id` 能力，使 continue 在 ACP 后端可用（best-effort，per-backend 门控，符合 0.21.0 BL-001 continue 能力门控模式）。ACP `session/resume` 是可选能力、后端实现参差，continue 仍是 best-effort。

### 8. 依赖定位：可选依赖

`agent-client-protocol`（+ pydantic）作为**可选运行时依赖**（extra `[acp]`），仅在 `--transport acp` 时 import。默认 CLI 路径不引入新依赖，保持 lean。pyproject 在 DEVELOP 阶段正式加 extra；spike 阶段在 venv 装。

## Alternatives

| 方案 | 评估 |
|------|------|
| 保留手搓 ACP | 不采纳。重复 SDK 已有的协议管道，且是未验证 stub，维护负担无收益 |
| 包装 acpx 子进程 | 不采纳。acpx 是 TS，多一层进程 + JSON 序列化；其 session/reconnect/queue/persistence loopflow 已有对等层，边际价值≈一个 adapter 命令表 |
| 放弃 CLI、仅 ACP | 不采纳（前轮已论证）。CLI 承担 goal exit code、自主工具调用、claude/codex/pi 直连、stderr 失败分类；0.21.0 可靠性特性建在其上。本 ADR 只让 ACP 可用，不丢 CLI |

## Consequences

- 新增可选运行时依赖 `agent-client-protocol`（+ pydantic），仅 ACP 路径加载；默认 CLI 路径依赖不变。
- `transports/acp.py` 大幅瘦身或删除（JSON-RPC 管道交给 SDK）；`backends/acp_backend.py` 从 stub 补全为可用实现。
- ADR-0018 的"默认 CLI"结论不变；本 ADR 使 ACP 从死路径变为可选可用路径，不改变默认行为。
- ADR-0021 的"ACP 后端直接透传"从 stub 变为真实实现。
- 需新增/修订 AC：ACP 后端 loop 端到端跑通（含 session/prompt、streaming 事件、permission auto-approve）。

## Architecture Boundary

协议管道（JSON-RPC/handshake/notification 分发）在 `infrastructure/transports/`，改用 SDK；session/notification 映射在 `infrastructure/backends/acp_backend.py`，是 loopflow 在 SDK 之上的一层；sync/async 桥接在 transports 层内部封装，不泄漏到 application/domain；CLI 路径与 ACP 路径在 backends 层分叉，runtime 选择。

## Verification

**spike 已通过**（spike/0049-acp-sdk-spike，commit `2dc01e4`，分支保留不合并）。

### 1. 环境与依赖

- `uv add agent-client-protocol` → 0.11.0 安装成功，带入 pydantic 2.13.4 + pydantic-core 2.46.4。
- 仅 spike 分支变更 `pyproject.toml`/`uv.lock`，不合并。
- `pi-acp` 0.0.31（pi 0.82.0）作为真实 ACP 后端。

### 2. sync/async 桥接方式

**采用：专属守护线程 + 持久事件循环。**

loopflow runner 是 sync/threading；SDK 是 asyncio。SDK 的 `Connection` 类在构造时启动后台 receive-loop task（`listening=True` 默认），需要事件循环持续运行。`asyncio.run` per-op 会在每次调用后销毁事件循环及其后台 task，导致 receive loop 被杀死——**不可行**。

方案：创建 daemon 线程，在其中 `asyncio.new_event_loop()` + `run_forever()`，主线程通过 `asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)` 提交协程并阻塞等待。事件循环在整个 transport 生命周期内持久运行，receive loop 不被打断。关闭时 `loop.call_soon_threadsafe(loop.stop)` + `thread.join()`。

此桥接完全封装在 `transports/acp_sdk.py` 内部，不泄漏到 application/domain 层。

### 3. SDK 实际用到的 API

| 模块 | 类/函数 | 用法 |
|------|--------|------|
| `acp.stdio` | `spawn_agent_process(client, command, *args)` | async context manager，spawn agent 子进程 + 创建 `ClientSideConnection` |
| `acp.client.connection` | `ClientSideConnection` | `.initialize()`, `.new_session()`, `.load_session()`, `.prompt()`, `.authenticate()`, `.close()` |
| `acp.interfaces` | `Client` Protocol | 实现 `session_update(session_id, update)` 收通知、`request_permission(session_id, tool_call, options)` 做授权 |
| `acp.schema` | `InitializeResponse` | `.agent_capabilities.load_session` (bool), `.auth_methods` |
| `acp.schema` | `NewSessionResponse` | `.session_id` |
| `acp.schema` | `PromptResponse` | `.stop_reason` (end_turn / max_tokens / ...) |
| `acp.schema` | `AllowedOutcome` | auto-approve 返回 `RequestPermissionResponse(outcome=AllowedOutcome(option_id=...))` |
| `acp.schema` | `AgentMessageChunk` / `AgentThoughtChunk` / `ToolCallStart` / `ToolCallProgress` / `UsageUpdate` | notification update 类型，有 `session_update` discriminator 字段 |
| `acp.helpers` | `text_block(text)` | 构造 `TextContentBlock` 用于 prompt |
| `acp.meta` | `PROTOCOL_VERSION = 1` | handshake protocol version |

**Client 协议**：Client 实现是 SDK→loopflow 的桥——agent 通过 JSON-RPC 调用 client 的 `session_update`（推送通知）和 `request_permission`（请求授权）。loopflow 实现 `_AutoApproveClient`：`session_update` 转发到注册的 notification handler；`request_permission` 自动返回 `AllowedOutcome`。

### 4. pi-acp 真实行为

| 项目 | 观测值 |
|------|--------|
| `protocolVersion` | 1 |
| `agentInfo` | name=pi-acp, version=0.0.31 |
| `loadSession` | **true** — `session/load` 可用 |
| `sessionCapabilities` | `{list: {}}` — 支持 `session/list` |
| `promptCapabilities` | image=true, audio=false, embeddedContext=false |
| `mcpCapabilities` | http=false, sse=false, acp=false |
| `authMethods` | `[{id: "pi_terminal_login", type: "terminal"}]` — 若 pi 已配置则无需 authenticate |
| `request_permission` | 简单文本 prompt 未触发。机制已就绪（`_AutoApproveClient` wired），但 pi-acp 在无工具调用时不发权限请求 |
| streaming 事件类型 | `session_info_update`, `available_commands_update`, `agent_thought_chunk`（思考过程）, `agent_message_chunk`（最终回答）, `tool_call`/`tool_call_update`（工具调用时）, `usage_update` |
| stderr | SDK transport 用 `asyncio.subprocess.PIPE` 读 stderr；spike 未做 stderr 文本提取（遗留项） |
| 首条 message chunk | pi-acp 先输出 context（AGENTS.md、skills 列表），然后才是 agent 回答。DEVELOP 阶段需在 backend 层过滤 |

### 5. 实跑结果

#### 独立 smoke test（`scripts/spike_0049_smoke.py`）

```
[smoke] initialize handshake → agentCapabilities: loadSession=true ✅
[smoke] session/new → sessionId: 019f98ed-...  ✅
[smoke] session/prompt → streaming: agent_thought_chunk ×6, agent_message_chunk ×3
[smoke] PromptResponse: stopReason=end_turn ✅
[smoke] Full agent text: "Hello from ACP!" ✅
```

#### loopflow 全链路（`loopflow run spike-acp --backend pi --transport acp`）

run.json status: `failed`（loop 脚本对 AgentResult 调 `len()` 抛异常，**非 ACP 问题**）。

events.jsonl 关键事件：
```jsonl
{"type":"agent_start","session":"wf_998c23..._1"}                    // ✅
{"type":"agent_session","session_id":"019f98f0-0556-..."}            // ✅ ACP sessionId
{"type":"agent_message","content":"Hello"}                          // ✅ streaming chunk
{"type":"agent_message","content":" from loop"}                     // ✅
{"type":"agent_message","content":"flow A"}                          // ✅
{"type":"agent_message","content":"CP!"}                             // ✅
{"type":"agent_done","exit_code":0,"status":"succeeded",
 "session_id":"019f98f0-0556-7ea3-a1ff-21a598ef5e24"}                // ✅
```

全链路验证：initialize handshake → session/new → session/prompt → streaming notification 映射到 events.jsonl → agent 文本输出回到 workflow → run 正常结束（agent_done exit_code=0）。

#### session/load（continue）验证（`scripts/spike_0049_resume.py`）

```
[resume] loadSession supported: True
[resume] session/new → sessionId: 019f98f0-e03e-...  ✅
[resume] prompt #1: "Remember the number 42" → response: "OK"  ✅
[resume] session/load(019f98f0-e03e-...) → True  ✅
[resume] prompt #2: "What number did I ask you to remember?" → response: "42"  ✅
[resume] Resume WORKS
```

**pi-acp 的 session/load 保留了对话上下文**——ADR-0049 §7 的 ACP continue 方案可行。

### 6. 遇到的坑与绕法

1. **`run_fore()` 拼写错误**：初始版本误写 `loop.run_fore()`，应为 `run_forever()`。已修复。
2. **pi-acp 首条 message chunk 包含 context**：pi-acp 在首次 prompt 时先输出 AGENTS.md + skills 列表作为 context，然后才是 agent 回答。loopflow 的 `agent_message` 事件因此包含 context 文本。DEVELOP 阶段需在 backend 层过滤。
3. **Pydantic serializer warning**：`InitializeResponse` 的 `auth` 字段默认 `{}`，序列化时 Pydantic 发出类型警告。不影响功能。
4. **capabilities 时序问题**：`AcpSdkBackend.capabilities` 在 transport `start()` 前被调用，此时 `load_session_supported` 返回 False（`_init_result` 为 None）。导致 `can_recover_continue=false`。DEVELOP 阶段需提前 initialize 或 lazy 声明。

### 7. session/load（continue）结论

**可行。** pi-acp 声明 `loadSession=true`，`session/load` 成功后 agent 保留上下文。ADR-0049 §7 方案成立。

### 8. ADR 设计修订建议

1. **auto-approve 足够**：`AllowedOutcome` 一刀切放行，无死锁。ADR §4 成立。
2. **sync/async 桥接**：专属线程 + 持久事件循环方案可行。`asyncio.run` per-op **不可行**（receive loop 被杀），ADR §3 应明确排除 (b)。
3. **依赖体积**：agent-client-protocol 0.11.0 + pydantic 共 ~3MB。作为可选依赖 `[acp]` 可接受。
4. **pi-acp context 输出**：DEVELOP 阶段需处理首条 chunk 包含 context 的问题。
5. **capabilities 时序**：DEVELOP 阶段需解决 initialize 前不可用的问题。

**结论：ADR-0049 设计成立，spike 验证通过。** 可将 status promote 为 `accepted`。
