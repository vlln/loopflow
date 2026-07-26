---
title: WebUI call/occurrence 显示简化 Report
description: BL-021 完成，web/src/App.tsx 改 4 处显示字符串（call_id 主显/session 降 tooltip、×N、第 N 次执行、N 个事件），web 测试 41 passed，断言同步更新 4 条
type: report
status: complete
created: 2026-07-26T09:10:00Z
---

# Summary

简化 WebUI 中 call/occurrence 显示措辞。call-list 主显 `call_id`（如 `call-a`），`session` 降为元素 `title` tooltip（hover 显示完整 session）；PhaseNode 节点显示 `×N`（替代 `N occurrence(s)`）；phase-detail-bar 显示 `第 N 次执行`（替代 `Occurrence N`）；EventTimeline 标题显示 `N 个事件`（替代 `N events`）。消除 session 含 call_id 又单独显示的重复，并区分 occurrence/events 措辞。web 测试 41 passed，因契约变更失效的 4 条断言已同步为新契约。

# Changes

| BL | 文件 | 改动 | commit |
|----|------|------|--------|
| BL-021 | `web/src/App.tsx` | 4 处显示字符串：call-list `<strong title={call.session ?? undefined}>{call.call_id}</strong>`；PhaseNode `×${data.count}`；phase-detail-bar `第 {selectedOccurrence.occurrence} 次执行`；EventTimeline `${events.length} 个事件` | （见 commit） |
| BL-021 | `web/src/App.test.tsx` | 同步 4 条因契约失效的断言：`wf-review-a`→`call-a`、`wf-review-b`→`call-b`、`/wf-plan/`→`/call-plan/`、`1 occurrence`→`×1` | （见 commit） |

# 改动细节

## call-list 主显 call_id，session 降 tooltip

```tsx
<strong title={call.session ?? undefined}>{call.call_id}</strong>
```

- 主显 `call.call_id`（逻辑编号，如 `call-a`）
- `session` 存在时进 `title`，hover 显示完整 session（如 `wf-review-a`）
- `session` 缺失时 `title` 为 `undefined`，不渲染 title 属性，无空白 tooltip
- 消除 session 含 call_id 又单独显示的冗余

## PhaseNode ×N

```tsx
<small>{data.declared ? 'pending' : `×${data.count}`}</small>
```

- 已执行节点显示 `×N`（如 `×2`），简短表示执行次数
- declared 未执行仍显示 `pending`

## phase-detail-bar 第 N 次执行

```tsx
<span className="section-meta">第 {selectedOccurrence.occurrence} 次执行</span>
```

## EventTimeline N 个事件

```tsx
<SectionHeader title={title} meta={`${events.length} 个事件`} />
```

## 测试断言同步

call-list 主显改为 call_id 后，原断言按 session 文本（`wf-review-a`/`wf-review-b`/`wf-plan`）定位元素的测试失效。同步为新契约（按 call_id 文本定位）：

| 行 | 旧断言 | 新断言 |
|----|--------|--------|
| App.test.tsx:123 | `getAllByText('wf-review-a')` | `getAllByText('call-a')` |
| App.test.tsx:132 | `getByText('wf-review-b')` | `getByText('call-b')` |
| App.test.tsx:169 | `getByRole('button', { name: /wf-plan/ })` | `getByRole('button', { name: /call-plan/ })` |
| App.test.tsx:573 | `toContain('1 occurrence')` | `toContain('×1')` |

仅改断言期望值，未改测试逻辑/场景。

# Verification Results

| 验证 | 结果 |
|------|------|
| `cd web && npm test -- --run` | 41 passed（3 files） |
| App.tsx 改动范围 | 仅 4 处显示字符串，无其他重构 |
| 测试改动范围 | 仅 4 条契约失效断言，无逻辑改动 |

# Notes

- **无 snapshot 需更新**：web 测试无 snapshot 断言，失效的是 4 条文本/role 断言，已同步为新契约。
- **不合并分支**：由用户合并，本容器只交付代码 + 文档。
- **未碰 loopflow 后端与 deep-research**：本分支 diff 只含 `web/src/App.tsx` + `web/src/App.test.tsx`。
