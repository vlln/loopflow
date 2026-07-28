# 0099 — Iteration 0.25.0

对应阶段：`DEVELOP`（增量迭代，从 v0.24.2 RELEASE 起步）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Retry 错误详情](01-plan-retry-error-details.md) | — | pending |
| 02 | [WebUI 错误布局收紧](02-plan-webui-error-layout.md) | — | pending |
| 03 | [Runs 左栏显示项目目录](03-plan-webui-runs-display.md) | — | pending |
| 04 | [工程债：npm audit + 版本单源](04-plan-eng-debt.md) | — | pending |

## 范围

- BL-031：agent retry hint 携带具体 schema 校验错误信息 + 类型兜底
- BL-032：error_banner 布局收紧（限高 + 截断）
- BL-033：Runs 左栏显示 working_directory 目录名替代 run_id
- BL-011：升级 @vitest/coverage-v8 + vitest 到 4.1.10（修复 brace-expansion 高危）
- BL-013：版本号单源化（__init__.py 用 importlib.metadata 读 pyproject.toml）

## 非范围

- 不改 retry 架构（ADR-0011 的 prompt 注入 + 重试机制不变，仅丰富 hint 内容）
- 不改失败分类策略（ADR-0044 的五分类不变）
- 不改 AC-029 的 stale 宽限期语义（BL-030 已在前一轮处理）
- 前端不新增组件，仅修改现有 JSX/CSS

## TEST_INFRA 增量检查

| 检查项 | 结论 | 依据 |
|--------|------|------|
| 测试基建 ADR 覆盖本轮需求 | ✅ 通过 | 无新测试层。BL-031 用 pytest 单元/集成，BL-032/033 用 vitest + Playwright |
| 测试框架/Mock 支持新模块 | ✅ 通过 | 既有 mock backend 覆盖 retry 场景，无新 Mock 需求 |
| 架构规则文件与契约一致 | ✅ 通过 | 无新 ADR/Spec 变更 |
| CI/门禁正常 | ⚠️ 上次 develop CI 有 failure（PR #12 合并时临时移除 frontend 检查导致） | 本轮 DEVELOP 的 PR 会重新触发 CI，需确认全绿 |

结论：无增量搭建需求，直接推进 DEVELOP。
