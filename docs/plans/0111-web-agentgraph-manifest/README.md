# 0111 — Web AgentGraph manifest 增量基建

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Web AgentGraph manifest 对齐](01-plan-web-agentgraph-manifest.md) | [Report](01-report-web-agentgraph-manifest.md) | done |

## 分支

`test/0111-web-agentgraph-manifest`（从 `develop` 拉出）

## 范围

- 将 Web manifest 从冻结前的 Phase/86 场景更新为 AgentGraph/89 场景
- 重新语义审查既有 TEST_NODES，只保留完整覆盖映射
- 自证 allow-planned 完整、strict 只拒绝真实缺口
