---
title: 0.27.0 系统测试报告
description: develop 全量系统测试：集成/E2E/六 profile strict/Playwright 三视口/性能安全兼容专项
type: report
status: complete
created: 2026-07-30T00:00:00Z
---

# Summary

0.27.0 SYSTEM_TEST 全量验证通过，无阻塞级缺陷。HEAD `84e53df`。所有测试层全绿，建议推进 RELEASE。

# 测试摘要

| 测试层 | 通过/总数 | 失败 | 耗时 |
|--------|----------|------|------|
| 服务集成测试 (tests/integration) | 146/146 | — | ~60s |
| CLI E2E (tests/e2e) | 22/22 | — | 0.25s |
| 六 profile strict manifest | 全绿 | — | — |
| Playwright 三视口 (browser) | 16/16 (2 skip) | — | 4.4s |
| 性能专项 (Runs 首屏 p95) | 1/1 | — | 3.3s |

结论: **[PASS] 全部通过**

# 分层结果

## 集成测试
- `tests/integration`：146 passed（含新增 `test_web_performance.py` 性能专项）。无失败。
- `tests/e2e`：22 passed。

## strict manifest（六 profile）
| profile | 结果 |
|---------|------|
| web | 89 scenarios ok |
| recovery | 98 scenarios ok |
| scheduling | 32 scenarios ok |
| agent | 26 scenarios ok |
| singleagent | 9 scenarios ok |
| iteration027 | 29 scenarios ok |

## 系统/视觉测试（Playwright 三视口 1440/1024/390）
16 passed，2 skipped（既有 viewport 边界固定，与本轮无关）。三栏布局、AgentGraph LR、light 对比度、图标 accessible name、千条 Runs 可达性均通过。

## 专项测试

**性能**：新增 `tests/integration/test_web_performance.py::test_runs_first_paint_p95_under_500ms`。fixture 1000 Runs（run.json ~2KB）+ 所选 Run 1000 条 1KB 事件，预热后 30 次测量，`/runs?limit=50` 与 `/runs/{id}` p95 均 < 500ms，符合 Spec §7 NFR。
（SSE 实时性 p95 < 500ms 已由 AC-016-B-2 在 DEVELOP 层覆盖，按测试执行边界不重复。）

**安全**：
- 依赖漏洞：`npm audit` 0 vulnerabilities；CI/MR 门禁含 `npm audit --audit-level=low`（.github/workflows/test.yml、scripts/mr-gate.sh），SAST 已覆盖。
- 网络暴露：默认仅绑定 127.0.0.1（AC-019-N-3/F-3 覆盖），远程需 `--allow-remote` 显式 opt-in。
- 敏感信息：后端诊断 stderr token 脱敏（AC-018-N-2），文件读取限制在 Loop/Run 根目录（AC-017-E-1/E-2）。

**兼容性**：Python 3.10 与 3.14 双版本 CI 均通过；macOS/Linux 目标。legacy/unversioned JSONL 时间线与 unattributed 标记由 AC-015-E-1/F-4 覆盖。

# 失败分类

无失败用例，无需分类。

# 阻塞级缺陷判定

逐条对照 Spec 用户故事优先级、数据完整性、安全、功能可用性：
- 核心用户故事均可完成（BL-046/051/052/054 链路全绿）。
- 无数据损坏或丢失。
- 无安全问题（bind 默认 loopback、token 脱敏、路径越界 403）。
- 无功能失效。

**判定：无阻塞级缺陷。**

# 备注

- Playwright 运行前需 `npm run build` 生成 `web/dist`（webServer 服务静态产物），本次已在 develop 上构建后执行。
- 付费外部 Agent 依赖：本轮不涉及付费调用，ACP 兼容性使用本地 mock（见 plan Constraints），沙箱验证不适用。

# 建议

推进 RELEASE。
