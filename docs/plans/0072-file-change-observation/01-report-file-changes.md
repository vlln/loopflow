---
title: File Change Observation Implementation Report
description: ADR-0039 文件变化观察层实现完成报告
type: report
status: done
created: 2026-07-23T18:00:00Z
---

# Summary

ADR-0039 文件变化观察层实现完成。phase() 调用时对 pwd 递归扫描快照 diff，写入 file_changes.jsonl（含 seq），通过 SSE file_changes topic 推送，WebUI Phase 详情下方展示文件变化列表。

# Changes

## Python 后端

- `src/loopflow/infrastructure/file_observation.py`（新文件）：
  - `FileObservationConfig.from_meta()` 从 loop frontmatter 解析 `file_observation.enabled` / `file_observation.exclude`
  - `FileChangeObserver` 类：`observe(phase, phase_id)` 扫描 working_dir，diff 前后快照，追加 record 到 file_changes.jsonl
  - 默认排除 .git、__pycache__、*.pyc、.DS_Store、node_modules、.venv
  - 自定义 exclude 使用 fnmatch 模式匹配
  - seq 严格递增，changes 含 path/action(created/modified/deleted)/size/prev_size
  - 无变化时返回 None（不写入空 record）
  - enabled=false 时不创建 file_changes.jsonl
- `src/loopflow/infrastructure/context.py`：RunContext 新增 `file_observer` 属性
- `src/loopflow/presentation/events.py`：`_emit_phase()` 在写入 phase event 后调用 `file_observer.observe()`
  - 异常静默吞掉（文件观察失败不影响工作流执行）
- `src/loopflow/application/execution.py`：`execute_workflow()` 从 loop meta 初始化 FileChangeObserver
- `src/loopflow/application/web.py`：`WebApplication.list_file_changes()` REST 查询读模型
- `src/loopflow/presentation/web/server.py`：新增 `GET /api/v1/runs/{id}/file-changes` 路由

## 前端

- `web/src/api.ts`：`api.fileChanges(id)` REST 查询
- `web/src/App.tsx`：`FileChangesList` 组件，Phase 详情下方显示文件变化列表
  - 按 phase_id 过滤记录
  - 显示 action 标签（created/modified/deleted 颜色区分）
  - 显示 path 和 size 变化
- `web/src/styles.css`：file-changes-list / file-change-item 样式
- `web/src/App.test.tsx`：mock file-changes 端点

## 测试

- `tests/unit/test_file_observation.py`（新文件）：17 个单元测试
  - FileObservationConfig：enabled/disabled/exclude/invalid 回退
  - FileChangeObserver：first observe (created)、modified、deleted、no changes、disabled、exclude、seq 递增、jsonl 追加、空目录、嵌套目录
- `tests/integration/test_web_api.py`：3 个 REST 端点测试
  - `test_file_changes_rest_endpoint_returns_records`
  - `test_file_changes_rest_endpoint_empty_for_no_file`
  - `test_file_changes_rest_404_for_nonexistent_run`
- `tests/file_changes_support/manifest.py`：AC-024 planned 节点替换为真实测试引用
- `tests/infrastructure/test_file_changes_manifest.py`：strict 模式验证无 planned 节点

# Verification

- Python: 385 passed, 1 skipped
- Frontend: 15 passed, typecheck clean, 99.26% stmt coverage
- AC-024 manifest: 0 planned nodes, strict mode passes
- AC-024 所有场景（N/B/E/F/U）覆盖

# Decisions

- 文件观察失败静默吞掉（try/except pass），不影响工作流执行——ADR-0039 要求观察层是 non-invasive 的。
- 默认排除 .git/__pycache__/.venv 等常见非业务目录，用户可通过 meta.file_observation.exclude 追加。
- file_changes.jsonl 不存在时 REST 返回空 list（不是 404），SSE topic 静默空——legacy Run 兼容。
- AC-024 manifest 的 planned 节点全部替换为真实测试引用，strict 模式通过。
