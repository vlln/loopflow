---
title: AC-019 布局与可访问性覆盖报告
description: 0112-05 执行结果：14 个 planned 场景补齐，strict web 89 场景全绿
type: report
status: complete
created: 2026-07-30T00:00:00Z
---

# Summary

AC-019（WebUI 布局与可访问性）14 个 planned 场景全部补齐。至此 **strict web manifest 89 场景 0 planned，全绿**。0108 SYSTEM_TEST 的 Web strict 层阻塞解除，可从该层恢复。

# Acceptance Results

新写节点（5 个）：
| AC | 测试节点 | 结果 |
|----|----------|------|
| AC-019-N-2 | `App.test.tsx::AC-019-N-2: keyboard selection shows focus and fires a single recover retry` | [PASS] |
| AC-019-N-3 | `tests/integration/test_web_api.py::test_ac019_n3_default_binds_loopback_only` | [PASS] |
| AC-019-B-4 | `App.test.tsx::AC-019-B-4: long error_summary is clamped, traceback stays expandable` | [PASS] |
| AC-019-E-2 | `App.test.tsx::AC-019-E-2: SSE disconnect shows stream error and keeps last data` | [PASS] |
| AC-019-F-2 | `App.test.tsx::AC-019-F-2: statuses remain text/icon distinguishable without color` | [PASS] |

复用已有节点（9 个）：
| AC | 测试节点 |
|----|----------|
| AC-019-N-1 / B-1 / B-2 / E-1 | `webui.spec.ts::operates Runs without overflow and renders a nonblank agent graph`（多视口） |
| AC-019-N-4 | `tests/unit/test_web_cli.py::test_web_remote_opt_in_warns_and_serves` |
| AC-019-N-5 | `App.test.tsx::AC-019-N-5: theme toggle switches data-theme and persists` |
| AC-019-B-3 | `webui.spec.ts::light theme keeps panels and status badges legible` |
| AC-019-F-1 | `webui.spec.ts::all icon-only controls expose names and tooltips` |
| AC-019-F-3 | `tests/unit/test_web_cli.py::test_web_remote_bind_requires_explicit_opt_in` |

实现提交 `03f3e9c`。

# Verification

| 门禁 | 结果 |
|------|------|
| strict manifest（web profile） | **89 scenarios, 0 planned, 全绿** |
| infrastructure 回归 | 82 passed, 1 skipped |
| 全量 Python（非 system） | 687 passed, 1 skipped |
| Frontend | 65 passed |

# 附带修复

- `test_manifest_checker_rejects_mapping_drift_and_unmapped_nodes` 原假设存在 planned 场景（`next()` 取 planned），planned=0 时 StopIteration。重构为从 TEST_NODES 临时摘除两个场景模拟"未登记 mapped"，与 0 planned 终态兼容。
- AC-014-B-7 冻结 expectation 从 409 run_in_grace 更正为 200（0112-03 契约对齐的遗漏传导）。

# Acceptance Reasonableness

- N-3 断言真实监听 socket 可经 loopback 连接且 `create_server("0.0.0.0")` 无 opt-in 时抛错，未 mock 进程。
- N-2 断言键盘聚焦元素（`document.activeElement`）与 recover retry 请求只发一次（calls 过滤长度=1）。
- E-2 断言断线后既有内容保留且 stream error 状态可见。
- F-2 断言状态徽章含多种可区分文本，非仅颜色。
- B-4 的 `-webkit-line-clamp` 在 jsdom 不解析，改断言专用 clamp class 挂载与完整多行文本在 DOM、Traceback 可展开；视觉截断由样式类承载，截图证据由 Playwright 层（webui.spec.ts 多视口）覆盖。
