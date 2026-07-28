## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DEVELOP` — 0.25.1 patch fixes (BL-034~037) on `fix/0251-bugfixes` |
| **设计评估** | 0.25.1 patch：BL-034 远程 run 文件预览兜底 run_dir/work、BL-035 events 重复渲染去重（agent_start + agent_session）、BL-036 auto-detect backend 显示名修复、BL-037 file changes 文件夹折叠。520 Python + 42 前端 + 13 Playwright 全绿。待合并 develop。 |
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
