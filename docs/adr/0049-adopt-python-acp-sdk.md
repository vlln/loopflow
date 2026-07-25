---
title: ADR 0049 — 采用官方 Python ACP SDK 替换手搓 ACP 管道
description: 用 agent-client-protocol（PyPI）替换 transports/acp.py + backends/acp_backend.py 的手搓 JSON-RPC 协议管道；保留 loopflow 自己的 session/recovery/queue；CLI 保留为主传输，ACP 成为真正可用的可选路径
type: adr
status: proposed
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

**待 spike 验证**（spike/0049-acp-sdk-spike，分支保留不合并）：

1. `uv add agent-client-protocol`（spike 分支，不合并）。
2. 用 SDK 重写最小 ACP transport，sync/async 桥接方案落地。
3. 用 `pi-acp` 作为真实 ACP 后端，跑通一个 loopflow loop（`loopflow run <loop> --backend pi --transport acp` 或等价路径），验证：initialize handshake、session/new、session/prompt、streaming notification 映射到 loopflow 事件、permission auto-approve 不死锁、agent 文本输出回到 workflow。
4. 记录：sync/async 桥接方式、SDK API 用法、pi-acp 行为、是否需要补 session/load（continue）。

spike 通过后回填本段结论并将 status promote 为 accepted；不通过则退回重新设计。
