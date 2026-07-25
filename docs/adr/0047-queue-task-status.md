---
title: ADR 0047 — 队列任务显式状态语义（deferred/supersede）
description: 队列条目增加 status（pending/deferred/superseded）、status_reason、superseded_by；资源锁失败显式标记 deferred 留队，enqueue --supersede 显式取代同 loop 任务，dispatch 跳过并清理 superseded；终态不计入 dispatch errors
type: adr
status: accepted
created: 2026-07-25T00:00:00Z
---

# ADR 0047: 队列任务显式状态语义（deferred/supersede）

## Context

queue 任务目前是"一次性文件"：**存在即 pending**，dispatch 执行前 unlink。这个极简模型有三个缺口：

- 资源锁失败时"跳过留队"只是行为，**没有状态**——任务看起来和普通 pending 无异，无法回答"为什么还没执行"
- 同 loop 多任务**不去重**，用户重复 enqueue 会全部执行
- `skipped` 只出现在 dispatch 返回值里，**不落盘**，事后无从审计

AC-012-F-1（失败即出队不重试）语义保留。loopflow 无常驻调度器，misfire 补偿不适用，超出本轮范围。

## Decision

### 1. 队列条目增加状态字段

新增 `status`（`pending` / `deferred` / `superseded`，默认 `pending`）、`status_reason`、`superseded_by`（Spec v15 已声明）。

### 2. deferred：锁失败显式化

资源锁不可得时将任务标记 `deferred` + `status_reason` 留队——BR-019 语义不变，仅把隐式行为显式化；锁释放后的 dispatch 正常消费。

### 3. supersede：显式取代

`enqueue --supersede` 将同 loop 的 `pending`/`deferred` 任务标记 `superseded` + `superseded_by`；dispatch 跳过 `superseded` 任务并清理（删除文件），计入 summary 的 `superseded` 桶。**默认不取代**——显式 enqueue 是用户刻意行为，应被尊重。

### 4. 终态不计错误

`deferred`/`superseded` 均不计入 dispatch errors；dispatch summary 增加 `deferred`/`superseded` 两桶。

### 5. Web 投影透传

Web 队列投影（`web_resources.py` 的 `QueueRepository`）透传 `status`/`status_reason`，呈现层无需额外推断。

## Alternatives

| 方案 | 评估 |
|------|------|
| 终态任务保留在队列目录供审计 | 不采纳。队列目录是待办语义，混入终态会让"还有什么要做"变模糊；审计由 runs 历史承担，`superseded` 由 dispatch 清理 |
| 同 loop 自动去重 | 不采纳。显式 enqueue 语义应被尊重；取代必须显式 `--supersede`，静默去重会吞掉用户的真实意图 |

## Consequences

- BR-053；由 AC-028 验收
- AC-012-B-1（资源锁失败跳过留队）语义不变，实现层补状态写入
- `queue.py` 入队 schema 向后兼容：缺 `status` 字段的既有条目按 `pending` 处理
- 与 ADR-0045 衔接：paused loop 的队列任务经 dispatch 落入 `deferred` 桶

## Architecture Boundary

状态机与文件操作在 `infrastructure/queue.py`；消费决策在 `infrastructure/dispatch.py`；投影在 `infrastructure/web_resources.py`。

## Verification

非技术选型类 ADR：队列文件读写为既有机制，无新依赖，豁免 spike 验证。正确性由 AC-028 自动化测试直接证明。
