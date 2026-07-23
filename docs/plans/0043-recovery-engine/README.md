# 0043 Recovery Engine

对应分支：`feat/0043-recovery-engine`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [确定性恢复引擎](01-plan-recovery-engine.md) | [实现报告](01-report-recovery-engine.md) | done |

## 范围

- 新 Call cache、input digest、稳定顺序/并行 Call ID 与生命周期段 reader
- failed Run 的 retry/continue 确定性重放、execution epoch 与 Run lock
- Backend durable session capability 和 session ID 及时持久化
- `recover` 应用命令、Web API、CLI deprecated `resume` alias
- WebUI Retry/Continue availability
- AC-020 全部 13 个场景从 `planned::` 迁移到真实测试节点

可靠停止（AC-021）与人工介入（AC-022）由后续独立执行容器实现。
