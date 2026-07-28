## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `SYSTEM_TEST` complete — 0.26.0 ready for RELEASE |
| **设计评估** | 0.26.0：BL-047 单 agent 运行入口（ADR-0055）、BL-044 CLI 内联应答 + loopflow respond、BL-045 intervene default/timeout + --unattended（ADR-0056）。549 Python + 41 前端 + 13 Playwright 全绿；严格 manifest：recovery 84 / scheduling 32 / agent 26 / singleagent 9 全过；web profile 严格化系既有债 BL-050（0.25.x 同） |
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
