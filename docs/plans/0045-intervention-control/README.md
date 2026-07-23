# 0045 Intervention Control

对应分支：`feat/0045-intervention-control`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [阻塞人工介入](01-plan-intervention-control.md) | [Report](01-report-intervention-control.md) | done |

## 范围

- workflow `intervene()` 请求持久化、等待输入、回答后重放
- Agent 结构化 intervention 控制输出和 durable session continue
- Intervention Web API、Run 读模型和 WebUI 回答控件
- AC-022 全部 11 个场景从 `planned::` 迁移到真实测试节点

恢复 AC-020 与可靠停止 AC-021 已完成，本执行容器不得改变其语义。
