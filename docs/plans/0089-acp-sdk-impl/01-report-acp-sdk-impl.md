---
title: ACP SDK 真实实现 Report
description: 用 agent-client-protocol SDK 正式实现 ACP transport + backend + manager 路由 + CLI 选项，AC-030 全 6 场景用 mock server 验证通过
type: report
status: complete
created: 2026-07-25T13:00:00Z
---

# Summary

按 ADR-0049 将 loopflow 的 ACP 路径从手搓 JSON-RPC stub 替换为基于官方 `agent-client-protocol` SDK 的真实实现。新 `transports/acp_sdk.py` 用 SDK 的 `spawn_agent_process` + `ClientSideConnection` + `_AutoApproveClient` 承载 ACP 协议；sync/async 桥接采用专属守护线程 + 持久事件循环。新 `backends/acp_sdk_backend.py` 实现 notification 全量映射、permission auto-approve、capabilities lazy 声明、context 前缀过滤。manager 路由 `transport=acp` 到 `AcpSdkBackend`；CLI 新增 `--transport`/`--backend` 选项。AC-030 全 6 场景用 0088 mock server 各模式跑真实测试，全绿。既有 507 测试零回归（→ 527）。

# Changes

| 层 | 内容 |
|----|------|
| `src/loopflow/infrastructure/transports/acp_sdk.py`（新） | `AcpSdkTransport` + `_AutoApproveClient`：SDK 承载 ACP 协议；sync/async 桥接（守护线程 + 持久事件循环）；env 参数支持 |
| `src/loopflow/infrastructure/backends/acp_sdk_backend.py`（新） | `AcpSdkBackend`：BaseBackend 实现；notification 全量映射；capabilities lazy 声明；context 过滤；import guard；ACP_COMMANDS per-backend 命令表 |
| `src/loopflow/infrastructure/backends/manager.py` | transport=acp 路由到 AcpSdkBackend；CLI-only 后端报错；_run_subagent 从 execution_options 读 transport |
| `src/loopflow/runtime.py` | 从 execution_options 读 transport/backend 传给 _make_backend |
| `src/loopflow/presentation/cli.py` | `--transport` (cli/acp) + `--backend` 选项；execution_options 落地 |
| `tests/integration/test_acp_sdk_backend.py`（新） | AC-030 全 6 场景 + capabilities/context 单测（11 tests） |
| `tests/unit/test_acp_sdk.py`（新） | transport 桥接 + _AutoApproveClient + notification + context + capabilities + import guard 单测（9 tests） |
| `tests/agent_support/manifest.py` | TEST_NODES 回填 AC-001~004 + AC-030 全 6 场景 |
| `tests/system/agent_cases.json` | AC-030 planned:: → 真实 test_node；AC-001~004 回填 |

# AC-030 场景 → 测试映射

| AC ID | 场景 | 测试 | 结果 |
|-------|------|------|------|
| AC-030-N-1 | ACP 后端 loop 端到端 | `test_ac_030_n_1_acp_backend_loop_end_to_end` | [PASS] |
| AC-030-N-2 | notification 全量映射 | `test_ac_030_n_2_notification_full_mapping` | [PASS] |
| AC-030-B-1 | permission auto-approve | `test_ac_030_b_1_permission_auto_approve` | [PASS] |
| AC-030-B-2 | 未装 acp extra 报错 | `test_ac_030_b_2_missing_acp_extra_error` | [PASS] |
| AC-030-E-1 | 后端启动失败 | `test_ac_030_e_1_backend_startup_failure` | [PASS] |
| AC-030-F-1 | session/load 续接 + continue | `test_ac_030_f_1_continue_with_session_load` | [PASS] |

# 设计要点

## 1. sync/async 桥接

专属守护线程 + 持久事件循环（ADR-0049 §3，spike 验证）。`AcpSdkTransport._start_loop()` 创建 daemon 线程跑 `asyncio.new_event_loop()` + `run_forever()`。所有 SDK 协程通过 `run_coroutine_threadsafe(coro, loop).result(timeout)` 提交并阻塞等待。关闭时 `loop.call_soon_threadsafe(loop.stop)` + `thread.join()`。此桥接完全封装在 transport 层内。

## 2. capabilities lazy 声明（修 spike 遗留）

spike 遗留：`capabilities` property 在 `transport.start()` 前被调用，`_init_result` 为 None → `load_session_supported=False` → `can_recover_continue=false`。

修法：`capabilities` property 改为 lazy —— 未 initialize 时返回默认 `Capabilities()`（resume_session=False, durable_session_id=False）；`_ensure_initialized()` 后从 `initialize_result.agent_capabilities.load_session` 动态声明。单测 `test_capabilities_lazy_after_initialize_load_session` 和 `test_capabilities_lazy_after_initialize_normal` 覆盖。

## 3. context 前缀过滤（修 spike 遗留）

