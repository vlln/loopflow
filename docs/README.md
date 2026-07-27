## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `RELEASE` complete (v0.25.0) |
| **设计评估** | v0.25.0 发布：BL-009 目录选择器 + BL-026 默认工作目录隔离 + BL-027 SSE detail 刷新 + traceback + BL-028 graph live-run join 边 + BL-029 Loops 切换性能 + BL-030 reconcile 宽限期移除。ADR-0053/0054 accepted。512 Python + 42 前端全绿。tag v0.25.0，main + develop 已同步。 |
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
