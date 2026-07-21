---
title: Web API Plan
description: 实现标准库 REST、SSE、静态资源服务和 loop web 安全绑定命令。
type: plan
status: done
created: 2026-07-19T06:05:00Z
---

# Context

0036 已提供 HTTP 无关的 WebApplication、repositories、事件 replay 和后台 workflow executor。Interface 0001 冻结了 REST/SSE wire contract 与 bind safety。

# Request

实现 `/api/v1` 全部 endpoint、统一错误信封、1 MiB 请求限制、SSE replay/live tail、wheel 静态资源与 `loop web`。

# Output Format

- `src/loopflow/presentation/web/` 标准库 server/handler。
- CLI `web` command，默认 loopback，远程绑定双确认。
- HTTP/SSE/静态资源/进程安全契约和集成测试。

# Constraints

1. 不引入 Web framework 或第三方 HTTP client。
2. handler 不直接扫描路径或实现 lifecycle。
3. 非 loopback host 未设置 allow_remote 时不得创建 socket。
4. JSON body 上限 1 MiB，未知字段交给 application validation。
5. SSE 以 persisted event_id 恢复，legacy 不提供精确 cursor。

# Checkpoint

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| REST | Interface 0001 endpoint/status/error/header 全部契约测试通过 | `9d48b49`；HTTP integration tests |
| SSE | replay、live、end、cursor、legacy、reader failure 正确 | `9d48b49`；event_id=5 failure injection |
| Static | `/` 与 hashed assets 从 wheel package resource 返回 | `9d48b49`；HTTP static + wheel smoke |
| Bind | loopback 默认、remote opt-in、拒绝时不创建 socket | `9d48b49`；CLI/bind tests |
| Quality | 新增 Python >=80%，MR gate 全绿 | 聚焦 85.18%；MR gate 全绿 |

# Steps

1. TDD 建立 handler routing、JSON/error response。
2. 接入 WebApplication 全部 REST endpoint。
3. 实现 SSE replay/live tail 与 stream end/error。
4. 实现 package static fallback 和安全路径。
5. 实现 `loop web` bind safety 与 composition root。
6. 运行契约、集成、coverage、MR 与 submission gates。

# Acceptance

- AC-014-N-4
- AC-014-N-5
- AC-014-N-6
- AC-014-N-7
- AC-014-F-1
- AC-014-F-2
- AC-015-E-1
- AC-015-F-1
- AC-015-F-2
- AC-016-N-1
- AC-016-N-2
- AC-016-B-1
- AC-016-B-2
- AC-016-E-1
- AC-016-E-2
- AC-016-F-1
- AC-016-F-2
- AC-017-B-2
- AC-017-E-1
- AC-017-E-2
- AC-017-F-1
- AC-018-N-2
- AC-018-E-1
- AC-018-E-2
- AC-018-F-1
- AC-018-F-2
- AC-019-N-3
- AC-019-N-4
- AC-019-F-3
