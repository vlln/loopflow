# 0059 Agent structured intervention 设计修订

对应阶段：`DESIGN`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Agent structured intervention 设计修订](01-plan-agent-intervention-design.md) | [Report](01-report-agent-intervention-design.md) | done |

## 背景

0058 的 WebUI 验证暴露出一个更高层抽象问题：人工介入的主路径不应是 workflow 作者写复杂 schema，而应是 Agent 结构化返回多个问题和预设选项。`intervene()` 仍有价值，但更接近 workflow routing/control gate。

## 范围

- 明确 Agent structured requests 是 Agent 继续执行所需输入。
- 明确 `intervene()` 是 workflow-level 路由/控制流 gate。
- 收敛 response 类型为 string，options 由 Agent 或 workflow 提供。
- 明确多 pending requests 的来源和 WebUI 形态。

## 非范围

- 不修改产品代码。
- 不修改测试代码。
- 不设计完整 JSON Schema form renderer。
