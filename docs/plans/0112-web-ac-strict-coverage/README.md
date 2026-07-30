# 0112 — Web AC strict 覆盖补齐

DEVELOP 阶段执行容器。目标：将 0111 冻结的 89 场景 Web manifest 中 71 个 `planned::` 节点补齐为真实测试节点（必要时补产品行为），使 `check-ac-manifest.py --profile web` strict 模式通过。0108 SYSTEM_TEST 保持 pending，本容器完成后从 Web strict 层恢复。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [AC-016 SSE 事件流](01-plan-ac016-sse.md) | 待完成后创建 | pending |
| 02 | [AC-017 Loops + AC-018 Backends](02-plan-ac017-ac018.md) | 待完成后创建 | pending |
| 03 | [AC-014 Runs 工作台](03-plan-ac014-runs.md) | 待完成后创建 | pending |
| 04 | [AC-015 AgentGraph](04-plan-ac015-agentgraph.md) | 待完成后创建 | pending |
| 05 | [AC-019 布局与可访问性](05-plan-ac019-layout.md) | 待完成后创建 | pending |

## 执行顺序与依赖

按 01 → 05 顺序执行（序号即依赖顺序：后端先行，UI/浏览器在后）。各单元独立 `feat/0112-*` 分支，从最新 `develop` 拉出，MR 门禁通过后合并。

## 共享汇聚点（前置声明）

各单元都会修改 `tests/web_support/ac_manifest.py` 的 `TEST_NODES`（追加映射）。约定：每个单元**只追加自己 AC 段的条目**，不得改动其他单元的映射；后合并者先 rebase 最新 `develop` 并重跑 MR 门禁，冲突仅在 `TEST_NODES` dict 内按 AC 段合并。`tests/system/cases.json` 由 generator 重新生成，不以手改解决冲突。

其他共享测试文件（`tests/integration/test_web_api.py`、`web/src/App.test.tsx`、`web/tests/webui.spec.ts`）各单元只追加新测试，不重构既有用例。
