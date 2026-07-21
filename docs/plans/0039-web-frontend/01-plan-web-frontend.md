---
title: Web Frontend Plan
description: 按 Carbon Mint Console 规范实现 Runs、Loops、Backends 三个响应式主从工作台。
type: plan
status: done
created: 2026-07-19T06:20:00Z
---

# Context

`references/DESIGN.md` 是视觉唯一标准；四个 prototype 只提供结构概念，不提供产品细节。0038 已提供 Interface 0001 REST/SSE。

# Request

实现可实际操作的 Runs、Loops、Backends WebUI，包含列表/筛选、Phase occurrence/Calls、Call 过程、Loop 文件预览、Backend diagnostics、Run commands、SSE reducer 和响应式导航。

# Output Format

- React/TypeScript components、API client、SSE reducer、React Flow graph。
- Vitest 组件/reducer 测试。
- Playwright 三视口系统、交互、布局、像素与截图测试。
- production build 同步进 wheel static。

# Constraints

1. 严格遵守 `references/DESIGN.md` 的颜色、字号、间距、圆角和无渐变/阴影规则。
2. Runs 列表常驻左侧；不得建立独立 Runs list 页面。
3. Phase 为聚合图，occurrence 以 phase_id 分离；不得伪造 Phase state/input/output。
4. 移动端单主视图，文字与控制不得重叠或横向溢出。
5. 状态不可只靠颜色；icon button 有 accessible name/tooltip。

# Checkpoint

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Runs | list/filter/actions/graph/occurrence/calls/events/SSE 正确 | Vitest + Playwright + Python lifecycle tests PASS |
| Loops | list/detail/markdown/workflow/agents/file errors/related Runs 正确 | Vitest + Playwright + resource tests PASS |
| Backends | real DTO/diagnostic/redaction/unknown/empty 正确 | Vitest + Playwright + resource tests PASS |
| Responsive | 1440/1024/390 无横滚、重叠，主流程可达 | Chromium 10 PASS / 2 viewport-independent skips |
| Visual | Carbon Mint tokens、React Flow 非空像素、截图通过 | 三视口 screenshots + node bounds/pixels PASS |
| Quality | TypeScript 四维 coverage >=80%，MR gate 全绿 | 100/85.71/87.01/100；MR gate PASS |

# Steps

1. 建立 typed API/SSE client 与 deterministic reducer。
2. 实现 shell/navigation/status primitives。
3. 实现 Runs 三列工作台和 responsive modes。
4. 实现 Loops 文件预览工作台。
5. 实现 Backends 状态与 diagnostics 工作台。
6. 编写 Vitest/Playwright、截图与无重叠断言。
7. build/sync、MR gate、Report 与 submission gate。

# Acceptance

- AC-014-N-1
- AC-014-N-2
- AC-014-N-3
- AC-014-N-4
- AC-014-N-5
- AC-014-N-6
- AC-014-N-7
- AC-014-N-8
- AC-014-B-1
- AC-014-B-2
- AC-014-E-1
- AC-014-E-2
- AC-014-F-1
- AC-014-F-2
- AC-015-N-1
- AC-015-N-2
- AC-015-N-3
- AC-015-N-4
- AC-015-N-5
- AC-015-B-1
- AC-015-B-2
- AC-015-E-1
- AC-015-E-2
- AC-015-F-1
- AC-015-F-2
- AC-016-N-1
- AC-016-N-2
- AC-016-B-1
- AC-016-B-2
- AC-016-E-1
- AC-016-E-2
- AC-016-F-1
- AC-016-F-2
- AC-017-N-1
- AC-017-N-2
- AC-017-B-1
- AC-017-B-2
- AC-017-E-1
- AC-017-E-2
- AC-017-F-1
- AC-017-F-2
- AC-018-N-1
- AC-018-N-2
- AC-018-B-1
- AC-018-B-2
- AC-018-E-1
- AC-018-E-2
- AC-018-F-1
- AC-018-F-2
- AC-019-N-1
- AC-019-N-2
- AC-019-N-3
- AC-019-N-4
- AC-019-B-1
- AC-019-B-2
- AC-019-E-1
- AC-019-E-2
- AC-019-F-1
- AC-019-F-2
- AC-019-F-3
