## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `SYSTEM_TEST` (0.27.0) |
| **设计评估** | 0112 已补齐 Web manifest 全部 71 个 planned 场景，strict web 89 场景 0 planned 全绿；提测门禁与 Report 验收合理性审查通过。过程中对齐 ADR-0046 reconcile 契约（Spec v20/AC-014-B-7/AC-029-B-1/Interface 0001）、修复 recovery manifest 节点存在性检查基建缺陷、4 处产品修复。0108 SYSTEM_TEST 从 Web strict 层恢复，已通过层不重跑。 |
| **核心模块** | backend, runtime, discovery, CLI, graph, display, agent, skills, Web Application/API/Frontend 已实现 |

<!-- Agent 中断恢复时，用 git log --oneline --grep="docs(state):\|docs(plan):" 重建上下文。 -->

## 子目录

| 路径 | 用途 |
|------|------|
| [backlog.md](backlog.md) | 工程需求池：迭代候选 |
| [vision.md](vision.md) | 全局顶层愿景 |
| [spec/](spec/) | Spec 需求规格（用户故事、模块划分、数据模型、非功能指标） |
| [interface/](interface/) | 接口定义（入参/出参/错误码，适用有 API 时） |
| [adr/](adr/) | 架构决策记录 |
| [plans/](plans/) | 任务执行计划 |
| [ac/](ac/) | 验收标准 |
