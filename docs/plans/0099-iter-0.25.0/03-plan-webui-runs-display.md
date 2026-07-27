---
title: Plan — Runs 左栏显示项目目录名
description: Runs 左栏的 <code> 当前显示 run_id（UUID），改为显示 working_directory 的目录名，让用户辨识 run 对应哪个项目（BL-033）
type: plan
status: pending
created: 2026-07-27T12:30:00Z
---

# Plan: Runs 左栏显示项目目录名

## 目标

Runs 左栏每个 run item 的次要标识行是 `<code>{run.run_id}</code>`——一串 UUID（9px 字号、ellipsis 截断），用户无法辨识哪个 run 对应哪个项目。`working_directory` 字段已在 `RunSummary` 中且后端始终填充，但仅用作 tooltip。

修复方向：将 `<code>` 的显示文本从 `run.run_id` 改为 `working_directory` 的 basename。`run_id` 保留为 React `key` 和 `selectRun` 参数（不变）。

## 步骤

1. **`web/src/App.tsx:148` — 替换 `<code>` 显示内容**

   当前：
   ```tsx
   <code title={run.working_directory}>{run.run_id}</code>
   ```

   改为：
   ```tsx
   <code title={run.working_directory}>
     {run.working_directory ? run.working_directory.split('/').filter(Boolean).pop() ?? run.run_id : run.run_id}
   </code>
   ```

   - `working_directory` 存在时取路径最后一段（如 `/tmp/lf_xxx/work` → `work`，`/home/user/bio-reproducer` → `bio-reproducer`）
   - `working_directory` 为空/null 时 fallback 到 `run_id`
   - `title` 属性保留完整路径（hover 看全路径）

2. **验证**：Playwright 测试中 runs 列表的 `<code>` 元素显示目录名而非 UUID。

## AC 覆盖

- AC-014-B-6（新增）：左栏 run item 次要标识显示 working_directory 的 basename 而非 run_id

## Constraints

- 纯前端 JSX 修改，不改 types.ts（`working_directory` 已在 `RunSummary` 中）
- 不改后端（`working_directory` 已在 `read_summary()` 返回）
- `run_id` 仍作为 React `key` 和 `selectRun(run.run_id)` 参数
- 不改 `<strong>` 主标识（loop name）

## Checkpoint

- `web/src/App.tsx`：runs 列表 `<code>` 显示 `working_directory` basename
- 前端测试全绿

## 风险

- `working_directory` 的 basename 可能与 loop name 相同（如 loop `hello` + working_directory `/tmp/hello/work` → basename `work`），但 `<strong>` 显示 loop name + `<code>` 显示目录名，组合后可辨识。
- `working_directory` 路径格式在不同 OS 下不同（Unix `/` vs Windows `\`）。当前 loopflow 仅支持 Unix，用 `split('/')` 即可。若未来支持 Windows 需改用 `Path` API。
