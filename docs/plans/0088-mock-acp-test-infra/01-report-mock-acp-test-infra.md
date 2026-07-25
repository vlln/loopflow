---
title: mock ACP server 测试基建 Report
description: 基于 agent-client-protocol SDK agent-side 的可脚本化 mock ACP server（5 行为模式）+ 12 条基建自证结果留档
type: report
status: complete
created: 2026-07-25T12:00:00Z
---

# Summary

按 ADR-0050 完成 0.22.0 ACP 路径的 mock ACP server 测试基建：`tests/agent_support/mock_acp_server.py` 基于官方 `agent-client-protocol` SDK agent-side 实现，通过 `MOCK_ACP_MODE` 环境变量控制 5 种行为模式（normal/permission/load_session/startup_fail/context_prefix），作为 stdio 子进程被 SDK client `spawn_agent_process` 真实地 spawn。12 条基建自证全部通过，既有 507 测试零回归。`agent-client-protocol>=0.11.0` 落地主依赖区（ADR-0049 §8 extra 划分留 DEVELOP/RELEASE）。

# Changes

| 层 | 内容 |
|----|------|
| `tests/agent_support/mock_acp_server.py`（新） | `MockAcpAgent(Agent)` 实现，通过 `MOCK_ACP_MODE` 控制 5 行为模式；入口 `asyncio.run(run_agent(agent))` 跑成 stdio ACP server |
| `tests/infrastructure/test_mock_acp_support.py`（新） | 12 条基建自证，用 `spawn_agent_process` + `_NotificationCollector(Client)` 直接驱动 mock server |
| `pyproject.toml` | `agent-client-protocol>=0.11.0` 加入 `[project] dependencies` |
| `uv.lock` | agent-client-protocol + pydantic 依赖锁定 |
| `scripts/mr-gate.sh` | 接入 `--profile agent` manifest 检查（allow-planned + strict） |

# Mock Server 行为模式清单

| 模式 | MOCK_ACP_MODE | 行为 | 覆盖 AC |
|------|--------------|------|---------|
| normal | `normal`（默认） | thought → tool_call → tool_call_update → message → usage → end_turn | N-1, N-2 |
| permission | `permission` | tool_call + request_permission → auto-approve → end_turn | B-1 |
| load_session | `load_session` | loadSession=true，session/load 保留上下文 | F-1 |
| startup_fail | `startup_fail` | 进程立即退出（非零） | E-1 |
| context_prefix | `context_prefix` | 首条 agent_message_chunk 含 context 前缀 | N-2 context 过滤 |

# SDK Agent-Side API 用法

| 模块 | 类/函数 | 用法 |
|------|--------|------|
| `acp` | `run_agent(agent)` | 入口：创建 `AgentSideConnection` over stdio 并 listen |
| `acp.interfaces` | `Agent` Protocol | mock 实现：`initialize`/`new_session`/`load_session`/`prompt`/`on_connect`/... |
| `acp.agent.connection` | `AgentSideConnection` | `on_connect(conn)` 获得；`conn.session_update(sid, update)` 发通知；`conn.request_permission(sid, tc, opts)` 请求授权 |
| `acp.helpers` | `update_agent_message_text`/`update_agent_thought_text`/`start_tool_call`/`update_tool_call` | 构造 notification update 对象（自带 `session_update` discriminator） |
| `acp.schema` | `InitializeResponse`/`NewSessionResponse`/`LoadSessionResponse`/`PromptResponse`/`UsageUpdate`/`PermissionOption`/`ToolCallUpdate`/`AgentCapabilities` | 请求/响应模型 |
| `acp.stdio` | `spawn_agent_process(client, cmd, *args)` | client 侧：spawn agent 子进程 + 创建 `ClientSideConnection`（自证测试用） |

**关键坑**：`UsageUpdate` 和 `AllowedOutcome` 的 discriminator 字段（`session_update`/`outcome`）是 `Literal` 类型但**无默认值**，创建时必须显式传入。spike 的 `_AutoApproveClient.request_permission` 中 `AllowedOutcome(option_id=...)` 未传 `outcome="selected"`，但因 spike 从未触发真实权限请求而未暴露。本容器自证已覆盖此路径。

