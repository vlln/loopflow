## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DEVELOP` (0.27.0 Web AgentGraph strict 补齐) |
| **设计评估** | 0111 已将 Web manifest 对齐 89 个冻结场景；14 个现有节点经逐项语义审查完整成立，71 个保持 planned，4 个 superseded，strict 无其他错误。增量 infrastructure 82 passed、1 skipped，最终 subagent 复审 PASS。DEVELOP 仅补完整测试和必要产品行为；0108 SYSTEM_TEST 保持 pending，恢复时从 Web strict 层继续。 |
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
