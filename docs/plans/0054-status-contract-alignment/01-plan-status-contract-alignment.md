---
title: Status Contract Alignment Plan
description: 对齐后端状态相关设计与产品接口、文档和 contract fixture
type: plan
status: done
created: 2026-07-23T14:00:00Z
---

# Goal

消除上一轮状态设计后的契约漂移，使活跃文档、产品返回、前端类型和测试契约对 InterventionSummary 与取消恢复状态语义的表达一致。

# Findings

1. Interface/Spec 与 recovery contract fixture 使用 `answered_at`，但产品和 WebUI 使用 `responded_at`。
2. Interface 和 recovery contract fixture 要求 `can_continue_session`，但产品 InterventionSummary 未返回该字段。
3. AC/ADR 索引仍使用“永久停止”描述，和 `cancelled` 不表示 abandon Run 的语义冲突。

# Decision

1. 采用产品现有字段名 `responded_at`，同步更新活跃 Spec、Interface 和 recovery contract fixture。
2. 保留 Interface 已承诺的 `can_continue_session`，在 InterventionSummary 中补齐派生字段。
3. 将活跃索引 wording 改为“可靠取消”。

# Acceptance

1. `GET /runs/{run_id}/interventions` 返回的 InterventionSummary 包含 `can_continue_session` 和 `responded_at`。
2. Spec、Interface、前端类型、recovery contract fixture 对 InterventionSummary 字段命名一致。
3. 活跃索引不再把 stop/cancel 描述为“永久停止”。
4. recovery manifest 与相关测试通过。

# Steps

1. 更新 InterventionSummary 实现和测试断言。
2. 更新 Spec、Interface、AC/ADR README wording。
3. 更新 recovery support contract/fixture。
4. 运行 manifest、contract、应用层和 Web 测试。
5. 写 Report、标记 Plan done 并提交。

# Exit

全部验收通过后，保持当前系统阶段为 DESIGN，等待下一轮正式功能设计。
