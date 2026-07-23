# 0044 Reliable Stop

对应分支：`feat/0044-reliable-stop`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [可靠停止](01-plan-reliable-stop.md) | [实现报告](01-report-reliable-stop.md) | done |

## 范围

- running/waiting_input Run 的永久取消状态机
- worker 进程身份持久化、进程组 SIGTERM/SIGKILL 和 PID 复用保护
- cancellation 与 execution epoch 的终态写保护
- Web API、CLI 兼容入口、WebUI Stop availability
- AC-021 全部 8 个场景从 `planned::` 迁移到真实测试节点

人工介入（AC-022）由后续独立执行容器实现。
