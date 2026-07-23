---
title: Grok ACP Transport Plan
description: 为 Grok Build backend 增加显式 ACP stdio transport，并验证 Grok agent stdio 协议互通
type: plan
status: done
created: 2026-07-22T00:00:00Z
---

# Goal

在已完成的 Grok CLI backend 基础上，增加 Grok ACP transport 支持。默认 `backend="grok"` 行为保持 CLI 不变；仅当调用 `_make_backend("grok", transport="acp")` 或等价显式配置时，使用 `grok agent stdio` 进行 JSON-RPC/ACP 通信。

# Acceptance

本 Plan 覆盖 AC-008 后端管理的 transport 扩展：

`AC-008-N-2`：显式指定 Grok ACP transport 时创建 Grok ACP backend，不影响默认 CLI backend 和其他后端。

`AC-008-B-2`：未知 backend 仍由既有 unknown 路径处理；`grok`/`gork` 注册名保持可用。

`AC-008-E-1`：Grok ACP 进程不可用、认证失败或 prompt 失败时沿用 ACP/runner 现有错误或 exit-code 路径，不引入静默成功。

# Constraints

1. 不把 Grok 默认 transport 改成 ACP；CLI 仍是默认路径。
2. Grok ACP 使用 `["grok", "agent", "stdio"]`，不新增外部依赖。
3. Grok ACP system prompt 不拼进 user prompt：`append` 映射为 `_meta.rules`，`overwrite` 映射为 `_meta.systemPromptOverride`。
4. Grok ACP session id 在 `session/new` 返回后立即通过 `session_handler` 上报，保证 durable session 可记录。
5. 监听标准 `session/update`，并额外兼容 Grok 文档中的 `x.ai/session/update`。
6. 解析 `agent_message_chunk` 到 text handler，解析 `agent_thought_chunk` 到 thought handler；其他 ACP 更新忽略。
7. 修正通用 `AcpTransport.start()` 与 `AcpBackend._ensure_initialized()` 重复 initialize 行为，避免真实 Grok agent stdio 收到多余 handshake。

# Steps

1. 阅读现有 `AcpBackend` / `AcpTransport` 与 Grok agent mode 文档。
2. 将 `GrokBackend` 改为 CLI/ACP delegating wrapper，默认选择 `_GrokCli`，`transport="acp"` 选择 `_GrokAcp`。
3. 新增 `_GrokAcp`：命令、session meta、session handler、message/thought notification 处理、create/resume。
4. 修正通用 ACP 初始化结果保存和复用，避免双 initialize。
5. 增加单元测试：Grok ACP 命令、`_meta`、resume、notification、session handler，以及通用 ACP 初始化复用。
6. 运行 targeted 单测、py_compile 和真实 `grok agent stdio` smoke。
7. 回填 Report，代码和文档分开提交。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Default behavior | Grok 默认仍走 CLI backend | Unit test existing path |
| ACP command | `transport="acp"` 使用 `grok agent stdio` | Unit test |
| ACP meta | append/overwrite system prompt 映射到 Grok `_meta` | Unit test |
| ACP stream | message/thought chunks 进入对应 handler | Unit test + smoke |
| ACP session | `session/new` 返回 session id 并可 prompt | Real smoke |
| Regression | 后端单测和语法检查通过 | Report |

# Exit

Plan 状态 done、Report complete、代码提交与文档提交分离、targeted tests 和真实 ACP smoke 通过后，本执行容器完成。
