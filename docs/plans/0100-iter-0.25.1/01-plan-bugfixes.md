---
title: 0.25.1 Patch — BL-034~037 Bug Fixes
description: Fix remote run file preview, event duplication, backend display name, and collapsible file changes folders
type: plan
status: done
created: 2026-07-28T03:42:14Z
---

# Plan: 0.25.1 Patch Bug Fixes

## 背景

v0.25.0 发布后用户报告 4 个 bug，需做 patch 升级。

## BL-034: 远程 run 文件预览失败

### 根因

`RunRepository.resolve_working_directory()` (`web_storage.py:448-469`) 仅检查 `run.json["working_directory"]` 和 `runs_index.jsonl` 中的路径。当工作目录在服务器上不存在时（远程 run 路径不可达、临时目录已清理），返回 `None`，导致 `preview_run_file()` 抛 `file_not_found`，前端显示 "File no longer exists"。

### 方案

在 `resolve_working_directory` 的候选列表末尾追加 `run_dir / "work"` 作为兜底（ADR-0054 默认隔离目录，与 run 数据同位）。改进错误消息区分"工作目录不可访问"和"文件不存在"。

## BL-035: Events 重复渲染

### 根因

1. `_call_backend()` (`runner.py:614-637`) 的 infra-retry 循环在每次迭代（包括重试）都写 `agent_start` 到 `events.jsonl`。重试时已有 `agent_retry` 事件记录重试，`agent_start` 是多余的。
2. `session_handler` (`manager.py:197-200`) 在后端每次创建/重建会话时被回调，同一 `session_id` 可能被写入多次。`project_events` (`web_events.py:117`) 返回所有原始事件不做去重。

### 方案

- `_call_backend`: 仅在 `infra_attempt == 0` 时写 `agent_start`
- `project_events`: 对同一 `(call_id, session_id)` 的重复 `agent_session` 事件去重，保留最后一条

## BL-036: Claude Code 后端显示为 unknown

### 根因

`runtime.py:63-104`: 当 `backend` 为 `None`（auto-detect），`_make_backend` 内部解析到 `"claude"`，但局部变量 `backend` 仍为 `None`。`AgentRunner(backend_name=None)` → `agent_start` 事件 `backend: None` → 前端显示 "backend unknown"。

### 方案

`_make_backend` 在实例上设置 `backend_name` 属性（`instance.backend_name = backend`）。`AgentRunner.__init__` 中用该属性做 display fallback（`self._display_backend`），仅在写 `agent_start` 事件时使用。**不改变 `backend_name`（用于 `input_digest`），保持缓存兼容性。**

## BL-037: File changes 文件夹不可折叠

### 根因

`ChangeTreeDirView` (`App.tsx:317-318`) 无 `onClick`、无 state、子节点无条件渲染。

### 方案

`ChangeTreeDirView` 加 `useState` toggle + chevron 图标，点击切换，默认展开。CSS 加 `cursor: pointer`。

## 验证

- Python: 520 passed, 1 skipped
- Vitest: 41 passed
- Playwright: 13 passed, 2 skipped

## BL-038: Loops 页面混入运行时状态

### 根因
Loops 定义页（侧栏列表 + 详情头部）渲染了 `paused`、`consecutive_failures`、`paused_reason`、Unpause 按钮等 run 级状态。API `/api/v1/loops` 也混入运行时字段。

### 方案
前端移除 Loops 页面的所有运行时状态渲染（streak badge、paused badge、paused_reason、Unpause 按钮、unpause handler）。CSS 清理 `.streak-badge`、`.loop-paused`、`.paused-reason`。

## BL-039: 切换 Runs 时卡顿

### 根因
`useEffect` on `selectedId` 未立即清空旧 `detail`，React 用旧数据重渲染（含 AgentGraph key 变化导致重挂载旧 props）。

### 方案
`selectedId` 变化时立即 `setDetail(null)`，API 响应到达后再设新值。

## BL-040: Backends API 对 missing 后端调用 _make_backend

### 根因
`BackendRepository.summary()` 对全部 9 个后端调用 `_make_backend(name)` 创建实例，只为读 capabilities。7 个 missing 后端的实例化是纯浪费。

### 方案
`if path:` 条件保护 `_make_backend` 调用，missing 后端用默认 capabilities。

## BL-041: 切换页面卡顿 + missing catch

### 根因
1. tab 切换用条件挂载/卸载（`{view === 'x' && <X />}`），组件 state 丢失，每次切换重新发 API 请求。
2. `LoopsWorkspace` 的 `api.loops()` 调用缺少 `.catch()`，500 错误时产生 unhandled promise rejection。

### 方案
1. 改用 `hidden` HTML 属性隐藏非活跃 workspace，三个 workspace 始终挂载，state 跨 tab 保留。
2. 补 `.catch((cause) => setError(messageOf(cause)))` 到 `api.loops()` 调用。
