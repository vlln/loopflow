---
title: manifest strict 欠账清理 Report
description: AC-010-N-2/E-2 按 BL-010 裁决修 AC 文本对齐 ADR-0031 现行实现；web profile 6 个历史 planned（AC-015-F-3/N-7/N-8、AC-016-B-3/F-3、AC-019-B-3）实证后补真实测试或修 AC 文本；三 profile manifest strict 全绿
type: report
status: done
created: 2026-07-25T08:05:00Z
---

# Summary

8 个 `planned::` 占位全部转真实测试节点，三 profile（web 80 / recovery 69 / scheduling 32 scenarios）strict 全绿。其中 6 条是 AC 文本与实现漂移，按用户裁决（同 BL-010 方式：只修 AC 文本对齐实证行为，不改实现）处理；3 条 AC 文本与实现一致，直接补测试登记。零生产代码改动。

# 逐场景处理

| 场景 | 处理方式 | 测试节点 | 结果 |
|------|---------|---------|------|
| AC-010-N-2 | 修 AC 文本（漂移）+ 增强既有用例 | tests/unit/test_discovery.py::TestListLoops::test_no_loop_md_not_discoverable | [PASS] |
| AC-010-E-2 | 修 AC 文本（漂移）+ 增强既有用例 | tests/unit/test_discovery.py::TestLoopMd::test_loop_md_bad_yaml | [PASS] |
| AC-015-F-3 | 修 AC 文本（漂移）+ 新补 pytest | tests/integration/test_web_api.py::test_workflow_syntax_error_run_start_fails_without_placeholders | [PASS] |
| AC-015-N-7 | 修 AC 文本（漂移）+ 新补 vitest | web/src/App.test.tsx::AC-015-N-7: executed declared phase replaces its placeholder, others stay pending | [PASS] |
| AC-015-N-8 | 修 AC 文本（漂移）+ 新补 vitest | web/src/App.test.tsx::AC-015-N-8: undeclared runtime phase renders with the undeclared marker | [PASS] |
| AC-016-B-3 | AC 文本与实现一致，直接补 pytest | tests/integration/test_web_api.py::test_sse_stream_end_waits_for_file_changes_terminal | [PASS] |
| AC-016-F-3 | 修 AC 文本（漂移）+ 新补 pytest | tests/integration/test_web_api.py::test_sse_file_changes_read_failure_emits_stream_error_and_closes | [PASS] |
| AC-019-B-3 | AC 文本与实现一致，补 playwright（沿用 AC-019 视觉场景既有层） | web/tests/webui.spec.ts::light theme keeps panels and status badges legible | [PASS] |

# 漂移修正清单（实证依据）

| AC | 旧文本（关键差异） | 实证行为 | 证据 |
|----|------------------|---------|------|
| AC-010-N-2 | loop.md 缺失时「回退到读取 workflow.py meta」 | `list_loops` 对缺 loop.md 的目录直接跳过（loop.md 必选，ADR-0031），其他 loop 正常 | `src/loopflow/infrastructure/discovery.py:70-72`（`loop_md.is_file()` 否则 `continue`）；既有用例增强后断言合法 loop 并存时仅合法者被发现 |
| AC-010-E-2 | 非法 YAML「回退到读取 workflow.py meta」 | `_load_loop_meta` 打印 stderr 并 SystemExit，`list_loops` 捕获后跳过该 loop | `discovery.py:45-47, 79-80`；增强用例断言 stderr 含 `invalid YAML` 且合法 loop 不受影响 |
| AC-015-F-3 | 「workflow.py 语法错误，无法提取 meta.phases」 | declared phases 实际来自 loop.md frontmatter（`web_resources._extract_declared_phases`），workflow.py 不参与提取；启动 Run 时子进程 `load_loop` 失败 → `BackgroundRunExecutor.start` 抛 `RuntimeError("run_process_start_failed")` → API 500 `internal_error`，不创建 Run，Loop 详情与 declared_phases 不受影响，服务不崩溃 | `web_resources.py:59-76, 119-126`；`execution.py:289-297`；`server.py:123-124`；新 pytest 全链路断言 |
| AC-015-N-7 | 「SSE 推送 phase 事件 → 观察 phase graph 占位替换」 | phase graph 数据来自 Run 详情投影，SSE 事件只进 eventReducer/fileChanges，不直接更新图；占位替换在 Run 详情（重新）加载时按 title 匹配合并 | `App.tsx:106-114`（SSE 回调无 detail 刷新）、`api.ts:47-63`、`App.tsx:201-213`（合并逻辑） |
| AC-015-N-8 | 带「"undeclared" badge」 | 无文字 badge；undeclared 节点打 `is-undeclared` 类，accent 边框色（`--accent-undeclared`） | `App.tsx:198, 208-211`、`styles.css:249` |
| AC-016-F-3 | 「stream_error（topic=file_changes）；run_event 不受影响继续推送」 | fc 读取 OSError 非 ApplicationError，轮询路径落入 server `_events` 通用 `except Exception`：发 `stream_error {code: event_read_failed, last_event_id}`（无 topic 字段）后关闭连接，run_event 不再推送；首次 replay 抛错则在 200 头后写入 500 错误体 | `server.py:285-299`；scratch 脚本实证（/tmp，两变体）；新 pytest 固化轮询变体行为 |

