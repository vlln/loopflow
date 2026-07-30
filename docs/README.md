## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DESIGN` (新一轮迭代) |
| **设计评估** | 0.27.0 已发布（v0.27.0 tag 在 main，main+develop 已同步）：BL-046 Agent waiting_input 控制协议、BL-051 Web 二进制预览、BL-052 Run append prompt、BL-054 New Run declared args 契约；reconcile 契约对齐 ADR-0046（Spec v20）；Web strict manifest 89 场景全绿。新一轮迭代候选从 docs/backlog.md 拉取。 |
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
