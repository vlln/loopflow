# 0099 — Iteration 0.25.0

对应阶段：`DESIGN` → `DEVELOP`（增量迭代，从 v0.24.2 RELEASE 起步）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Retry 错误详情](01-plan-retry-error-details.md) | — | pending |
| 02 | [WebUI 错误布局收紧](02-plan-webui-error-layout.md) | — | pending |
| 03 | [Runs 左栏显示项目目录](03-plan-webui-runs-display.md) | — | pending |
| 04 | [工程债：npm audit + 版本单源](04-plan-eng-debt.md) | — | pending |

## 范围

- BL-031：agent retry hint 携带具体 schema 校验错误信息
- BL-032：error_banner 布局收紧（限高 + 可折叠）
- BL-033：Runs 左栏显示 working_directory 目录名替代 run_id
- BL-011：升级 @vitest/coverage-v8 + vitest 到 4.1.10（修复 brace-expansion 高危）
- BL-013：版本号单源化（__init__.py 用 importlib.metadata 读 pyproject.toml）

## 非范围

- 不改 retry 架构（ADR-0011 的 prompt 注入 + 重试机制不变，仅丰富 hint 内容）
- 不改失败分类策略（ADR-0044 的五分类不变）
- 不改 AC-029 的 stale 宽限期语义（BL-030 已在前一轮处理）
- 前端不新增组件，仅修改现有 JSX/CSS
