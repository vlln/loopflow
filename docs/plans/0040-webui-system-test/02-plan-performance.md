---
title: WebUI Performance Test Plan
description: 验证 1000 Runs API 首屏与 100 条 1 KiB SSE 的冻结 p95 指标。
type: plan
status: done
created: 2026-07-19T07:10:00Z
---

# Context

Spec 0001 与 AC-016-B-2 要求两项 p95 均小于 500ms。

# Request

在真实本地 HTTP server 上预热 1000 Runs 数据集后测量 API 30 次，并持续写入/订阅 100 条 1 KiB SSE。

# Output Format

独立 Report，记录 p95、max、顺序和阈值结论。

# Constraints

单客户端、无后端执行负载；使用单调时钟。

# Checkpoint

两项 p95 <500ms，SSE event_id 严格递增。

# Steps

1. 构造并预热数据集。
2. 测量 Runs API 30 次。
3. 测量 SSE 100 条并校验顺序。
