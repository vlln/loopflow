## 决策列表

| 编号 | 标题 | 状态 | 关联 Spec |
|------|------|------|-------------|
| [0001](0001-tech-stack.md) | 技术栈选型 | accepted | Spec / ADR-0002 |
| [0002](0002-architecture.md) | 架构模式与目录结构 | accepted | Spec |
| [0003](0003-backend-reuse.md) | 后端代码复用策略 | accepted | Spec |
| [0004](0004-resume-mechanism.md) | Resume 恢复机制 | superseded | ADR-0036 替代 |
| [0005](0005-test-framework.md) | 测试框架选型 | accepted | Spec |
| [0006](0006-ci-platform.md) | CI 平台选型 | accepted | Spec |
| [0007](0007-coverage.md) | 覆盖率策略 | accepted | Spec |
| [0008](0008-deployment.md) | 部署策略：本地型发布 | accepted | Spec / BL-056 修订 |
| [0009](0009-phase-graph.md) | PhaseGraph 执行图与终端渲染 | superseded | ADR-0052 替代 |
| [0031](0031-loop-definition.md) | loop.md — loop 定义文件格式（frontmatter + body） | accepted | — |
| [0032](0032-dispatch-queue.md) | 调度机制：dispatch + queue + resource lock | accepted | — |
| [0033](0033-webui-architecture.md) | 本地 WebUI 技术栈与分层 | accepted | Spec v19 / ADR-0052 修订 |
| [0034](0034-web-event-run-lifecycle.md) | Web 事件与 Run 生命周期契约 | accepted | Spec v19 / ADR-0052 修订 |
| [0035](0035-webui-test-infrastructure.md) | WebUI 测试与交付基础设施 | accepted | Spec v12 / AC-0010 / Interface 0001 |
| [0036](0036-recovery-intervention.md) | 可校验恢复、可靠取消与人工介入 | accepted | Spec v13 / AC-0011 / Interface 0001 |
| [0037](0037-recovery-test-infrastructure.md) | 恢复控制测试基础设施 | accepted | ADR 0036 / AC-0011 / Interface 0001 |
| [0038](0038-grok-backend-transport.md) | Grok 后端传输策略 | accepted | AC-0001 AC-008 / ADR 0018 / ADR 0023 |
| [0039](0039-file-change-observation.md) | 工作目录文件变化观察层 | superseded | ADR-0052 替代 |
| [0040](0040-declared-phases-predisplay.md) | Declared Phases 预显示与合并语义 | superseded | ADR-0052 替代 |
| [0041](0041-sse-multi-topic-transport.md) | SSE 多 topic 传输层 | accepted | Spec v19 / ADR-0034 §5 / ADR-0052 修订 |
| [0042](0042-run-working-directory.md) | Run 显式工作目录 | accepted | Spec / AC-0013 / ADR-0039 / BL-020 §5 |
| [0043](0043-file-observation-baseline.md) | 文件观察基线快照语义 | superseded | ADR-0052 替代 |
| [0044](0044-failure-classification.md) | Agent 失败分类与重试/续接策略 | accepted | Spec v15 / AC-026 |
| [0045](0045-loop-failure-circuit-breaker.md) | Loop 失败熔断与 loop_state 存储 | accepted | Spec v15 / AC-027 |
| [0046](0046-stale-grace-period.md) | stale 失联宽限期 | accepted | Spec v15 / AC-029 |
| [0047](0047-queue-task-status.md) | 队列任务显式状态语义 | accepted | Spec v15 / AC-028 |
| [0048](0048-failure-injection-test-infra.md) | 失败注入测试基础设施 | accepted | ADR-0044~0047 / AC-026~029 |
| [0049](0049-adopt-python-acp-sdk.md) | 采用官方 Python ACP SDK 替换手搓 ACP 管道 | accepted | BL-014 / spike 通过（pi-acp 实跑） |
| [0050](0050-mock-acp-test-infra.md) | mock ACP server 测试基础设施 | accepted | ADR-0049 / AC-030 |
| [0051](0051-agent-body-excludes-frontmatter.md) | Agent body 剥离 frontmatter | accepted | BL-018 / ADR-0025 / ADR-0026 |
| [0052](0052-remove-phase.md) | 移除 Phase 抽象，改为 Agent 实例图 | accepted | ADR-0039 / ADR-0040 / ADR-0043 |
| [0053](0053-web-directory-picker.md) | Web 端跨平台目录选择器 | accepted | ADR-0042 / BL-009 |
| [0054](0054-webui-default-workdir-isolation.md) | WebUI/API 默认工作目录隔离 | accepted | ADR-0042 / BL-026 |
| [0055](0055-single-agent-run.md) | 单 agent 运行入口 | accepted | BL-047 / Spec v17 / AC-032 |
| [0056](0056-waiting-input-lifecycle.md) | waiting_input 生命周期：CLI 应答通道与无人值守策略 | accepted | BL-044 / BL-045 / ADR-0036 §5 / Spec v17 / AC-031 |
| [0057](0057-agent-intervention-protocol.md) | Agent intervention 控制协议与 capability preflight | accepted | BL-046 / Spec v18 / AC-023 |

## 状态说明

| 状态 | 含义 |
|------|------|
| draft | 草稿，编写中 |
| proposed | 编写完成，待出口把关审查 |
| accepted | 审查通过，当前生效 |
| superseded | 被新版 ADR 替代 |
| deprecated | 已废弃，不再适用 |
