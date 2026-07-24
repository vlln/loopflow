---
title: SSE Multi-Topic Transport Implementation Report
description: ADR-0041 SSE 多 topic transport 实现完成报告
type: report
status: done
created: 2026-07-23T16:00:00Z
---

# Summary

ADR-0041 SSE 多 topic transport 实现完成。SSE 从 events.jsonl 管道重构为多路复用传输层，支持 run_event 和 file_changes topic 各自独立游标。

# Changes

## Python 后端

- `src/loopflow/infrastructure/web_events.py`：新增 `replay_file_changes(path, last_seq)` 函数，读取 file_changes.jsonl 并按 seq 过滤重放。文件不存在时返回空（静默空 topic）。
- `src/loopflow/application/web.py`：`WebApplication` 新增 `replay_file_changes(run_id, last_seq)` 方法，封装 run_dir 查找和 cursor_out_of_range 错误。
- `src/loopflow/presentation/web/server.py`：
  - `_events()` handler 重构为多 topic 多源合并
  - 接受 `last_event_id` + `last_file_changes_id` 双游标
  - run_event topic：cursor 超出返回 410 JSON（保持 AC-016-E-1 兼容）
  - file_changes topic：cursor 超出发送 `event: stream_error`（带 topic 字段），不影响 run_event
  - `stream_end` 等待所有 topic terminal
  - 新增 `_send_topic_error(topic, exc)` helper
  - `getattr(self.app, "replay_file_changes", None)` 兼容旧 mock

## 前端

- `web/src/types.ts`：新增 `FileChange` 和 `FileChangeRecord` 类型
- `web/src/api.ts`：
  - `connectRunEvents` 签名改为 `(runId, cursors, handlers)`
  - `cursors: { lastEventId, lastFileChangesId }` per-topic 游标
  - `handlers: { onEvent, onFileChanges?, onState }` 多 topic handler
  - EventSource URL 包含 `last_file_changes_id` 参数
  - 监听 `event: file_changes` 分发到 `onFileChanges`
- `web/src/App.tsx`：更新 `connectRunEvents` 调用为新签名

## 测试

- `tests/web_support/factories.py`：新增 `append_file_changes()` factory 方法
- `tests/integration/test_web_api.py`：新增 4 个多 topic SSE 测试
  - `test_sse_multi_topic_pushes_run_event_and_file_changes`（AC-016-N-3）
  - `test_sse_multi_topic_per_topic_cursor_reconnect`（AC-016-N-4）
  - `test_sse_file_changes_cursor_out_of_range_does_not_affect_run_event`（AC-016-E-3）
  - `test_sse_no_file_changes_jsonl_silently_empty`（legacy 兼容）

# Verification

- Python: 360 passed, 1 skipped, 81% coverage
- Frontend: 15 passed, typecheck clean, 99.48% stmt coverage
- AC-016-N-3/N-4/E-3 覆盖
- 现有 SSE 测试全部不回归（AC-016-N-1/N-2/B-1/B-2/E-1/E-2/F-1/F-2）

# Decisions

- run_event cursor 超出仍返回 410 JSON（fatal），file_changes cursor 超出发送 SSE stream_error（non-fatal）。这保持了 AC-016-E-1 的现有契约，同时满足 AC-016-E-3 的"不影响其他 topic"要求。
- file_changes.jsonl 不存在时 topic 静默空，不报错——legacy Run 兼容。
- `getattr` 兼容旧测试 mock（FailingApplication 无 replay_file_changes 方法）。
