---
title: mock ACP server 测试基建 Plan
description: 基于 agent-client-protocol SDK agent-side 实现可脚本化 mock ACP server + 5 行为模式 + 基建自证
type: plan
status: done
created: 2026-07-25T11:30:00Z
---

# Goal

为 0.22.0 ACP 路径（ADR-0049 / AC-030 共 6 场景）搭建 CI 可跑的 mock ACP 后端。mock server 基于官方 SDK agent-side 实现，跑成 stdio 子进程，让 loopflow 的 ACP transport 真实地 spawn 它。通过环境变量 `MOCK_ACP_MODE` 控制行为，覆盖 AC-030 全场景所需的后端行为模式。依据 ADR-0050。

# Constraints

- mock server 用 `agent-client-protocol` SDK agent-side（`acp.run_agent` + `Agent` Protocol），不手搓 JSON-RPC——验证 agent-side 契约
- mock server 是独立 Python 脚本（`tests/agent_support/mock_acp_server.py`），作为 stdio 子进程被 spawn，自身是 asyncio
- 不编写 AC-030 业务测试用例（DEVELOP 0089 职责）；本容器只交付 mock server + 自证
- 不实现 src/ 真实 AcpSdkBackend（DEVELOP 0089 职责）
- 自证聚焦：mock server 本身行为正确（initialize 握手、各脚本化模式、session/load 上下文、permission 流程），用最小 SDK client 直接驱动
- `agent-client-protocol` 放主依赖区（`[project] dependencies`）；ADR-0049 §8 定位为可选 extra `[acp]`，0088/0089 实现阶段先作普通依赖，最终 extra 划分留 DEVELOP/RELEASE

# Steps

1. `uv add agent-client-protocol` → 正式引入依赖到 pyproject `[project] dependencies`；uv.lock 更新
2. `tests/agent_support/mock_acp_server.py`（新）：实现 `MockAcpAgent(Agent)`，通过 `MOCK_ACP_MODE` 环境变量控制行为；入口 `if __name__ == "__main__": asyncio.run(run_agent(agent))`
3. `tests/infrastructure/test_mock_acp_support.py`（新）：自证测试——用 `spawn_agent_process` + 最小 Client 实现，验证各行为模式
4. 验证：pytest 全绿无回归；三既有 profile + agent profile `--allow-planned` 通过；mock 自证全绿
5. 回填 ADR-0050 Verification，promote proposed→accepted

# Acceptance

- mock server 行为模式清单全部可触发且自证通过：
  - normal：initialize 握手 → session/new → session/prompt → streaming 多类通知（thought/message/tool_call/tool_call_update/usage） → PromptResponse(stop_reason=end_turn)
  - permission：prompt 中发 tool_call + request_permission → client auto-approve → 不死锁 → end_turn
  - load_session：loadSession=true → session/new → prompt "remember X" → session/load 同 session_id → prompt "what" → 回答含 X（上下文保留）
  - startup_fail：进程启动即退出（非零）或 initialize 不响应
  - context_prefix：首条 agent_message_chunk 含 context 前缀文本
- `uv run pytest tests/ -q` 全绿，既有测试零回归
- `python3 scripts/check-ac-manifest.py --allow-planned` 与 `--profile recovery --allow-planned` 与 `--profile scheduling --allow-planned` 通过
- `python3 scripts/check-ac-manifest.py --profile agent --allow-planned` 通过（AC-030 6 场景 planned:: 占位保持）
- 本容器不涉及 AC-030 场景实现（planned:: 占位保持）

# Checkpoint

- mock server 实现完成后先手动跑一遍各模式确认行为，再写自证
- `uv add` 后先跑既有测试确认零回归，再写新自证
- 合入前全部 manifest 检查通过

# Exit

全部 Acceptance 通过，ADR-0050 Verification 回填并转 accepted，写 Report，合回 develop。
