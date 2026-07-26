# 0088 mock ACP server 测试基建

对应阶段：`TEST_INFRA`（0.22.0 迭代，服务 ADR-0049 / AC-030）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [mock ACP server 测试基建](01-plan-mock-acp-test-infra.md) | [Report](01-report-mock-acp-test-infra.md) | done |

## 范围

- 基于 `agent-client-protocol` SDK agent-side 实现可脚本化的 mock ACP server（`tests/agent_support/mock_acp_server.py`），作为 stdio 子进程被 spawn
- 行为模式清单（通过 `MOCK_ACP_MODE` 环境变量控制）：
  1. **normal**：streaming 多类通知（agent_thought_chunk / agent_message_chunk / tool_call / tool_call_update / usage_update）后 end_turn
  2. **permission**：发 tool_call 后 request_permission，验证 auto-approve 不死锁（AC-030-B-1）
  3. **load_session**：声明 loadSession=true，session/load 保留上下文（AC-030-F-1）
  4. **startup_fail**：启动即失败/超时（AC-030-E-1）
  5. **context_prefix**：首条 message chunk 含 context 文本（pi-acp 行为复现）
- 基建自证：`tests/infrastructure/` 新增自证测试，用最小 SDK client 直接驱动 mock server 验证各模式
- 正式引入依赖 `agent-client-protocol`（放主依赖区；ADR-0049 §8 定位为可选 extra，最终 extra 划分留 DEVELOP/RELEASE）
- 依据：ADR-0050 / ADR-0049 / AC-030

## 非范围

- AC-030 业务测试用例（DEVELOP 0089 职责）
- src/ 真实 AcpSdkBackend 实现（DEVELOP 0089 职责）
- ADR-0049 §8 的最终 extra 划分（DEVELOP/RELEASE 职责）