AC-016-F-3 暴露一个真实缺陷候选：file_changes 读取 OSError 未像 `cursor_out_of_range`（AC-016-E-3，ApplicationError 路径）那样按 topic 隔离。按本容器约束未改行为、未强行实现，建议后续作为 backlog 项裁决（修实现按 topic 隔离 vs 维持现状）。

# Changes

| 层 | 内容 |
|----|------|
| `docs/ac/0004-scheduling.md` | AC-010-N-2/E-2 两行场景文本对齐 ADR-0031 现行行为 |
| `docs/ac/0010-webui.md` | AC-015-F-3/N-7/N-8、AC-016-F-3 四条场景文本对齐实证行为 |
| `docs/backlog.md` | BL-010 状态 done（关联迭代 0.21.0） |
| `tests/unit/test_discovery.py` | 两用例补「合法 loop 并存不受影响」断言；E-2 补 stderr `invalid YAML` 断言 |
| `tests/integration/test_web_api.py` | +3：AC-016-B-3（fake app 双 topic 门控）、AC-016-F-3（fake app fc OSError 实证行为）、AC-015-F-3（StartFailingExecutor 模拟子进程启动失败全链路） |
| `web/src/App.test.tsx` | +2：AC-015-N-7/N-8（installFetch 新增 `detailOverride` 选项注入 declared_phases/graph） |
| `web/tests/webui.spec.ts` | +1：AC-019-B-3（light colorScheme，面板沿祖先链解析有效背景与前景色对比、status 徽章 bg/fg 对比、截图） |
| `tests/scheduling_support/manifest.py` | TEST_NODES +2（AC-010-N-2/E-2） |
| `tests/system/scheduling_cases.json` / `cases.json` | 8 条换真实节点并同步 AC 文本；AC-015-F-3 expectations 改 `http_status 500 internal_error` |
| `tests/infrastructure/test_scheduling_manifest.py` | 计数断言对齐 32 implemented / 0 planned（旧断言硬编码 30/2 的欠账状态） |

# Commits

| commit | 内容 |
|--------|------|
| `cb5044a` | docs(plan): 0086 manifest strict 欠账清理容器与计划 |
| `11754ff` | docs(ac): AC-010 文本对齐 ADR-0031 现行行为（BL-010 裁决落地，backlog 置 done） |
| `79da2ae` | docs(ac): web 4 场景文本对齐现行实现（AC-015-F-3/N-7/N-8、AC-016-F-3 漂移修正） |
| `57d78ae` | test(scheduling): AC-010-N-2/E-2 用例补合法 loop 并存与 stderr 断言 |
| `113ad03` | test(web): AC-016-B-3/F-3 SSE 双 topic 门控与读取失败、AC-015-F-3 语法错误 loop 启动失败 |
| `ad669b0` | test(webui): AC-015-N-7/N-8 占位合并与 undeclared 标记、AC-019-B-3 light 主题对比 |
| `72278c8` | test(infra): manifest 8 场景真实节点 |
| `613efca` | test(infra): scheduling manifest 计数断言对齐 32/0 |

# Verification Results

| 层 | 结果 |
|----|------|
| `check-ac-manifest.py`（web，strict） | AC manifest ok: 80 scenarios |
| `check-ac-manifest.py --profile recovery`（strict） | AC manifest ok: 69 scenarios |
| `check-ac-manifest.py --profile scheduling`（strict） | AC manifest ok: 32 scenarios |
| `uv run pytest tests/ -q` | 495 passed, 1 skipped |
| `cd web && npm run test:coverage` | Test Files 3 passed, Tests 41 passed |
| `cd web && npm run build` | ✓ built |
| `npx playwright test webui.spec.ts` | 13 passed, 2 skipped（既有 viewport 条件 skip） |
| npm audit | 既有失败（BL-011：brace-expansion 经 @vitest/coverage-v8 链 5 high），与本容器无关，跳过 |

# Notes

- 零生产代码改动：所有漂移按裁决修 AC 文本，未触碰实现。
- uv.lock 的既有未提交修改与本任务无关，未触碰、未入任何 commit。
- AC-015-F-3 的 expectations 从 `dom/matches-ac` 改为 `http_status 500 internal_error`（与实证行为一致，通过 checker 的 code↔status 映射校验）。
