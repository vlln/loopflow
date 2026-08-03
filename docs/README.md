## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DEVELOP` (0.28.0) |
| **设计评估** | 0.28.0 迭代：TEST_INFRA 增量闭环（0113 done — BL-059 子进程确定性、BL-057/058 demo loop 黑盒），MR 门禁全绿（693 Python + 65 前端 + 16 Playwright）。进入 DEVELOP：本轮无新增 Spec/AC（BL-057/058 仅测试资产），BL-059 已随基建修复，无待开发业务特性。 |
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
