# 0060 Agent structured intervention 测试契约

对应阶段：`TEST_INFRA`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Agent structured intervention 测试契约](01-plan-agent-intervention-test-infra.md) | [Report](01-report-agent-intervention-test-infra.md) | done |

## 背景

0059 冻结了新的人工介入抽象：Agent structured requests 是主路径，`intervene()` 是 workflow routing gate。当前实现仍是旧 schema/单 request/单 respond 口径，进入 DEVELOP 前需要先补 vNext AC、接口和测试契约。

## 范围

- 新增 Agent structured requests/options/batch respond 的 AC。
- 在 Web API interface 中声明 vNext request/read model 和 batch respond command。
- 增加 vNext contract schema 和反向自证。
- 更新 recovery manifest，让新增 AC 以 planned node 进入门禁。

## 非范围

- 不修改 `src/` 产品实现。
- 不修改 Web 前端业务实现。
- 不让当前旧实现伪装满足 vNext 契约。