# Self-Test Results（tests/infrastructure/test_mock_acp_support.py）

| 自证项 | 测试 | 结果 |
|--------|------|------|
| normal initialize 握手 | test_mock_normal_initialize_handshake | [PASS] |
| normal 多类 streaming 通知 | test_mock_normal_streaming_multi_type_notifications | [PASS] |
| normal message 回显 | test_mock_normal_message_echoes_user_text | [PASS] |
| normal usage_update tokens | test_mock_normal_usage_update_has_tokens | [PASS] |
| permission 请求 + auto-approve | test_mock_permission_request_sent_and_auto_approved | [PASS] |
| permission 不死锁 | test_mock_permission_no_deadlock | [PASS] |
| permission tool_call 前置 | test_mock_permission_tool_call_before_request | [PASS] |
| load_session 声明能力 | test_mock_load_session_declares_capability | [PASS] |
| load_session 上下文保留 | test_mock_load_session_retains_context | [PASS] |
| startup_fail 非零退出 | test_mock_startup_fail_exits_nonzero | [PASS] |
| context_prefix 首条含 context | test_mock_context_prefix_first_chunk_has_context | [PASS] |
| context_prefix 仅首条 | test_mock_context_prefix_only_first_prompt | [PASS] |

# Verification Results

| 层 | 结果 |
|----|------|
| `uv run pytest tests/ -q` | 507 passed, 1 skipped（495 → 507，零回归） |
| `check-ac-manifest.py --allow-planned` | AC manifest ok: 80 scenarios |
| `check-ac-manifest.py --profile recovery --allow-planned` | AC manifest ok: 69 scenarios |
| `check-ac-manifest.py --profile scheduling --allow-planned` | AC manifest ok: 32 scenarios |
| `check-ac-manifest.py --profile agent --allow-planned` | AC manifest ok: 21 scenarios |
| mr-gate：Python 全量 + 覆盖率 | 507 passed, 1 skipped；覆盖率 81.96%（门禁 59%） |
| mr-gate：四 profile manifest | 均 ok |
| mr-gate：前端 typecheck / vitest / build | clean / 41 passed / 成功 |
| mr-gate：npm audit | **失败（既有问题，见 Notes）** |
| mr-gate：Playwright 浏览器测试 | 10 passed, 2 skipped（单独补跑） |
| mr-gate：wheel-smoke | wheel assets ok |

# Notes

- **ADR-0049 §8 依赖定位**：ADR-0049 将 `agent-client-protocol` 定位为可选 extra `[acp]`，但 0088/0089 实现阶段先放入主依赖区（`[project] dependencies`），因为 mock server 是测试基建需要它。最终 extra 划分（`[acp]` extra、`pip install loopflow[acp]`）留 DEVELOP/RELEASE 阶段。此决策与 ADR-0049 §8 不矛盾：§8 的"可选依赖"是最终形态，0088 是实现阶段的临时落地。
- **SDK discriminator 坑**：`UsageUpdate(session_update="usage_update", ...)` 和 `AllowedOutcome(outcome="selected", ...)` 的 discriminator 字段虽为 `Literal` 但无默认值，必须显式传入。spike 未触发真实权限请求，此坑在 0088 自证中首次暴露并修复。
- **mr-gate npm audit 既有失败**：`npm audit --audit-level=low` 报 5 high（brace-expansion 经 @vitest/coverage-v8 链），与本次改动无关（web/ 与 package-lock.json 零改动，develop 上同样失败）。门禁在 audit 处中断，其后的浏览器测试与 wheel-smoke 单独补跑（结果见上表）。
- **AC-030 6 场景保持 planned::**：本容器不写 AC-030 业务用例（DEVELOP 0089 职责）。agent profile manifest 21 scenarios 中 AC-030 6 场景以 `planned::` 占位保持，待 0089 实现。
- **mr-gate 接入 agent profile**：`scripts/mr-gate.sh` 新增 `--profile agent` 检查（allow-planned + strict），与 recovery/scheduling 同模式。
