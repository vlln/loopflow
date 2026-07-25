---
title: ADR 0050 — mock ACP server 测试基础设施
description: 用 agent-client-protocol SDK agent-side 实现可脚本化 mock ACP server（5 行为模式）作为 CI 可跑的 ACP 后端替身；自证落在 tests/infrastructure，不写 AC-030 业务用例
type: adr
status: proposed
created: 2026-07-25T11:30:00Z
---

# ADR 0050: mock ACP server 测试基础设施

## Context

0.22.0 DESIGN 冻结了 ADR-0049（采用官方 Python ACP SDK）和 AC-030（ACP 后端 loop 端到端，6 场景：N-1/N-2/B-1/B-2/E-1/F-1），但 CI 无可用 ACP 后端：

- 真实 `pi-acp` 消耗 quota、不可在 CI 重复跑、行为不可控（无法按需触发 permission、load_session、失败）
- AC-030-B-1 需要后端发 `request_permission`——pi-acp 在无工具调用时不发，无法覆盖
- AC-030-E-1 需要后端启动失败——真实后端无法按需制造
- AC-030-F-1 需要 `session/load` 保留上下文——需要可复现的 session 状态

没有这层基建，DEVELOP 阶段 AC-030 的 6 场景无法在 CI 下跑通，每次验证都依赖手动连 pi-acp。

## Decision

### 1. 基于官方 SDK agent-side 实现 mock server

mock ACP server 用 `agent-client-protocol` 包的 agent-side API（`acp.run_agent` + `Agent` Protocol + `AgentSideConnection`）实现，而非手搓 JSON-RPC。理由：

- mock server 自身走与真实后端相同的 SDK 代码路径（initialize/new_session/load_session/prompt + session_update notification），验证的是 agent-side 契约本身
- SDK 提供 Pydantic schema 模型，mock 不需要自行实现分帧/handshake
- spike（ADR-0049）已验证 SDK 的 agent-side 与 client-side 互通；mock 复用同一 SDK 版本

### 2. 行为脚本化协议

mock server 通过 `MOCK_ACP_MODE` 环境变量控制行为模式，覆盖 AC-030 全场景所需后端行为：

| 模式 | 行为 | 覆盖 AC |
|------|------|---------|
| `normal`（默认） | streaming 多类通知（thought/message/tool_call/tool_call_update/usage）后 end_turn | N-1, N-2 |
| `permission` | prompt 中发 tool_call + request_permission，auto-approve 后继续 | B-1 |
| `load_session` | 声明 loadSession=true，session/load 保留上下文 | F-1 |
| `startup_fail` | 启动即退出（非零）或 initialize 不响应 | E-1 |
| `context_prefix` | 首条 agent_message_chunk 含 context 前缀（pi-acp 怪癖复现） | N-2 context 过滤 |

### 3. stdio 子进程

mock server 是独立 Python 脚本（`tests/agent_support/mock_acp_server.py`），通过 `asyncio.run(run_agent(agent))` 跑成 stdio ACP server。loopflow 的 AcpSdkBackend（0089 实现）用 `spawn_agent_process` 真实地 spawn 它，与 spawn pi-acp 走完全相同的代码路径。

### 4. 自证在 tests/infrastructure/

基建自证用最小 SDK client（`spawn_agent_process` + `_TestClient`）直接驱动 mock server，验证各行为模式：

- initialize 握手返回正确 protocol_version/agent_capabilities/loadSession
- normal 模式：多类 streaming 通知 + end_turn
- permission 模式：request_permission 到达 client、auto-approve 放行、不死锁
- load_session 模式：session/new → prompt → session/load 同 session_id → prompt 上下文保留
- startup_fail 模式：进程启动失败
- context_prefix 模式：首条 chunk 含 context 前缀

**不编写 AC-030 业务用例**——那是 DEVELOP 0089 职责。

### 5. 依赖落地

`agent-client-protocol` 在本容器正式引入为**主依赖**（pyproject `[project]` dependencies）。ADR-0049 §8 将其定位为可选 extra `[acp]`，但 0088/0089 实现阶段先作为普通依赖装在主依赖区——mock server 是测试基建需要它，RELEASE 前再定 extra 划分。此决策与 ADR-0049 §8 的关系：§8 的"可选依赖"是最终形态，0088 是实现阶段的临时落地，最终 extra 划分留 DEVELOP/RELEASE。

## Alternatives

| 方案 | 评估 |
|------|------|
| 录制/回放真实 pi-acp 流 | 不采纳。脆——pi-acp 输出随版本/上下文变化；难覆盖 permission/load 分支（录制时碰不到）；回放器需自行实现分帧 |
| 手搓 JSON-RPC echo server | 不采纳。绕过 SDK，不能验证 agent-side 契约；mock 与真实后端走不同代码路径，等于自测自 |
| 在 src/ 实现 AcpSdkBackend 后直接连 pi-acp 测 | 不采纳。pi-acp 消耗 quota、CI 不可重复、行为不可控（无法触发 permission/失败）；AC-030 全场景无法在 CI 跑通 |

## Consequences

- 服务 ADR-0049 / AC-030；本 ADR 自身不引入 AC，正确性由 tests/infrastructure 自证测试证明
- DEVELOP 0089 实现 src/ AcpSdkBackend 后，AC-030 业务测试用 mock server 作为后端替身
- `agent-client-protocol` + `pydantic` 进入主依赖区；RELEASE 阶段重新评估 extra `[acp]` 划分
- 生产代码（src/）零改动；若 DEVELOP 发现 mock 行为缺口，回本容器扩展而非就地发散

## Architecture Boundary

全部落在 `tests/`：`agent_support/mock_acp_server.py`（mock ACP server + 行为脚本化）、`tests/infrastructure/test_mock_acp_support.py`（自证）。src/ 一行不改。依赖变更仅在 `pyproject.toml` / `uv.lock`。

## Verification

（搭建完成后回填）
