## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `SYSTEM_TEST` complete — 0.25.1 patch (BL-034~041) ready for RELEASE |
| **设计评估** | 0.25.1 patch：BL-034 远程 run 文件预览兜底、BL-035 events 去重、BL-036 backend 显示名、BL-037 文件夹折叠、BL-038 Loops 页移除运行时状态、BL-039 切换 run 清空旧 detail、BL-040 Backends API 优化、BL-041 workspace 持久化 + missing catch。520 Python + 41 前端 + 13 Playwright 全绿。待合并 develop。 |
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
