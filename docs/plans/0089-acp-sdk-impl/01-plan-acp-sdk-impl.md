---
title: ACP SDK 真实实现 Plan
description: 用 agent-client-protocol SDK 正式实现 ACP transport + backend + manager 路由 + CLI 选项，AC-030 全 6 场景用 mock server 验证
type: plan
status: done
created: 2026-07-25T12:00:00Z
---

# Goal

按 ADR-0049 将 loopflow 的 ACP 路径从手搓 JSON-RPC stub 替换为基于官方 `agent-client-protocol` SDK 的真实实现，使 `--transport acp` 成为真正可选可用的路径。用 0088 mock ACP server 验证 AC-030 全 6 场景（CI 可跑，不依赖真实 pi-acp）。

# Constraints

- 从 develop 拉新分支 `feat/0089-acp-sdk-impl`，不合并 spike 分支（spike 代码是验证级，正式版处理遗留项 + 测试 + 质量门禁）
- `agent-client-protocol` 保持主依赖区（0088 已落主依赖；ADR-0049 §8 最终 extra 划分留 RELEASE）
- grok ACP 处理（ADR-0038）：`_GrokAcp` 改继承 `AcpSdkBackend`，命令 `["grok", "agent", "stdio"]`；grok ACP 的 `_meta` system prompt 映射（rules/systemPromptOverride）暂不支持（SDK 的 session/new 不传 `_meta`），在 Report 交代
- 旧 `transports/acp.py` + `backends/acp_backend.py`：`AcpBackend` 仍被 `_GrokAcp` 引用，删除会导致 import 断裂。保留 `AcpTransport`/`AcpBackend` 作为兼容壳（`_GrokAcp` 继承 `AcpSdkBackend` 后不再引用 `AcpBackend`，但 `test_backend_refine.py` 可能引用 `AcpBackend`——需检查后决定删除或保留）
- capabilities 时序修法：spike 遗留——capabilities 在 start() 前被调导致 load_session_supported=False。正式版改为 lazy：`capabilities` property 在 `_ensure_initialized()` 后从 `initialize_result.agent_capabilities.load_session` 动态声明 `resume_session`/`durable_session_id`
- context 过滤：首条 agent_message_chunk 可能含 context 前缀（pi-acp 行为）。在 backend 层过滤 `[context]` 前缀文本，不污染业务输出。用 mock 的 context_prefix 模式测试
- `_run_subagent` 需从 `_ctx.execution_options` 读 transport 传给 `_make_backend`（spike 未修复此 gap）
- CLI-only 后端（claude/codex）传 transport=acp 时报错（"backend X has no ACP transport"），不强制适配器
- AC-030 全 6 场景用 mock server 各模式跑真实测试，不依赖真实 pi-acp

# Steps

1. 建 `docs/plans/0089-acp-sdk-impl/`（README + 本 Plan）
2. 分支 `feat/0089-acp-sdk-impl` 从 develop
3. TDD：AC-030 6 场景测试先行（用 mock_acp_server 各模式），红 → 实现 → 绿
4. 实现 `transports/acp_sdk.py`（from spike，清理 + context 过滤 hook）
5. 实现 `backends/acp_sdk_backend.py`（from spike，修 capabilities lazy + context 过滤 + notification 全量映射）
6. 更新 `manager.py`（transport=acp 路由 + per-backend ACP 命令 + CLI-only 报错）
7. 更新 `runtime.py`（execution_options 读 transport/backend）
8. 更新 `cli.py`（--transport / --backend 选项）
9. 处理 `grok.py`（_GrokAcp 继承 AcpSdkBackend）
10. 决定旧 acp.py/acp_backend.py 去留
11. manifest：agent_cases.json AC-030 planned:: 换真实节点（同步 manifest.py TEST_NODES）
12. 门禁：pytest 全绿；四 profile strict；前端无改动跑 vitest/build 确认无回归
13. Report + README done
14. commit 拆分 + 合并 develop（--no-ff），删分支

# Acceptance

- AC-030-N-1：ACP 后端 loop 端到端，events 含 agent_start→agent_session→agent_message→agent_done(exit_code=0)
- AC-030-N-2：notification 全量映射（thought/tool_call/usage），无类型静默丢弃
- AC-030-B-1：request_permission auto-approve，不阻塞不死锁
- AC-030-B-2：未装 agent-client-protocol extra 时报错提示安装
- AC-030-E-1：后端启动失败 → run failed，error_summary 含不可用信息
- AC-030-F-1：声明 loadSession 的后端 session/load 续接 + continue 门控；不声明时 continue_not_supported
- `uv run pytest tests/ -q` 全绿无回归
- `check-ac-manifest.py --profile agent` strict 通过（agent profile 全绿）
- 四 profile strict（web/recovery/scheduling 既有 + agent 新全绿）
- 前端 vitest/build 无回归

# Checkpoint

- TDD 红阶段：先写 6 场景测试，确认全红（无 AcpSdkBackend）
- 实现绿阶段：逐场景实现，从 N-1 到 F-1
- capabilities lazy 声明需单独单测覆盖
- context 过滤需用 context_prefix 模式单测覆盖
- grok ACP 处理在 Plan/Report 说明，不阻塞核心实现

# Exit

全部 Acceptance 通过，写 Report，合回 develop（--no-ff），删分支。