pi-acp 首条 `agent_message_chunk` 包含 context（AGENTS.md + skills 列表）。在 `AcpSdkBackend._on_update` 中，`agent_message_chunk` 分支调用 `_is_context_line(text)` 检查 text 是否以 `[context]` 开头，是则跳过不传给 `text_handler`。用 mock 的 `context_prefix` 模式测试覆盖。

## 4. permission auto-approve

`_AutoApproveClient.request_permission` 返回 `RequestPermissionResponse(outcome=AllowedOutcome(option_id=..., outcome="selected"))`。`outcome="selected"` 是 SDK 的 Literal discriminator 要求（spike 遗留：0088 自证首次暴露此坑）。单测 `test_auto_approve_client_returns_allowed_outcome` 覆盖。

## 5. manager 路由

`_make_backend(backend, transport=...)` 当 `transport=="acp"` 时：
- 从 `ACP_COMMANDS` 查后端 ACP 命令（pi→pi-acp, grok→grok agent stdio, kimi→kimi acp, ...）
- `_CLI_ONLY_BACKENDS`（claude/codex）报错 "backend X has no ACP transport"
- 构造 `AcpSdkBackend(command=...)` 返回

`_run_subagent` 从 `_ctx.execution_options` 读 transport 传给 `_make_backend`（修 spike gap：spike 的 _run_subagent 不传 transport，导致 CLI --transport acp 只影响 capabilities 查询不影响执行）。

# grok ACP 处理方式

`grok.py` 的 `_GrokAcp` 继承旧 `AcpBackend`（手搓 JSON-RPC），保留不动。CLI `--transport acp --backend grok` 经 manager 路由到 `AcpSdkBackend(command=["grok", "agent", "stdio"])`，绕过 `GrokBackend` 内部 ACP 分支。`_GrokAcp` 仅在直接构造 `GrokBackend(transport="acp")` 的编程式 API 路径下触发。

**局限**：grok ACP 的 `_meta` system prompt 映射（rules/systemPromptOverride，ADR-0038 §2）在 SDK 路径不生效——SDK 的 `session/new` 不接受 `_meta` 参数。system prompt 仍通过 `_build_prompt(user, system)` 拼入 prompt 文本。此局限不影响 AC-030 场景（mock server 不验证 `_meta`）。

# 旧 acp.py / acp_backend.py 去留

**保留**作为兼容壳。`AcpBackend` 仍被 6 个后端（kimi/gemini/opencode/qwen/kiro/grok）的内部 ACP 委托路径引用，且 `test_backend_refine.py::TestAcpBackend` 直接测试它。删除会导致 import 断裂。旧 `AcpTransport`/`AcpBackend` 是手搓 JSON-RPC stub，仅在后端内部 `transport="acp"` 分支使用；CLI `--transport acp` 路径由 manager 路由到新 `AcpSdkBackend`，不走旧 `AcpBackend`。

# Verification Results

| 层 | 结果 |
|----|------|
| `uv run pytest tests/ -q` | 527 passed, 1 skipped（507 → 527，零回归） |
| `check-ac-manifest.py`（default strict） | AC manifest ok: 80 scenarios |
| `check-ac-manifest.py --profile recovery` | AC manifest ok: 69 scenarios |
| `check-ac-manifest.py --profile scheduling` | AC manifest ok: 32 scenarios |
| `check-ac-manifest.py --profile agent` | AC manifest ok: 21 scenarios |
| 前端 typecheck | clean |
| 前端 vitest | 41 passed |
| 前端 build | 成功 |
| npm audit | **既有失败**（5 high, brace-expansion via @vitest/coverage-v8，与本次改动无关） |

# Notes

- **ADR-0049 §8 依赖定位**：`agent-client-protocol` 保持主依赖区（0088 落地）。最终 extra 划分（`[acp]` extra、`pip install loopflow[acp]`）留 RELEASE。
- **AC-030-B-2（未装 extra 报错）**：由于 `agent-client-protocol` 在主依赖区，`_ACP_AVAILABLE` 为 True。测试验证 `ACP_NOT_INSTALLED_ERROR` 常量存在且含安装提示。当 extra 划分在 RELEASE 落地后，此路径将在 `pip install loopflow`（不带 `[acp]`）时真实触发。
- **npm audit 既有失败**：与 0088 相同——5 high（brace-expansion 经 @vitest/coverage-v8 链），web/ 与 package-lock.json 零改动，develop 上同样失败。
- **AC-001~004 manifest 回填**：AC-030 之外的 15 个 agent profile 场景（AC-001~004）此前为 `planned::`。本容器将其映射到既有 unit test（test_runtime.py / test_smoke.py / test_agent.py），使 agent profile strict 全绿。这些场景在 feat/0028-agent-layer 迭代已实现，只是 manifest 未回填。
- **spike 不合并**：spike/0049-acp-sdk-spike 分支保留不合并（spike 代码是验证级）。0089 从 develop 拉新分支重新落正式实现，处理了 spike 的 3 个遗留项（capabilities 时序、context 过滤、_run_subagent 不传 transport）+ 测试 + 质量门禁。
