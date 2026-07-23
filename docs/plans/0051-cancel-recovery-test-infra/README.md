# 0051 取消恢复测试契约同步

对应阶段：`TEST_INFRA`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [取消恢复测试契约](01-plan-cancel-recovery-test-infra.md) | [Report](01-report-cancel-recovery-test-infra.md) | done |

## 背景

0050 已把 `cancelled` 重新定义为当前 execution attempt 被取消，并新增/修改 AC-021/022 场景。现有 recovery manifest 和测试夹具仍包含旧语义，例如 waiting_input stop 关闭 request、cancelled 不可 recover。进入 DEVELOP 前，测试基础设施必须能表达新契约。

## 范围

- 同步 AC-020..022 recovery manifest 映射
- 更新 fixture/contract 正反例，使 cancelled recover/respond 和 atomic continue forbidden 可被表达
- 将尚未实现的产品行为节点标记为 planned，供 DEVELOP 替换为真实测试
- 保持产品代码不变

## 非范围

- 不修改 `src/` 产品实现
- 不修改 Web 前端业务行为
- 不让当前未实现的新产品语义伪装为已通过
