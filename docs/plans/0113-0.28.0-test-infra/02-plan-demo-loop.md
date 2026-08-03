---
title: BL-057/058 demo loop + SYSTEM_TEST 真实链路黑盒
description: mock backend demo loop（生成 png/pdf + 主动 intervention）+ 端到端黑盒测试补盲区
type: plan
status: pending
created: 2026-08-03T00:00:00Z
---

# Context

0.27.1 复盘确认 SYSTEM_TEST 黑盒盲区：AC-033（二进制预览）与 AC-023（intervention）只用 fixture/mock 集成覆盖，无真实 agent 链路端到端黑盒；parallel 事件串线正是此类盲区漏过的真实缺陷。SYSTEM_TEST 不调付费 Agent，用 mock backend demo loop 补真实链路黑盒。

# Request

1. 造 mock backend（`--mock bash`）demo loop：某阶段用 bash 生成 `chart.png`/`report.pdf`，另一阶段 `intervene()` 请求批准。
2. 配 Playwright/system 测试跑该 loop：验证 WebUI 二进制预览（AC-033）+ intervention 应答（AC-023）端到端。
3. 不付费、可入 CI。

# Constraints

- 不修改 active Spec/AC/Interface、accepted ADR（人类已确认仅 Plan 容器，无权威文档变更）。
- demo loop 用 `--mock bash`（ADR-0014），不调真实付费后端。
- 新增测试归 SYSTEM_TEST 层（Playwright 浏览器黑盒），不重复 DEVELOP 单元测试。

# Checkpoint

- [ ] demo loop 资产就绪（生成 png/pdf + waiting_input 协议可触发）
- [ ] 端到端黑盒测试通过（二进制预览 + intervention 应答）
- [ ] CI 可运行（不付费）
