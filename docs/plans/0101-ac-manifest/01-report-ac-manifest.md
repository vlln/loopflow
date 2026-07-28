---
title: AC Manifest 增量 Report — AC-031/032 覆盖与 singleagent profile
description: recovery manifest 补 AC-031、新增 singleagent profile 覆盖 AC-032、修复 agent profile 既有漂移，mr-gate 全绿
type: report
status: complete
created: 2026-07-28T11:20:00Z
---

# Report: AC Manifest 增量

## 结果

| Checkpoint | 结果 |
|-----------|------|
| recovery profile `--allow-planned` 通过（含 AC-031 ×11） | PASS（84 scenarios） |
| singleagent profile `--allow-planned` 通过（AC-032 ×7） | PASS（9 scenarios） |
| web/scheduling/agent profile 不回归 | PASS（86/32/26 scenarios） |
| mr-gate 全门禁 | PASS（524 Python passed + 1 skipped；5 个 manifest profile 全 ok；41 Vitest；13 Playwright；wheel-smoke ok） |

## 增量检查发现的计划外问题

1. **agent profile 既有漂移**（非本轮引入）：AC-001 的 BL-018 追加场景（N-4/B-3/B-4/E-1/F-2）从未录入 `tests/agent_support/manifest.py` TARGETS，mr-gate 在 develop 上实际为红。处置：补 TARGETS ×5；其中 4 个纯 parse_agent 场景补了真实单测（`tests/unit/test_agent.py::TestParseAgentFrontmatter`，39 passed）并映射 TEST_NODES；AC-001-F-2（pi argv `---` 进程断言）无对应测试设施，留 planned:: 并录 BL-048。
2. **`check-ac-manifest.py --write` 无早退**：写入后仍以严格模式校验，新生成的 planned:: 节点必然报错（exit≠0 但文件已写入），首次使用易误判。录 BL-049。

## AC 验收标注

本容器为测试基建增量，不直接实现业务 AC；AC-031/032 的 planned:: 节点由 0102（DEVELOP）回填真实测试节点。

## 证据

- mr-gate 日志：`/tmp/mr-gate-0101.log`（本地运行，exit=0）
- 关键 commit：`40fb5f7`（test）、`3f4f98b`（docs）
