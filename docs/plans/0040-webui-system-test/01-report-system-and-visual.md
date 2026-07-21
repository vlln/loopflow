---
title: WebUI System And Visual Test Report
description: 记录 WebUI SYSTEM_TEST 的集成、黑盒、视觉、覆盖率与兼容性结果。
type: report
status: complete
created: 2026-07-19T07:10:00Z
---

# 结果

[PASS] 无失败用例，无阻塞级缺陷；无需进入修复循环。

| 测试层 | 通过/总数 | 失败用例 | 结果 |
|--------|----------|----------|------|
| 服务集成/API 契约 | 22/22 | — | PASS |
| Strict AC manifest | 60/60 | — | PASS |
| CLI E2E | 13/13 | — | PASS |
| Python 全量 | 273/274（1 skip） | — | PASS，coverage 82.79% |
| Vitest | 8/8 | — | PASS，四维最低 85.71% |
| Chromium | 10/10（2 非目标视口 skip） | — | PASS |
| Wheel smoke | 1/1 | — | PASS |

# Visual Evidence

Playwright 在 1440x900、1024x768、390x844 生成 Runs/Backends 截图和全程 trace。自动断言覆盖页面横向溢出、长文本 containment、React Flow 节点完整边界/非透明像素；人工复查未见重叠、裁切或空白 graph。

# 分类

未出现测试失败，因此没有基建缺陷、设计缺陷或局部 bug 分类项。Python 3.10/3.14 required checks 与当前 macOS Python 3.14 验证兼容性通过。
