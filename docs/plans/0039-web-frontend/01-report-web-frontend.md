---
title: Web Frontend Report
description: 记录 Runs、Loops、Backends 工作台、响应式布局与视觉验收证据。
type: report
status: complete
created: 2026-07-19T06:20:00Z
---

# 结果

完成 Carbon Mint Console Web Frontend。Runs、Loops、Backends 均使用真实 REST/SSE DTO；Runs 支持跨页聚合、URL selection、Run commands、Phase occurrence、Call/Event 隔离与 Run state；移动端采用单主视图，tablet Inspector 为可关闭抽屉。

# Acceptance Results

- [PASS] AC-014-N-1 AC-014-N-2 AC-014-N-3 AC-014-N-4 AC-014-N-5 AC-014-N-6 AC-014-N-7 AC-014-N-8 AC-014-B-1 AC-014-B-2 AC-014-E-1 AC-014-E-2 AC-014-F-1 AC-014-F-2 — commit caaa976
- [PASS] AC-015-N-1 AC-015-N-2 AC-015-N-3 AC-015-N-4 AC-015-N-5 AC-015-B-1 AC-015-B-2 AC-015-E-1 AC-015-E-2 AC-015-F-1 AC-015-F-2 — commit caaa976
- [PASS] AC-016-N-1 AC-016-N-2 AC-016-B-1 AC-016-B-2 AC-016-E-1 AC-016-E-2 AC-016-F-1 AC-016-F-2 — commit caaa976
- [PASS] AC-017-N-1 AC-017-N-2 AC-017-B-1 AC-017-B-2 AC-017-E-1 AC-017-E-2 AC-017-F-1 AC-017-F-2 — commit caaa976
- [PASS] AC-018-N-1 AC-018-N-2 AC-018-B-1 AC-018-B-2 AC-018-E-1 AC-018-E-2 AC-018-F-1 AC-018-F-2 — commit caaa976
- [PASS] AC-019-N-1 AC-019-N-2 AC-019-N-3 AC-019-N-4 AC-019-B-1 AC-019-B-2 AC-019-E-1 AC-019-E-2 AC-019-F-1 AC-019-F-2 AC-019-F-3 — commit caaa976

# Tests And Coverage

- Python: 273 passed, 1 skipped; project coverage 82.79%.
- Vitest: 8 passed; statements 100%, branches 85.71%, functions 87.01%, lines 100%.
- Playwright Chromium: 10 passed, 2 viewport-independent skips across 1440x900, 1024x768, 390x844.
- Strict AC manifest: 60 scenarios, no `planned::` nodes.
- `npm audit --audit-level=low`: 0 vulnerabilities.
- Production build and isolated wheel static-asset smoke: PASS.
- `./scripts/mr-gate.sh`: PASS.

# Commits

- `caaa976 feat(web): implement responsive operations console`

# Visual Evidence

- Playwright records trace for every run and writes full-page Runs/Backends screenshots per viewport.
- Assertions verify no page horizontal overflow, 500-character unbroken output containment, React Flow node bounds, non-transparent node pixels, and non-empty graph screenshots.
- Manual screenshot review caught and fixed hidden-container React Flow framing on 390px and the missing tablet drawer close control on 1024px.

# Risks

- Vite reports a non-blocking 512.06 kB minified main chunk (162.30 kB gzip). Current product is a compact local console; route-level splitting can be evaluated when workspace count or startup performance becomes material.
- Browser tests use deterministic route fixtures; Python integration/system tests cover server protocol, filesystem, process, security, and SSE behavior.
