---
title: Grok Backend Transport
description: 记录 Grok Build 后端默认 CLI、显式 ACP、streaming-json 解析和 ACP 初始化修正
type: adr
status: accepted
created: 2026-07-22T00:00:00Z
---

# ADR 0038: Grok Backend Transport

## 背景

Grok Build 提供两条可用于 loopflow 的 Agent 执行入口：

1. Headless CLI：`grok -p <prompt> --output-format streaming-json`
2. ACP stdio：`grok agent stdio`

loopflow 已有后端体系、`CliBackend`、`AcpBackend` 和 `AcpTransport`。现有架构约束包括：

- ADR 0018：所有后端默认 CLI-first，ACP 仅显式启用。
- ADR 0023：后端输出优先使用 JSON/结构化模式。
- ADR 0021：ACP `session/update` 是后续事件归一化方向。

Grok 接入需要在不破坏既有后端行为的前提下，支持可恢复 session id、思考/文本分离和未来 ACP 扩展。

## 决策

### 1. Grok 默认使用 CLI headless

`GrokBackend()` 默认走 CLI：

```bash
grok -p <prompt> --output-format streaming-json --permission-mode bypassPermissions
```

resume 使用：

```bash
grok -p <prompt> --output-format streaming-json --resume <session_id> --permission-mode bypassPermissions
```

CLI 输出解析规则：

| Grok streaming-json 事件 | loopflow 处理 |
|--------------------------|---------------|
| `text.data` | agent text chunk |
| `thought.data` | thought handler |
| `end.sessionId` | durable backend session id |
| `error.message` | text error output，exit code 由 transport 决定 |

system prompt 映射：

| system_mode | Grok CLI 参数 |
|-------------|---------------|
| `append` | `--rules <system>` |
| `overwrite` | `--system-prompt-override <system>` |

### 2. Grok ACP 仅显式启用

仅当调用方显式传入 `transport="acp"` 时，`GrokBackend` 使用：

```bash
grok agent stdio
```

Grok ACP session 创建通过 `_meta` 传系统语义：

| system_mode | ACP `_meta` |
|-------------|-------------|
| `append` | `{ "rules": system }` |
| `overwrite` | `{ "systemPromptOverride": system }` |

Grok ACP 监听标准 `session/update`，并兼容 Grok 文档提到的 `x.ai/session/update`。处理以下 update：

| ACP update | loopflow 处理 |
|------------|---------------|
| `agent_message_chunk` | agent text chunk |
| `agent_thought_chunk` | thought handler |

`session/new` 返回 `sessionId` 后立即调用 `session_handler`，保证 Run cache 能尽早持久化 durable session id。

### 3. `grok` 是唯一后端名

`grok` 是公开文档、backend manager、diagnostics 和 WebUI 中唯一有效的 Grok 后端名称。`gork` 是错误拼写，不作为兼容别名保留；显式指定 `backend="gork"` 应按 unknown backend 处理。

### 4. ACP 初始化只发送一次

`AcpTransport.start()` 负责启动子进程并发送唯一一次 `initialize`。初始化结果保存到 transport，由 `AcpBackend._ensure_initialized()` 读取 `authMethods`，不得再次发送 `initialize`。

原因：真实 ACP server 通常预期 `initialize` 是一次性 handshake。重复发送可能导致协议错误、状态重置、重复认证协商或事件流顺序异常。

## 备选方案

### 方案 A：只支持 CLI

- 优点：实现最小，已通过真实 headless smoke。
- 缺点：无法验证和保留 Grok ACP 的 session/update、模型列表和更丰富状态事件。

### 方案 B：默认切到 ACP

- 优点：更结构化，和 ACP 事件模型更一致。
- 缺点：违反 ADR 0018；ACP tool call/授权处理仍不完整，存在死锁或阻塞风险。

### 方案 C：默认 CLI，显式 ACP（采纳）

- 优点：保持已验证默认路径；ACP 可由高级调用方显式启用；符合 ADR 0018。
- 缺点：当前 CLI/API 尚未公开 `--transport` 参数，ACP 主要通过 backend factory 或未来配置启用。

## 选择理由

1. CLI headless 已真实验证，且 `streaming-json` 提供 text、thought、sessionId，满足 loopflow 当前后端契约。
2. ACP 真实 `grok agent stdio` smoke 已验证 initialize、session/new、session/prompt、agent_message_chunk 和 end_turn。
3. 默认 CLI 可避免 ACP tool call 授权处理不完整带来的死锁风险。
4. 显式 ACP 保留未来更完整 session/update 和协议能力。
5. 错误拼写不注册为兼容别名，避免 diagnostics/WebUI 出现两个名称指向同一 binary。

## 后果

### 正面

- Grok 可作为一等 backend 使用。
- CLI 和 ACP 两条路径都能取得 durable session id。
- Grok thinking/text 分离可进入 loopflow 的 handler 体系。
- 通用 ACP 初始化流程更符合协议。

### 负面

- `GrokBackend` 内部需要 CLI/ACP 双实现，维护成本高于单一路径。
- ACP 仍没有完整 tool call 授权/响应处理，不适合默认启用。
- 错误拼写不再被容错，旧配置中若写成 `gork` 会明确失败，需要修正为 `grok`。

## 验证

| 验证项 | 复现步骤 | 结论 | 证据 |
|--------|----------|------|------|
| Grok CLI contract | `grok --help`、`grok --version`、真实 `grok -p ... --output-format streaming-json` | 可用 | Plan 0046 Report |
| Grok CLI session id | headless smoke 返回 `end.sessionId` | 可用 | `019f8997-25ab-7173-898e-956133b9c73c` |
| Grok ACP stdio | 手工 JSON-RPC：`initialize` -> `session/new` -> `session/prompt` | 可用 | Plan 0047 Report |
| Grok ACP text stream | `agent_message_chunk` 拼接为 `loopflow-grok-acp-ok` | 可用 | Plan 0047 Report |
| ACP 初始化单次发送 | 单元测试覆盖 `AcpBackend` 复用 `_initialize_result` | 通过 | `tests/unit/test_backend_refine.py` |

## 约束范围

- `src/loopflow/infrastructure/backends/grok.py`
- `src/loopflow/infrastructure/backends/manager.py`
- `src/loopflow/infrastructure/backends/diagnostics.py`
- `src/loopflow/infrastructure/backends/acp_backend.py`
- `src/loopflow/infrastructure/transports/acp.py`

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|----------|----------------|
| AR-001 | Grok 默认 transport 必须是 CLI | `grok.py` | 单元测试/代码审查 |
| AR-002 | Grok ACP 只能在 `transport="acp"` 时启用 | `grok.py` | 单元测试/代码审查 |
| AR-003 | Grok CLI 必须使用 `streaming-json` 并解析 `end.sessionId` | `grok.py` | 单元测试 |
| AR-004 | Grok ACP system prompt 必须走 `_meta.rules` 或 `_meta.systemPromptOverride` | `grok.py` | 单元测试 |
| AR-005 | ACP transport 初始化不得重复发送 `initialize` | `acp.py` / `acp_backend.py` | 单元测试 |

## 修订记录

- 2026-07-24：删除 `gork` 误拼写 backend 名称。它不再作为兼容别名注册到 backend manager 或 diagnostics，避免后端检测和 WebUI 显示重复 Grok 后端。
