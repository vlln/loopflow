## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `TEST_INFRA` (0.27.0 基建修复) |
| **设计评估** | 0108 SYSTEM_TEST 的集成 99、CLI E2E 22 通过；strict manifest 暴露 Web profile generator 对 86 场景无条件生成 `planned::`，使 strict 门禁不可通过，分类为基建缺陷。其他五 profile strict 全绿。当前以 0109 修复 Web manifest 真实节点校验，TEST_INFRA 门禁通过后恢复 SYSTEM_TEST；0108 保持 pending。 |
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
