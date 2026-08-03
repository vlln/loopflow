---
title: 0.28.0 系统测试 — Report
description: 0.28.0 SYSTEM_TEST 全层结果与失败分类
type: report
status: complete
created: 2026-08-03T00:00:00Z
---

# Report — 0.28.0 系统测试

## 结论

SYSTEM_TEST 全层通过，无阻塞级缺陷，可进入 RELEASE。

## 执行信息

- develop HEAD：`3791d9c`（工作树干净）
- 时间：2026-08-03

## 测试层结果

| 层 | 命令 | 结果 | 备注 |
|----|------|------|------|
| 集成/全量 Python | `pytest tests/` | **693 passed, 1 skipped** | 含 test_mock_acp_support（BL-059 修复后稳定）与 demo loop 黑盒（BL-057/058） |
| strict manifest | 六 profile | **全过** | web 89 / recovery 98 / scheduling 32 / agent 26 / singleagent 9 / iteration027 29 |
| 视觉/浏览器 | Playwright 三视口 | **16 passed, 2 skipped** | chromium-1440/1024/390 |
| 性能专项 | `test_web_performance.py` | **1 passed** | Runs 首屏 p95 < 500ms |

## 失败分类

无失败。无基建缺陷/设计缺陷/局部 bug。

## 阻塞级缺陷判定

无（Agent 判定，依据：全层通过、无失败用例、性能与 manifest 门禁达标）。

## 证据路径

- 全量测试：`693 passed`（本 Report 生成前 72s 全绿）
- strict manifest：六 profile `ok` 输出
- Playwright：`16 passed (4.8s)`
- 性能：`test_web_performance.py 1 passed`
