# 执行容器 0101 — AC Manifest 增量（0.26.0 TEST_INFRA）

| 子任务 | Plan | Report | 状态 |
|--------|------|--------|------|
| AC-031/032 manifest 覆盖 + singleagent profile | [01-plan-ac-manifest.md](01-plan-ac-manifest.md) | [01-report-ac-manifest.md](01-report-ac-manifest.md) | done |

## 分支

`test/0101-ac-manifest`（从 `develop` 拉出）

## TEST_INFRA 增量检查结论

对照 0.26.0 DESIGN 增量（AC-031、AC-032、ADR-0055/0056）检查既有基建：

| 检查项 | 结论 | 依据 |
|--------|------|------|
| 既有测试基建 ADR 覆盖本轮需求 | 覆盖，无新增 ADR | 本轮无新测试层/新外部依赖：单 agent 入口走 CLI 集成测试（ADR-0005/0014），intervention 扩展走 recovery 测试设施（ADR-0037）；tty 交互由实现层可注入抽象 + CliRunner `input=` 覆盖，不需新基建 |
| 测试框架/Mock 支持新增模块 | **有缺口**：AC-031 使 recovery manifest 缺 11 个场景（mr-gate 红）；AC-032 无任何 profile 覆盖 | `python3 scripts/check-ac-manifest.py --profile recovery --allow-planned` 报 missing AC ids |
| 架构规则文件与最新契约一致 | 不适用（无架构约束规则文件变更需求） | 本轮无模块边界变更 |
| CI/门禁仍正常 | 待本容器修复 manifest 后验证 | 见 Report |

增量搭建范围：recovery manifest TARGETS 补 AC-031 ×11；新增 `singleagent` profile（manifest 模块 + cases.json + check-ac-manifest 注册 + mr-gate 两行）。
