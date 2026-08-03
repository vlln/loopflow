# 0113 — 0.28.0 增量测试基建

TEST_INFRA 增量执行容器（0.28.0 迭代）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [BL-059 子进程测试确定性](01-plan-bl059-subprocess.md) | [Report](01-report-bl059-subprocess.md) | pending |
| 02 | [BL-057/058 demo loop + 黑盒盲区](02-plan-demo-loop.md) | [Report](02-report-demo-loop.md) | pending |

## 执行位置

`develop`（TEST_INFRA 增量阶段）。分支 `ci/0113-0.28.0-test-infra` → develop。

## 增量检查结论（2026-08-03）

| 检查项 | 结论 | 依据 |
|--------|------|------|
| 既有测试基建 ADR 覆盖本轮需求 | 覆盖 | ADR-0014（mock 两档）、ADR-0035（WebUI 测试）、ADR-0050（mock ACP server）已 accepted，能力就绪 |
| 测试框架/Mock 支持新增模块 | 有增量 | demo loop 资产（生成 png/pdf + waiting_input 协议）不存在；BL-059 子进程时序竞态需修复 |
| 架构规则文件与契约一致 | 一致 | 本轮无 Spec/架构 ADR 变更（ADR-0008 修订不涉架构规则） |
| CI/门禁仍正常 | 正常 | PR #35/#36 五 checks 全绿 |

增量搭建仅对 01/02 两单元自证，既有基建不重跑。
