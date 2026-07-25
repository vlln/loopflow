## 决策列表

| 编号 | 标题 | 状态 | 关联 Spec |
|------|------|------|-------------|
| [0031](0031-loop-definition.md) | loop.md — loop 定义文件格式（frontmatter + body） | accepted | — |
| [0032](0032-dispatch-queue.md) | 调度机制：dispatch + queue + resource lock | accepted | — |
| [0033](0033-webui-architecture.md) | 本地 WebUI 技术栈与分层 | accepted | Spec v12 |
| [0034](0034-web-event-run-lifecycle.md) | Web 事件与 Run 生命周期契约 | accepted | Spec v12 |
| [0035](0035-webui-test-infrastructure.md) | WebUI 测试与交付基础设施 | accepted | Spec v12 / AC-0010 / Interface 0001 |
| [0036](0036-recovery-intervention.md) | 可校验恢复、可靠取消与人工介入 | accepted | Spec v13 / AC-0011 / Interface 0001 |
| [0037](0037-recovery-test-infrastructure.md) | 恢复控制测试基础设施 | accepted | ADR 0036 / AC-0011 / Interface 0001 |
| [0038](0038-grok-backend-transport.md) | Grok 后端传输策略 | accepted | AC-0001 AC-008 / ADR 0018 / ADR 0023 |
| [0039](0039-file-change-observation.md) | 工作目录文件变化观察层 | accepted | Spec v14 / AC-0012 / ADR-0041 |
| [0040](0040-declared-phases-predisplay.md) | Declared Phases 预显示与合并语义 | accepted | Spec v14 / AC-0009 / AC-0010 |
| [0041](0041-sse-multi-topic-transport.md) | SSE 多 topic 传输层 | accepted | Spec v14 / ADR-0034 §5 / ADR-0039 |
| [0042](0042-run-working-directory.md) | Run 显式工作目录 | accepted | Spec / AC-0013 / ADR-0039 |
| [0043](0043-file-observation-baseline.md) | 文件观察基线快照语义 | accepted | Spec / AC-0012 / ADR-0039 |
| [0044](0044-failure-classification.md) | Agent 失败分类与重试/续接策略 | accepted | Spec v15 / AC-026 |
| [0045](0045-loop-failure-circuit-breaker.md) | Loop 失败熔断与 loop_state 存储 | accepted | Spec v15 / AC-027 |
| [0046](0046-stale-grace-period.md) | stale 失联宽限期 | accepted | Spec v15 / AC-029 |
| [0047](0047-queue-task-status.md) | 队列任务显式状态语义 | accepted | Spec v15 / AC-028 |
| [0048](0048-failure-injection-test-infra.md) | 失败注入测试基础设施 | accepted | ADR-0044~0047 / AC-026~029 |
| [0049](0049-adopt-python-acp-sdk.md) | 采用官方 Python ACP SDK 替换手搓 ACP 管道 | proposed | BL-014 / spike 验证中 |

## 状态说明

| 状态 | 含义 |
|------|------|
| draft | 草稿，编写中 |
| proposed | 编写完成，待出口把关审查 |
| accepted | 审查通过，当前生效 |
| superseded | 被新版 ADR 替代 |
| deprecated | 已废弃，不再适用 |
