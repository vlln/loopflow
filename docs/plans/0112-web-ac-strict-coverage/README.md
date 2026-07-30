# 0112 — Web AC strict 覆盖补齐

DEVELOP 阶段执行容器。目标：将 0111 冻结的 89 场景 Web manifest 中 71 个 `planned::` 节点补齐为真实测试节点（必要时补产品行为），使 `check-ac-manifest.py --profile web` strict 模式通过。0108 SYSTEM_TEST 保持 pending，本容器完成后从 Web strict 层恢复。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [AC-016 SSE 事件流](01-plan-ac016-sse.md) | [Report](01-report-ac016-sse.md) | done |
| 02 | [AC-017 Loops + AC-018 Backends](02-plan-ac017-ac018.md) | [Report](02-report-ac017-ac018.md) | done |
| 03 | [AC-014 Runs 工作台](03-plan-ac014-runs.md) | [Report](03-report-ac014-runs.md) | done |
| 04 | [AC-015 AgentGraph](04-plan-ac015-agentgraph.md) | [Report](04-report-ac015-agentgraph.md) | done |
| 05 | [AC-019 布局与可访问性](05-plan-ac019-layout.md) | [Report](05-report-ac019-layout.md) | done |

## 执行顺序与依赖

按 01 → 05 顺序执行（序号即依赖顺序：后端先行，UI/浏览器在后）。各单元独立 `feat/0112-*` 分支，从最新 `develop` 拉出，MR 门禁通过后合并。

## 共享汇聚点（前置声明）

各单元都会修改 `tests/web_support/ac_manifest.py` 的 `TEST_NODES`（追加映射）。约定：每个单元**只追加自己 AC 段的条目**，不得改动其他单元的映射；后合并者先 rebase 最新 `develop` 并重跑 MR 门禁，冲突仅在 `TEST_NODES` dict 内按 AC 段合并。`tests/system/cases.json` 由 generator 重新生成，不以手改解决冲突。

其他共享测试文件（`tests/integration/test_web_api.py`、`web/src/App.test.tsx`、`web/tests/webui.spec.ts`）各单元只追加新测试，不重构既有用例。

## 提测门禁审查（DEVELOP 收尾，Agent 判断）

| 审查内容 | 结论 | 依据 |
|----------|------|------|
| 所有 Plan Report 测试报告完整 | PASS | 5 份 Report 均含验收表 + Verification 段，测试数逐层记录（Python 687、前端 65、基建 82） |
| 所有 AC 四场景已标注，无遗漏 | PASS | strict web manifest 89 场景 0 planned，全部映射真实节点；4 个 superseded 已在 AC-0010 正文标注替代关系 |
| 覆盖率达标 | PASS | 前端 statements 88.88%/branches 82.65%/functions 85.21%/lines 95.79%，与 0107 基线（87.46/81.06/83.45/94.62）相比不降反升；Python 层 687 passed 无新增失败 |
| strict manifest 通过 | PASS | `check-ac-manifest.py --profile web`：89 scenarios ok |

## Report 验收合理性审查（防放宽断言/hack 过门禁）

| 审查内容 | 结论 | 依据 |
|----------|------|------|
| PASS 的 AC 可反向定位 | PASS | 抽查 AC-016-N-1/AC-014-B-7/AC-015-E-2/AC-019-N-3，均可定位到具体测试函数与实现提交（git log --grep AC-xxx 可考） |
| 测试有实质断言 | PASS | 断言覆盖 HTTP 状态/错误码 details、SSE 事件序列、图结构（nodes/edges/current）、DOM 存在性与 class、socket 连接、malformed 精确结构，非"不抛异常"。产品修复类（B-6/E-2/E-3/B-3）均先跑红确认缺口再修复 |
| 失败/跳过有解释 | PASS | 无失败；1 个 skip 为既有 viewport 边界固定（与本轮无关） |
| 实现范围与 diff 相称 | PASS | 4 处产品修复（working_directory、malformed reason、label fallback、declared_phases）与对应 AC oracle 一一对应，diff 聚焦 |

**结论：提测门禁通过，可推进 SYSTEM_TEST（从 0108 Web strict 层恢复）。**
