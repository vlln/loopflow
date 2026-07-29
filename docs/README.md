## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DESIGN` (0.27.0 Web 契约对齐) |
| **设计评估** | 0109 已修复 Web manifest 无条件 planned 和节点校验缺陷，基础设施 81 passed、1 skipped，独立复审通过；strict 随后准确拒绝 54 个未完整覆盖场景。语义审查确认 AC-015/Spec 的 Phase 契约未同步 accepted ADR-0052，AC-014-E-2 与现行 stale 语义冲突，另有有效 Web AC 覆盖缺口。因此从 TEST_INFRA 转回 DESIGN；详见 0109 Report。0108 SYSTEM_TEST 保持 pending，已通过层不重跑。 |
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
