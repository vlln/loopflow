---
title: WebUI Performance Test Report
description: 记录 1000 Runs API 与 100 条 SSE 延迟专项结果。
type: report
status: complete
created: 2026-07-19T07:10:00Z
---

# 结果

| 指标 | 样本 | p95 | max | 阈值 | 结果 |
|------|------|-----|-----|------|------|
| 1000 Runs 数据集 API | 30 | 56.81ms | 56.93ms | <500ms | PASS |
| 1 KiB SSE 落盘到可读 | 100 | 98.93ms | 104.06ms | <500ms | PASS |

SSE 收到 100/100，event_id 严格按 1..100 递增。两项均有显著余量，无性能阻塞。
