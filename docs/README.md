## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `TEST_INFRA` (0.27.0) |
| **设计评估** | Spec v18、AC-0011/0013/0015、Interface 0001 已 active，ADR-0057 已 accepted；独立审查与 BL-046 spike 均通过，人类已批量确认冻结。当前仅搭建和验证本轮增量测试基建：BL-051 契约闭环、BL-046 Agent waiting_input 协议、BL-052 append_prompt、BL-054 declared args 符合性；不得提前实现业务功能。 |
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
