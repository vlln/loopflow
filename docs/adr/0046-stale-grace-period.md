---
title: ADR 0046 — stale 失联宽限期
description: run.json 增加 stale_since，读模型首次判定 stale 时原子写入作为宽限期起点；默认 24h 宽限内 reconcile 返回 409 run_in_grace，期满后按 BR-032 转 failed；宽限内 worker 恢复写终态优先
type: adr
status: accepted
created: 2026-07-25T00:00:00Z
---

# ADR 0046: stale 失联宽限期

## Context

现状 stale 是**纯读时投影**：`web_storage.py` 的 `read_summary` 实时 PID 探活，失联即 stale、reconcile 即 failed，**没有时间维度**。这导致一个高频误伤场景：笔记本睡眠后 PID 探活失败，实际仍存活的 run 被误判失败。本地单用户场景下隔夜睡眠（8–12h）是常态而非异常。loopany 的 terminal-grace 提供了可借鉴的形态：失联先记账，给一段宽限期再宣判。

## Decision

### 1. run.json 增加 stale_since

读模型首次判定 stale 时原子写入 `stale_since`，此后**不刷新**（避免宽限期被读操作无限续命）；进程恢复或 reconcile 时清除。

### 2. 宽限期与 reconcile 语义

> 2026-07-27 修订：移除宽限期对 reconcile 的阻止。reconcile 在检查进程是否存活后（`_identity_matches`），如果进程已确认死亡，直接清理为 `failed`，不再等待宽限期过期。`stale_since` 仍记录并供 UI 显示，但不再阻塞 reconcile。原因：reconcile 本身已做进程探活——如果进程活着返回 `process_alive` 不做破坏性操作，如果死了直接清理是正确行为。宽限期阻止一个已确认死亡的 run 被清理没有安全收益，反而在频繁重启 server 的场景下导致 stale run 永远无法清理。

宽限期默认 24h（覆盖隔夜睡眠）。`stale_since` 记录宽限期起点，供 UI 呈现剩余时间。reconcile 不再被宽限期阻止——进程探活已确认死亡即立即清理。

### 3. worker 恢复优先

宽限期内 worker 恢复并写入终态时以 worker 写入为准（`execution.py` 的 epoch+status 乐观锁保证 worker 写入优先）：`stale_since` 清除，不发生 reconcile。

### 4. UI 呈现

宽限期内 stale 呈现"失联（宽限中）"与剩余时间，非警报化——宽限期的意义正是把"可能没事"与"确认出事"区分开。

## Alternatives

| 方案 | 评估 |
|------|------|
| 心跳机制（worker 周期写 heartbeat，以新鲜度判定） | 不采纳。worker 崩溃即停写，与 PID 探活等效但多一条写路径；睡眠恢复场景两者表现一致，简单优先 |
| 更短宽限期（如 6h） | 不采纳。本地单用户场景隔夜睡眠约 8–12h 常见，6h 仍误伤；误判失败的代价高于晚判，24h 更安全 |

## Consequences

- BR-052（对 BR-032 的补充约束，BR-032 原文不变）；由 AC-029 验收
- `web_storage.py` 的 `read_summary` 从纯读操作变为**首次 stale 时写 `stale_since`**，原子写复用 BR-031 既有机制
- legacy run 无 `stale_since`，按首次判定 stale 时记录，自然进入宽限期
- reconcile 调用方不再需要处理 `run_in_grace` 错误码（保留在错误映射表中向后兼容，但不再触发）

## Architecture Boundary

宽限期判定与 `stale_since` 读写落在 `infrastructure/web_storage.py`（仓储层）；错误码映射在 `presentation/web/server.py`；worker 侧不感知宽限期。

## Verification

非技术选型类 ADR：原子写与乐观锁均为既有机制，无新依赖，豁免 spike 验证。正确性由 AC-029 自动化测试直接证明（时间窗口用注入时钟/短窗口测试，不依赖真实等待）。
