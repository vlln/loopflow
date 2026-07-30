## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `RELEASE` (0.27.0) |
| **设计评估** | 0108 SYSTEM_TEST 全绿：集成 146、E2E 22、六 profile strict manifest、Playwright 三视口 16、性能专项（Runs 首屏 p95<500ms）、安全（npm audit 0 漏洞、默认 loopback）、兼容（Python 3.10/3.14）。无阻塞级缺陷。develop 待发布。 |
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
