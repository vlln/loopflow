## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `RELEASE` complete (v0.26.0) |
| **设计评估** | 0.26.0：BL-047 单 agent 运行入口（ADR-0055）、BL-044 CLI 内联应答 + loopflow respond、BL-045 intervene default/timeout + `--unattended`（ADR-0056）。549 Python + 41 前端 + 13 Playwright 全绿；严格 manifest：recovery 84 / scheduling 32 / agent 26 / singleagent 9 全过。tag v0.26.0，main + develop 已同步。既有债：BL-049（--write 无早退）、BL-050（web profile 无 TEST_NODES 机制）。 |
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
