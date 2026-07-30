## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `TEST_INFRA` (0.27.0 Web AgentGraph 增量基建) |
| **设计评估** | 0110 已将 ADR-0052 传导至 Spec v19、AC-0010/0012、ADR-0033/0034/0041 与 Web Interface；独立审查全部 PASS，并经人类批量确认冻结。原 strict 54 个缺口保持诚实：17 个 AC-015 场景按 AgentGraph oracle 重评，37 个有效 Web 场景继续补覆盖，另新增 3 个场景。0108 SYSTEM_TEST 保持 pending，已通过层不重跑。 |
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
