---
title: 0.25.1 Patch — BL-034~037 Bug Fixes Report
description: Execution report for 0.25.1 patch bug fixes
type: report
status: complete
created: 2026-07-28T03:42:14Z
---

# Report: 0.25.1 Patch Bug Fixes

## BL-034: 远程 run 文件预览失败

### 改动
- `web_storage.py:resolve_working_directory` — 末尾追加 `run_dir / "work"` 兜底候选
- `web.py:preview_run_file` — 错误消息从 "File was not found" 改为 "Working directory for run is not available on this server"

### 验证
- 既有测试全绿，无回归

## BL-035: Events 重复渲染

### 改动
- `runner.py:_call_backend` — `agent_start` 仅在 `infra_attempt == 0` 时写入 events.jsonl
- `web_events.py:project_events` — 新增 `_dedup_events` 函数，对同一 `(call_id, session_id)` 的重复 `agent_session` 事件去重，保留最后一条

### 验证
- `test_events_jsonl_on_resume` 通过（恢复后 agent_start 计数不翻倍）
- 全量测试无回归

## BL-036: 后端显示为 unknown

### 改动
- `manager.py:_make_backend` — 创建实例后设置 `instance.backend_name = backend`（resolved name）
- `runner.py:AgentRunner.__init__` — 新增 `self._display_backend`，从实例属性 fallback，`isinstance` 检查防 MagicMock 污染
- `runner.py` 两处 `agent_start` 事件写入改用 `self._display_backend`

### 设计决策
**不改变 `backend_name`（用于 `input_digest`），保持缓存兼容性。** 修改 `backend_name` 会导致 auto-detect 的 run `input_digest` 从 `backend=None` 变为 `backend="claude"`，破坏既有 run 的恢复能力（cache digest 不匹配 → `ReplayDiverged`）。Display fallback 只影响 `agent_start` 事件的 `backend` 字段。

### 验证
- `test_failure_classification.py` 全绿（MagicMock 不污染）
- `test_events_jsonl_on_resume` 通过（input_digest 不变，cache 兼容）

## BL-037: File changes 文件夹不可折叠

### 改动
- `App.tsx:ChangeTreeDirView` — `useState(true)` toggle，点击切换，`ChevronDown`/`ChevronRight` 图标，`role="button"` + `tabIndex` + 键盘支持
- `styles.css:.change-tree-row.is-dir` — `cursor: pointer`, `user-select: none`, `:hover` 高亮

### 验证
- Vitest 41 passed
- Playwright 13 passed, 2 skipped

## BL-038: Loops 页面混入运行时状态

### 改动
- `App.tsx` — 移除 Loops 侧栏的 `streak ×N` badge 和 `paused` StatusBadge
- `App.tsx` — 移除详情头部的 `failure streak ×N`、`paused` badge、`paused_reason`、Unpause 按钮
- `App.tsx` — 删除 `unpause` handler（不再从 Loops 页面触发）
- `App.test.tsx` — 删除 `shows paused loop badge with streak and unpauses via API` 测试
- `styles.css` — 删除 `.streak-badge`、`.loop-paused`、`.paused-reason` 样式

### 验证
- Vitest 41 passed（减少 1 个测试，因删除的功能不再需要）
- Playwright 13 passed

## BL-039: 切换 Runs 时卡顿

### 改动
- `App.tsx:94` — `useEffect` on `selectedId` 增加 `setDetail(null)` 在 API 调用前

### 验证
- Vitest 41 passed
- 远端实测：切换 run 无卡顿

## BL-040: Backends API 对 missing 后端调用 _make_backend

### 改动
- `web_resources.py:summary()` — `if path:` 条件保护 `_make_backend` 调用

### 验证
- Python 520 passed
- 远端 API 耗时 0.279s → 0.279s（missing 后端的实例化开销极小，实际瓶颈在 `--version` 子进程调用）

## BL-041: 切换页面卡顿 + missing catch

### 改动
- `App.tsx` — 三个 workspace 用 `<div hidden={view !== 'x'}>` 替代条件挂载，state 跨 tab 保留
- `App.tsx:445` — `api.loops()` 补 `.catch((cause) => setError(messageOf(cause)))`
- `styles.css` — 删除 `.workspace-container.hidden` 规则（用原生 `hidden` 属性替代）

### 验证
- Vitest 41 passed（jsdom 尊重 `hidden` 属性，测试中 hidden workspace 的元素不被 `getByRole` 发现）
- Playwright 13 passed
- 远端实测：切换 Runs/Loops/Backends 无卡顿

## 测试总计

| 层 | 结果 |
|----|------|
| Python | 520 passed, 1 skipped |
| Vitest | 41 passed |
| Playwright | 13 passed, 2 skipped |
