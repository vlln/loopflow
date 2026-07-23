---
title: Grok ACP Transport Report
description: 记录 Grok ACP stdio transport 实现、单测和真实协议 smoke 结果
type: report
status: complete
created: 2026-07-22T00:00:00Z
---

# Summary

已为 Grok backend 增加显式 ACP transport。`GrokBackend()` 默认仍使用 CLI headless；`GrokBackend(transport="acp")` 使用 `grok agent stdio`。Grok ACP 支持 `_meta.rules`、`_meta.systemPromptOverride`、`agent_message_chunk`、`agent_thought_chunk` 和 session id 早期上报。

同时修正通用 ACP 初始化流程：`AcpTransport.start()` 保存 initialize 结果，`AcpBackend._ensure_initialized()` 复用该结果，不再重复发送 `initialize`。

# Acceptance

| 场景 | 结果 | 证据 | 提交 |
|------|------|------|------|
| AC-008-N-2 | [PASS] | `GrokBackend(transport="acp")` 使用 `["grok", "agent", "stdio"]`，默认 Grok CLI 路径保持可用 | `12da95a` |
| AC-008-B-2 | [PASS] | `grok`/`gork` 注册保持不变；本 Plan 不修改 unknown backend 路径 | `12da95a` |
| AC-008-E-1 | [PASS] | ACP prompt 失败返回 exit code 1；ACP process/handshake 失败沿用 transport RuntimeError | `12da95a` |

# Verification

| 命令 | 结果 |
|------|------|
| `.venv/bin/python -m pytest tests/unit/test_backend_refine.py tests/unit/test_web_resources.py -q` | PASS: 28 passed |
| `.venv/bin/python -m py_compile src/loopflow/infrastructure/backends/grok.py src/loopflow/infrastructure/backends/acp_backend.py src/loopflow/infrastructure/transports/acp.py` | PASS |
| `grok agent stdio` JSON-RPC smoke: `initialize` -> `session/new` -> `session/prompt` | PASS: `sessionId=019f89a0-384a-7f11-875f-66d1bfaef88f`; `agent_message_chunk` 拼接为 `loopflow-grok-acp-ok`; `session/prompt` 返回 `stopReason=end_turn` |

# Notes

- 真实 ACP smoke 使用 TTY 手工 JSON-RPC，因此 stdout 包含输入回显；项目 `AcpTransport` 使用 pipe，不会收到 TTY 回显。
- `grok agent stdio` 需要访问 Grok 本地 auth/session storage 和网络，测试在用户授权后于 sandbox 外执行。
- 未运行完整 `loopflow run --backend grok --transport acp` 端到端；当前 CLI/API 还没有公开 `--transport` 参数，本 Plan 验证的是 backend factory 显式 transport 路径和 Grok ACP 协议互通。
- 未运行 `scripts/submission-gate.py`：默认 system manifest 未收录 AC-008 场景，本 Report 以 docs/ac/0001-loopflow.md 的 AC-008 为契约来源。
