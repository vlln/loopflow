## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `RELEASE` |
| **设计评估** | WebUI SYSTEM_TEST 全绿：集成 22/22、CLI E2E 13/13、全量 273 pass、strict manifest 60/60、Vitest 8/8、Chromium 10 pass；性能与安全专项通过 |
| **核心模块** | backend, runtime, discovery, CLI, graph, display, agent, skills, Web Application/API/Frontend 已实现；develop 为待发布状态，无阻塞级缺陷 |

<!-- Agent 中断恢复时，用 git log --oneline --grep="docs(state):\|docs(plan):" 重建上下文。 -->

## 子目录

| 路径 | 用途 |
|------|------|
| [vision.md](vision.md) | 全局顶层愿景 |
| [spec/](spec/) | Spec 需求规格（用户故事、模块划分、数据模型、非功能指标） |
| [interface/](interface/) | 接口定义（入参/出参/错误码，适用有 API 时） |
| [adr/](adr/) | 架构决策记录 |
| [plans/](plans/) | 任务执行计划 |
| [ac/](ac/) | 验收标准 |
