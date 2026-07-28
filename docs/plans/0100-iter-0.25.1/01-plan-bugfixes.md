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
- Vitest: 42 passed
- Playwright: 13 passed, 2 skipped
