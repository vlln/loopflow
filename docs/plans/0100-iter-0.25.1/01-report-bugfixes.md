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
- Vitest 42 passed
- Playwright 13 passed, 2 skipped

## 测试总计

| 层 | 结果 |
|----|------|
| Python | 520 passed, 1 skipped |
| Vitest | 42 passed |
| Playwright | 13 passed, 2 skipped |
