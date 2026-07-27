## 当前系统状态

<!-- 状态变更时更新以下字段 -->

| 字段 | 值 |
|------|-----|
| **当前阶段** | `DESIGN` → TEST_INFRA (iter 0.25.0) |
| **设计评估** | v0.25.0 迭代：BL-031 schema 兜底+retry hint（coerce_json + 二次校验）+ BL-032 error_banner 布局 + BL-033 runs 左栏显示目录名 + BL-011 vitest 升级 + BL-013 版本单源化。Plan 0099，4 个执行单元。AC-026 N-5/B-3/E-2/E-3 + AC-014 B-6 + AC-019 B-4。独立审查通过。 |
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
