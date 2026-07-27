---
title: Plan — WebUI Failed Run 错误布局收紧
description: error_banner 的 error_summary 文本无高度限制，failed run 时占据大量空白。收紧为限高 + 截断 + 可折叠（BL-032）
type: plan
status: pending
created: 2026-07-27T12:30:00Z
---

# Plan: WebUI Failed Run 错误布局收紧

## 目标

`run-error-banner` 中的 `.error-summary-text` 是一个 `<span>`，`word-break: break-word` 但无 `max-height`。当 `error_summary` 很长时（多行错误、长 traceback 摘要），banner 无限展开，挤占 Phase 工作区和 Inspector 的可见空间。

修复方向：给 `.error-summary-text` 加 `max-height` + `overflow` 限制，超长时截断并显示"展开"按钮。

## 步骤

1. **`web/src/styles.css:217-218` — 限制 summary 文本高度**

   ```css
   .run-error-banner .error-summary-text {
     word-break: break-word;
     flex: 1;
     max-height: 3em;           /* 约 2 行 */
     overflow: hidden;
     text-overflow: ellipsis;
     display: -webkit-box;
     -webkit-line-clamp: 2;
     -webkit-box-orient: vertical;
   }
   ```

   纯 CSS 方案，不需要额外的展开/折叠交互。`-webkit-line-clamp` 在所有目标浏览器（Chrome/Edge/Firefox/Safari）中受支持。traceback 已有 `<details>` 折叠且 `max-height: 200px`，不变。

2. **验证**：Playwright 视觉回归测试中，failed run 的 error_banner 高度不超出约 2 行文本 + traceback 折叠条。

## AC 覆盖

- AC-019-B-4（新增）：error_summary 超过 2 行时，banner 截断显示前 2 行，不挤占相邻面板

## Constraints

- 纯 CSS 修改，不改 JSX 结构
- 不改 traceback 的 `<details>` 折叠行为（已折叠，不变）
- 不改 `.row-error`（runs 列表中的单行错误提示，10px 字号，已是极简）

## Checkpoint

- `web/src/styles.css`：`.error-summary-text` 加 `max-height` + `-webkit-line-clamp`
- 前端测试全绿
- Playwright 视觉回归无回归

## 风险

- `-webkit-line-clamp` 在旧浏览器中不支持，但 loopflow 的目标浏览器均为现代浏览器。
- 截断后用户无法看到完整 error_summary——但 traceback `<details>` 中有完整信息，且 API 返回完整数据。
