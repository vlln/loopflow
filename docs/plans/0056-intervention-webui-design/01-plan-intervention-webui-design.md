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
- 回答提交成功后，后续 worker/agent 失败按普通 Run execution failure 展示，不作为 Intervention 特殊状态建模。

## 5. 多 request 首版只处理一个 pending，但列表要可解释

当前后端允许列出多个 request。首版 UI 选择最早 pending request 作为主操作区；其他 request 在折叠历史中显示。若没有 pending，则展示最近 answered/closed 的只读摘要。

# Review Questions

审核结论：

1. `cancelled + pending request` 时，回答问题作为最高优先级主操作，`recover_retry` 降为次要动作。
2. 首版接受只支持顶层 schema type，不做完整 JSON Schema form renderer。
3. 不单独建模“回答成功但自动恢复失败”；回答持久化成功后，后续失败归入普通 Run execution failure。
4. 多个 request 首版按“最早 pending 为主、其他只读折叠”处理。

# Framework Business Boundary

提交回答的 4 个错误边界属于框架层 application command 业务逻辑，是 respond 命令必须保证的业务不变量，由后端保证，不由 WebUI 自行推断：

| 边界 | 框架层保证 | UI 行为 |
|------|----------|---------|
| schema 校验失败 | 返回 `422 validation_failed`；response 不落盘；不启动恢复 worker | 保持 pending 输入状态，显示错误 |
| request 不存在 | 返回 `404 intervention_not_found`；不修改 Run | 显示错误并刷新 Run/request |
| request 已 answered | 返回 `409 intervention_already_answered`；不覆盖 response；不重复启动恢复 | 切到 answered/history 只读展示 |
| Run 当前不允许 respond | 返回 `409 invalid_run_transition`；不修改 request | 显示状态冲突并刷新 Run |

`POST /runs/{run_id}/interventions/{request_id}/response` 的职责是校验并持久化 response，然后让同一 Run 进入恢复执行流程。若 response 已经持久化且恢复 worker 后续失败，该失败属于普通 Run execution failure，由 Run status、events、call status 和 existing recover actions 表达；不新增 `response_persisted`、`recovery_started`、`respond_status` 或独立 lifecycle state。

因此下一阶段需要先用 AC/interface/contract tests 固化上述 4 个框架层业务边界，再补 UI 状态展示；不为低概率恢复失败设计单独的 intervention error 协议。

# Acceptance For Next Stage

设计已审核通过。下一阶段应先进入 TEST_INFRA：

1. 补 AC，覆盖 intervention panel 视觉层级、cancelled + respond 优先级、answered/history/error 状态。
2. 补 AC/contract，明确 4 个 respond 提交前错误边界由框架保证。
3. 补 WebUI contract/DOM 测试计划。
4. 再进入 DEVELOP 调整现有 0055 实现。

# Exit

本 Plan 已经用户审核通过，可进入 TEST_INFRA。
