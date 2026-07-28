# 执行容器 0102 — 0.26.0 迭代（BL-047 + BL-044 + BL-045）

| 子任务 | Plan | Report | 状态 |
|--------|------|--------|------|
| BL-047 单 agent 运行入口（ADR-0055 / AC-032） | [01-plan-single-agent.md](01-plan-single-agent.md) | [01-report-single-agent.md](01-report-single-agent.md) | pending |
| BL-044+045 waiting_input 生命周期（ADR-0056 / AC-031） | [02-plan-waiting-input.md](02-plan-waiting-input.md) | [02-report-waiting-input.md](02-report-waiting-input.md) | pending |

## 分支

`feat/0102-single-agent-waiting-input`（从 `develop` 拉出）

## 契约

- ADR：[0055](../adr/0055-single-agent-run.md)、[0056](../adr/0056-waiting-input-lifecycle.md)（accepted）
- AC：[AC-032](../ac/0014-single-agent-run.md)、[AC-031](../ac/0011-recovery-intervention.md)（active）
- Spec v17：US-035/036/037、BR-058~061、Intervention 表新字段
- Manifest：singleagent profile（AC-032）、recovery profile（AC-031）的 planned:: 节点需在本容器回填为真实测试节点
