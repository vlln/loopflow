---
title: ADR 0045 — Loop 失败熔断与 loop_state 存储
description: 新增 per-loop 跨 run 状态文件 ~/.loopflow/loop_state/<loop>.json，连续失败达阈值自动熔断置 paused，dispatch 对 paused loop 的任务标记 deferred 留队，解除仅手动；告警以 UI 分级呈现节流
type: adr
status: accepted
created: 2026-07-25T00:00:00Z
---

# ADR 0045: Loop 失败熔断与 loop_state 存储

## Context

无人值守循环下，故障 loop 会被 cron 高频 dispatch 反复触发，**反复消耗配额而无人知晓**。阻断这个循环需要 per-loop 的跨 run 状态，但现状没有这个存储位：

- `state.json` 是 per-run 业务状态（BR-010），随 run 目录生灭，语义不同
- runs 历史虽是事实来源，但无法承担"暂停"这种写标记

用户已确认采用独立文件方案。

## Decision

### 1. 独立 loop_state 文件

新增 `~/.loopflow/loop_state/<loop>.json`，字段：`consecutive_failures` / `paused` / `paused_reason` / `paused_at` / `last_run_id`（Spec v15 已声明）。O(1) 读写，独立于 run 目录，不随 run 生灭。

### 2. 熔断规则

run 进入 failed 终态时该 loop `consecutive_failures` +1，done 时归零；达阈值（默认 5，loop.md frontmatter `failure_threshold` 可覆盖）置 `paused` 并写 `paused_reason`。手动 `loopflow run` 与 dispatch 触发的失败**都计入**。

### 3. paused 的消费语义

- dispatch：将 paused loop 的队列任务标记 `deferred` 留队，**不计失败**
- 手动 `loopflow run`：不拦截（用户显式操作优先于熔断保护）

### 4. 解除仅手动

CLI/Web 的 loop 恢复操作清除 `paused` 与 streak；**不提供自动解除**——熔断是保护闸，自动解除会让保护形同虚设。

### 5. 告警节流形态

无外部通知渠道，节流体现为 UI 呈现分级：streak 首次失败醒目提示，连续重复失败聚合为一条（带 streak 计数）；`error_summary` 在 Run 列表/详情可见（现状 `types.ts` 已定义该字段但 `App.tsx` 未渲染，本轮补齐呈现）。

## Alternatives

| 方案 | 评估 |
|------|------|
| 从 runs 目录推导 streak | 不采纳。runs 按工作目录分区 `lf_<pwd>/`，同 loop 跨目录需全量扫描合并，dispatch 高频路径代价大；且 paused 是写标记，推导只能产出只读事实 |
| 熔断状态写进 loop.md | 不采纳。loop.md 是用户声明契约，运行时不得改写；`failure_threshold` 只读不写 |

## Consequences

- BR-050 / BR-051；由 AC-027 验收
- 新增 `infrastructure/loop_state.py` 模块
- loop_state 文件损坏或缺失时按初始状态（`consecutive_failures=0`、`paused=false`）处理，不阻塞 run 与 dispatch
- dispatch summary 中 paused loop 的任务落入 `deferred` 桶而非 `errors`（与 ADR-0047 的队列状态语义衔接）

## Architecture Boundary

状态存取在 `infrastructure/loop_state.py`；计数与熔断判定在 `application/execution.py`（run 终态收尾）与 `infrastructure/dispatch.py`（消费前检查）；UI 分级呈现在 `web/`。

## Verification

非技术选型类 ADR：文件读写复用既有原子写机制，无新依赖，豁免 spike 验证。正确性由 AC-027 自动化测试直接证明。
