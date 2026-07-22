# 0042 Recovery Controls Test Infrastructure

对应分支：`test/0042-recovery-controls-infra`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [恢复控制测试基建](01-plan-recovery-controls-infra.md) | [基建报告](01-report-recovery-controls-infra.md) | done |

## 范围

- 分段 Call cache 与 Intervention fixture
- durable/non-durable session Backend fake
- 原子写、Run lock、execution epoch、process group 和 clock 故障注入 double
- AC-020..022 planned manifest 与 v13 contract schema
- 正向冒烟和反向拦截自证

本容器不实现 recover、stop、intervene、Web endpoint 或前端业务交互。
