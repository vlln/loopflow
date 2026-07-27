## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DEVELOP` — BL-009 Web 端跨平台目录选择器已合并 develop，全量测试通过（Python 508 passed / 前端 42 passed），待下一轮 RELEASE |
| **设计评估** | BL-009 完成：GET /system/list-directory + 前端模态目录浏览器替代 macOS-only osascript（ADR-0053 accepted）。旧 POST /system/pick-directory 标注 deprecated，保留向后兼容。develop 上全量回归通过。 |
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
