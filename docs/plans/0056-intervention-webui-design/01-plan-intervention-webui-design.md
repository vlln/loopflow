---
title: Intervention WebUI Design Plan
description: 设计用户回答问题介入链路的 WebUI 信息架构、状态表达和交互规则
type: plan
status: done
created: 2026-07-23T15:00:00Z
---

# Goal

补齐 Intervention WebUI 的产品设计，使用户在 Run 等待输入或取消后仍有 pending request 时，能够清楚地区分“回答问题继续同一 Run”和“恢复/重跑 execution attempt”的不同语义。

# Process Correction

0054/0055 已产生代码和测试提交，但它们没有严格按 devloop 分阶段推进。本设计容器不继续扩大实现，而是把已暴露出的 WebUI 产品问题拉回 DESIGN 审核：

- 0054：状态契约字段对齐，实际含产品代码修正。
- 0055：Intervention 控件和测试对齐，实际含 WebUI 行为修改。
- 0056：补齐设计，作为后续是否修正 0055 实现的依据。

# Design Proposal

## 1. Intervention 是 Run Detail 的主焦点，而不是普通补充卡片

当 Run 满足以下任一条件时，Run detail 顶部必须把 Intervention 区域提升为主操作区：

- `status=waiting_input`
- `allowed_actions` 包含 `respond`

主操作区展示顺序：

1. Run status 与 request key。
2. 人类需要回答的 prompt。
3. request 来源：workflow replay 或 agent session continuation。
4. 匹配 schema 的输入控件。
5. 提交状态、错误和已回答结果。

Phase graph、Calls 和事件仍可见，但视觉层级低于 pending intervention。

## 2. `respond` 与 `recover` 必须分开解释和排序

`respond` 是“回答当前 pending request，并恢复同一 Run”。`recover_retry/recover_continue` 是“不回答该 request，重新执行到恢复边界”。两者不应在同一视觉层级混杂。

规则：

- `waiting_input`: 主按钮是回答问题；`stop` 是次要危险动作。
- `cancelled + respond`: 主按钮仍是回答问题；`recover_retry` 是次要动作；`rerun` 是更低层级动作。
- `cancelled + respond + recover_continue`: Continue 只表示恢复取消点的 backend session，不表示提交回答；文案必须包含 `session`。
- `rerun`: 始终表达为创建新 Run，不和 respond/recover 放在同一组。

## 3. 首版 schema UI 只支持顶层类型

首版不做完整 JSON Schema form renderer，只识别顶层 `type`：

| schema type | 控件 | 提交值 |
|-------------|------|--------|
| `boolean` | Approve / Reject 或 Yes / No 双按钮 | `true` / `false` |
| `string` | 单行文本输入 | string |
| `number` | number input | number |
| `object` | JSON textarea | parsed object |
| `array` | JSON textarea | parsed array |
| `null` schema | JSON textarea | parsed any JSON value |
| unknown/unsupported | JSON textarea | parsed JSON，后端校验 |

前端只做基本 parse/type guard，最终以后端 schema 校验为准。

## 4. pending、answered、error 三类状态都要可见

Intervention panel 不只展示 pending request：

- pending：展示输入控件。
- answered：展示 response 摘要、responded_at 和只读状态，不显示再次提交控件。
- submit error：错误贴在 panel 内，同时保留 toast；输入内容不丢失。
- recovery error：显示“回答已保存，但恢复失败”的区别，避免误以为回答未提交。

## 5. 多 request 首版只处理一个 pending，但列表要可解释

当前后端允许列出多个 request。首版 UI 选择最早 pending request 作为主操作区；其他 request 在折叠历史中显示。若没有 pending，则展示最近 answered/closed 的只读摘要。

# Review Questions

审核结论：

1. `cancelled + pending request` 时，回答问题作为最高优先级主操作，`recover_retry` 降为次要动作。
2. 首版接受只支持顶层 schema type，不做完整 JSON Schema form renderer。
3. 回答成功但自动恢复失败时，UI 必须区分“response 已保存”和“Run 恢复失败”。
4. 多个 request 首版按“最早 pending 为主、其他只读折叠”处理。

# Backend Contract Gap

第 3 点需要后端契约支持。当前实现顺序是：

1. `POST /runs/{run_id}/interventions/{request_id}/response` 先原子持久化 answer；
2. 再自动启动 recover；
3. 如果 recover 返回 `replay_diverged`、`continue_not_supported` 或 `invalid_run_transition`，HTTP 只返回普通错误。

这意味着前端不能仅凭本次 error response 判断 answer 是否已保存，只能再查询 `GET /runs/{run_id}/interventions` 推断。后续 TEST_INFRA 需要先冻结一个明确契约，例如在错误响应 `details` 中携带：

```json
{
  "response_persisted": true,
  "request_id": "approve-1",
  "run_id": "abc",
  "recovery_started": false
}
```

或引入等价的 read model 字段。该契约必须区分：

- schema 校验失败：answer 未保存；
- duplicate answer：answer 原本已存在；
- answer 已保存但自动恢复失败；
- answer 已保存且恢复 worker 已启动。

# Acceptance For Next Stage

设计已审核通过。下一阶段应先进入 TEST_INFRA：

1. 补 AC，覆盖 intervention panel 视觉层级、cancelled + respond 优先级、answered/history/error 状态。
2. 补 Web API error details 契约，覆盖 answer persisted 但 recovery failed 的区分。
3. 补 WebUI contract/DOM 测试计划。
4. 再进入 DEVELOP 调整现有 0055 实现。

# Exit

本 Plan 已经用户审核通过，可进入 TEST_INFRA。
