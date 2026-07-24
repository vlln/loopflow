# 0070 SSE 多 topic 传输层

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [SSE 多 topic transport 实现](01-plan-sse-multi-topic.md) | [Report](01-report-sse-multi-topic.md) | done |

## 背景

ADR-0041 已 accepted。SSE 从 events.jsonl 管道重构为多 topic transport，支持 run_event 和 file_changes topic 各自独立游标。ADR-0034 §5 已修订 event_id 为 run_event topic 游标。

## 范围

- server.py SSE handler 从单源读取改为多源合并（events.jsonl + file_changes.jsonl）
- per-topic 游标（last_event_id + last_file_changes_id）
- SSE `event:` 字段区分 topic，`id:` 字段为 per-topic 游标
- stream_end 等所有 topic terminal
- 单 topic 游标超出不影响其他 topic
- 前端 api.ts connectRunEvents 扩展为多 topic 监听
- file_changes.jsonl 的 seq 字段和 replay 查询（为 0072 预留接口）

## 非范围

- 不实现文件变化采集（属于 0072）
- 不实现 declared phases 预显示（属于 0071）
- 不引入 WebSocket
- 不承诺跨 topic 顺序保证

## 依赖

- 无前置依赖，可独立开始
- 0072 依赖本容器完成
