# 0089 ACP SDK 真实实现

对应阶段：`DEVELOP`（0.22.0 迭代，服务 ADR-0049 / AC-030）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [ACP SDK 真实实现](01-plan-acp-sdk-impl.md) | [Report](01-report-acp-sdk-impl.md) | done |

## 范围

- 用官方 `agent-client-protocol` SDK 替换手搓 ACP 管道（`transports/acp.py` + `backends/acp_backend.py`），正式实现 ADR-0049 的全部设计要点
- 新 `transports/acp_sdk.py`：SDK 承载 ACP 协议（spawn_agent_process + ClientSideConnection + Client Protocol）；sync/async 桥接 = 专属守护线程 + 持久事件循环
- 新 `backends/acp_sdk_backend.py`：BaseBackend 实现，notification 全量映射、session/new|load|prompt、permission auto-approve、capabilities 动态声明
- `manager.py`：transport="acp" 路由到 AcpSdkBackend；CLI-only 后端报错
- `runtime.py`：从 execution_options 读 transport/backend 传给 _make_backend
- `cli.py`：--transport（cli/acp）、--backend 选项
- grok ACP 路径处理（_GrokAcp 改走 AcpSdkBackend）
- AC-030 全 6 场景用 0088 mock server 跑真实测试
- manifest：agent_cases.json AC-030 planned:: 换真实 test_node

## 非范围

- 真实 pi-acp 端到端（CI 用 mock server，不依赖真实后端）
- ADR-0049 §8 的最终 extra 划分（`[acp]` extra 留 RELEASE）
- 新 ACP 后端适配（仅复用已有 pi-acp/grok agent stdio）

## 依据

- ADR-0049（accepted，含 spike 验证结论）
- ADR-0038（grok ACP 显式启用约束）
- Spec v16 BR-054~057、US-034
- AC-030（6 场景）
- 0088 mock ACP server 测试基建
