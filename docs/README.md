## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DEVELOP` (0.27.0) |
| **设计评估** | Spec v18、AC-0011/0013/0015、Interface 0001 与 ADR-0057 已冻结；0106 增量测试基建已合并并通过 30 项自证、六 profile allow-planned 门禁和 Python CI。当前按 BL-046/051/052/054 创建 feature Plan，TDD 回填 recovery 的 14 个及 iteration027 的 29 个 `planned::` 节点；全部 feature 合并和提测门禁通过前不得进入 SYSTEM_TEST。 |
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
