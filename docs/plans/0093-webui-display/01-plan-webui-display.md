---
title: WebUI call/occurrence 显示简化 Plan
description: BL-021 在 web/src/App.tsx 改 4 处显示：call-list 主显 call_id（session 降 title tooltip）、PhaseNode 显示 ×N、phase-detail-bar 显示"第 N 次执行"、EventTimeline 显示"N 个事件"
type: plan
status: done
created: 2026-07-26T09:07:00Z
---

# Goal

简化 WebUI 中 call/occurrence 的显示措辞，消除 `call_id` 重复（session 含 call_id 又单独显示）+ occurrence/events 措辞区分。代码已执行并验证，本 Plan 记录已执行计划。

# Constraints

- 只改 `web/src/App.tsx` 的这 4 处显示字符串，不重构其他部分
- 不改 loopflow 后端代码、不改 deep-research
- 测试必须通过：因契约变更导致断言失效的测试（断言旧显示字符串）需同步更新为新契约，不改变测试逻辑
- session 缺失时不渲染 title（`call.session ?? undefined`），不显示空白 tooltip
- 不合并分支（由用户合并）

# Steps（已执行）

1. 建 `docs/plans/0093-webui-display/`（README + 本 Plan）
2. 分支 `feat/0093-webui-display` 从 develop
3. `web/src/App.tsx` 四处 Edit：
   - call-list：`<strong title={call.session ?? undefined}>{call.call_id}</strong>`
   - PhaseNode：`<small>{data.declared ? 'pending' : `×${data.count}`}</small>`
   - phase-detail-bar：`<span className="section-meta">第 {selectedOccurrence.occurrence} 次执行</span>`
   - EventTimeline：`<SectionHeader title={title} meta={`${events.length} 个事件`} />`
4. 同步更新 `web/src/App.test.tsx` 因契约变更失效的 4 条断言：
   - `getAllByText('wf-review-a')` → `getAllByText('call-a')`（主显改为 call_id）
   - `getByText('wf-review-b')` → `getByText('call-b')`
   - `getByRole('button', { name: /wf-plan/ })` → `getByRole('button', { name: /call-plan/ })`
   - `toContain('1 occurrence')` → `toContain('×1')`（PhaseNode 新格式）
5. 验证：`cd web && npm test -- --run`
6. Report + README done
7. commit（代码先于文档，分两次）

# Acceptance

- `npm test -- --run` 全绿（41 passed）
- call-list 主显 `call_id`，session 进 `title` 属性（hover 显示）
- session 缺失时不渲染 title（无空白 tooltip）
- PhaseNode 显示 `×N`
- phase-detail-bar 显示 `第 N 次执行`
- EventTimeline 显示 `N 个事件`
- `git diff develop..feat/0093-webui-display --stat` 只含 `web/src/App.tsx` + `web/src/App.test.tsx`

# Checkpoint

- web 测试 41 passed（契约变更后断言已同步，无回归）
- App.tsx 仅 4 处字符串改动，无其他重构
- 测试断言改动仅限契约失效的 4 条，未改测试逻辑

# Exit

全部 Acceptance 通过，写 Report，由用户合回 develop（--no-ff），不合并分支。
