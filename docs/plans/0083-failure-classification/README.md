# 0083 Agent 失败分类与重试/续接策略

对应阶段：`DEVELOP`（0.21.0 迭代，ADR-0044 / BR-049 / AC-026，BL-001）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Agent 失败分类与重试/续接策略](01-plan-failure-classification.md) | [Report](01-report-failure-classification.md) | done |

## 范围

- 失败五分类 auth/quota/transient/task/unknown；分类来源优先级：后端结构化上报（agent_done payload `error_category`）> stderr 模式匹配兜底 > unknown
- 策略：transient 保持既有 3/9/27s 退避重试（最多 3 次）行为完全不变；auth/quota/task/unknown 不自动重试直接失败
- `backends/manager.py` agent_done payload 携带 `error_category`（后端已知类别时）；异常分支不再纯吞，异常类型映射为分类（连接/超时类 → transient，其余 → unknown）
- `AgentError` 增加 `category` 字段（仅携带不做决策）；run.json 失败路径写 `error_category`（与 error_summary 并列）
- stderr 模式表扩充识别 auth/quota（保守：宁可 unknown 不可误判 transient）
- AC-026 全部 7 场景自动化测试 + recovery manifest 落实真实 test_node

## 非范围

- 各真实后端的结构化错误上报实现（尽力而为通道，本容器只定义协议与消费侧）
- recover retry/continue 恢复边界调整（BR-033 不变，AC-026-F-1 只验证分类不改变边界）
- AC-027（0084）/ AC-029（0085）场景实现
- goal 模式 exit code 3/6 语义调整（不变）
