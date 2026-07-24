# 0052 取消恢复语义实现

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [取消恢复实现](01-plan-cancel-recovery-implementation.md) | [Report](01-report-cancel-recovery-implementation.md) | done |

## 背景

0050/0051 已冻结并同步测试契约。当前产品代码仍把 `cancelled` 当作只能 rerun 的终态，并在 waiting_input stop 时关闭 pending request。本容器实现应用层、读模型和 WebUI 的新语义。

## 范围

- `RunRepository.allowed_actions` 派生 cancelled recover/respond/continue actions
- `WebApplication.stop_run/recover_run/respond_intervention` 状态转换
- WebUI 在 cancelled + pending request 时展示 respond，在 cancelled 可恢复时展示 Retry/Continue
- 替换 0051 中 7 个 planned recovery manifest 节点

## 非范围

- 不实现通用原子提交事务系统
- 不改变 backend 真实 durable session 能力探测
- 不发布版本
