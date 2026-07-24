---
title: SSE Multi-Topic Transport Implementation Plan
description: 实现 SSE 多 topic transport，支持 run_event 和 file_changes 独立游标
type: plan
status: pending
created: 2026-07-23T15:00:00Z
---

# Goal

实现 ADR-0041 的 SSE 多 topic transport，将 SSE 从 events.jsonl 管道重构为多路复用传输层。替换 AC-016 多 topic 场景的 planned 节点。

# Acceptance

1. SSE 连接支持 `?last_event_id=N&last_file_changes_id=M` 双游标参数。
2. 同一连接推送 `event: run_event`（id=event_id）和 `event: file_changes`（id=seq）。
3. per-topic 独立 replay：run_event 从 events.jsonl，file_changes 从 file_changes.jsonl。
4. stream_end 在所有 topic terminal 时才发送。
5. 单 topic 游标超出返回 stream_error（带 topic 字段），不影响其他 topic。
6. file_changes.jsonl 无数据时 file_changes topic 静默（不报错），run_event 正常推送。
7. 前端 connectRunEvents 支持 per-topic 游标和多 event handler。
8. AC-016-N-3/N-4/B-3/E-3/F-3 manifest planned 节点被真实测试替换。

# Steps

1. application service 增加 replay_file_changes(run_id, last_seq) 查询。
2. file_changes.jsonl reader 增加 seq 字段解析和 max_seq 查询。
3. server.py _events() handler 重构为多 topic 多源合并。
4. SSE 事件按 topic 分发，id 字段为 per-topic 游标。
5. stream_end 等待所有 topic terminal。
6. 游标超出返回 per-topic stream_error。
7. 前端 api.ts connectRunEvents 扩展多 topic。
8. 前端 types.ts 增加 FileChangeRecord 类型。
9. 替换 AC-016 多 topic manifest planned 节点。
10. 运行 Python/Web/manifest 验证。
11. 写 Report、标记 done 并提交。

# Exit

0070 done 后，0072 可基于 file_changes topic 实现文件变化推送。
