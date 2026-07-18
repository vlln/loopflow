---
title: ADR 0034 — Web 事件与 Run 生命周期契约
description: 定义 events.jsonl v2 信封、Phase occurrence 关联、缓存边界、断线恢复、原子元数据写入和陈旧进程 reconcile
type: adr
status: proposed
created: 2026-07-18T00:00:00Z
---

# ADR 0034: Web 事件与 Run 生命周期契约

## Context

WebUI 要同时观察正在写入的 Run、重建带循环的 Phase 执行图、查看 Agent Call 过程并在断线后继续消费事件。现有运行目录中有两种 JSONL：`events.jsonl` 是 Run 级时间线，`<seq>.jsonl` 是 Agent 调用的 resume 缓存。两者服务于不同正确性目标，不能因 Web 展示而合并为一种格式。

历史 `events.jsonl` 没有统一信封，部分事件缺少 Phase 或 Call 关联。循环还会让同名 Phase 多次出现，仅凭 `phase` title 无法区分 occurrence。与此同时，`run.json` 会被执行进程写入并被 Web 服务并发读取；只检查 PID 也可能因 PID 复用把已退出 Run 误判为 running。

需要冻结 Web 事件关联、缓存兼容、断线恢复、原子持久化和陈旧状态修复的共同契约。

## Decision

### 1. `events.jsonl` 使用 v2 统一信封

新写入 `events.jsonl` 的每一行使用以下信封：

| 字段 | 类型 | 必填 | 语义 |
|------|------|------|------|
| version | integer | 是 | 固定为 `2` |
| event_id | integer | 是 | Run 内从 1 开始严格递增的持久化事件序号 |
| type | string | 是 | `phase`、`agent_start`、ACP 兼容事件、`agent_done` 等 |
| ts | ISO 8601 string | 是 | 事件发生时间 |
| run_id | string | 是 | 所属 Run |
| phase | string | 条件必填 | Phase title；Phase 和 Agent 事件必填 |
| phase_id | string | 条件必填 | 本次 Phase occurrence 的稳定标识；Phase 和 Agent 事件必填 |
| call_id | string | 条件必填 | 一次 Agent Call 的稳定标识；Agent 事件必填 |
| payload | object | 是 | 事件类型特有数据，不重复信封字段 |

示例：

```json
{"version":2,"event_id":1,"type":"phase","ts":"2026-07-18T20:00:00Z","run_id":"abc","phase":"Review","phase_id":"phase-1","payload":{"title":"Review","occurrence":1}}
{"version":2,"event_id":2,"type":"agent_start","ts":"2026-07-18T20:00:01Z","run_id":"abc","phase":"Review","phase_id":"phase-1","call_id":"call-1","payload":{"session":"wf_abc_1"}}
```

后端或缓存产生的扁平 ACP 兼容事件写入 `events.jsonl` 时，由运行时分配 `event_id` 并补齐当前 `run_id`、`phase`、`phase_id`、`call_id`，事件原有数据进入 `payload`。

### 2. Phase title 聚合，`phase_id` 区分 occurrence

`phase` 是 workflow 作者声明的 title，用于执行图聚合同名节点；`phase_id` 标识一次实际进入该 Phase 的 occurrence。每次进入 Phase 都生成新的稳定 `phase_id`，即使 title 相同。

Phase 事件的 `payload.occurrence` 是同 title 在该 Run 中从 1 开始的出现序号。Agent Calls 和事件只通过显式 `phase_id`/`call_id` 关联：

- 选择聚合 Phase 时可以列出其全部 occurrences；
- 选择某个 occurrence 时只显示同一 `phase_id` 的 Calls 和 Events；
- 不根据事件相邻位置、当前 UI 选择或 title 猜测 occurrence；
- 首版不从日志文本推断 Phase input、output 或 state diff。

### 3. `<seq>.jsonl` 保持扁平 resume 缓存

`<seq>.jsonl` 继续存储去掉 JSON-RPC 外壳的 ACP `SessionNotification` 兼容扁平事件，不使用 v2 Web 事件信封。它是 resume 正确性契约，不是 Web API 存储格式。

- Agent 执行时实时追加缓存事件，完成后追加扁平 `agent_done`；
- 新缓存事件可以携带 `phase`、`phase_id`、`call_id`，但不要求 `version`、`event_id`、`run_id`、`payload`；
- resume 只检查对应 `<seq>.jsonl` 是否存在，以及 `agent_done.exit_code == 0`；
- Web 展示只消费 `events.jsonl` 的 v2/legacy reader 结果，不把缓存文件当作第二条 Web 时间线；
- 不迁移既有缓存，不改变 ADR 0004 的序号重放和缓存命中语义。

### 4. Legacy 事件只做有证据的关联

没有 `version` 信封的历史 `events.jsonl` 视为 `legacy`。Reader 必须保留其原始事件顺序和内容，并尽力恢复聚合 Phase 图。

只有在事件自身存在明确 session、phase 或其他稳定证据时，才建立 Call 或 Phase occurrence 关联。并行交错、字段缺失或证据冲突时，事件标记为 `unattributed`。不得按文件位置、最近出现的 Phase 或 UI 需要虚构归属，也不要求改写历史文件。

### 5. `event_id` 是 SSE 断线恢复游标

`event_id` 在单个 Run 内严格递增且持久化后才可对 SSE 客户端可见。客户端提供最后确认的 `event_id`，服务端：

1. 从 `events.jsonl` 重放所有 `event_id > last_event_id` 的已持久化 v2 事件；
2. 继续推送之后成功追加的事件；
3. 允许客户端按 `event_id` 去重；
4. 游标超出可恢复范围时返回明确的不可恢复响应，不静默跳到最新事件；
5. 建立或重建 SSE 连接不得触发 Run 执行、resume 或状态修改。

Legacy 文件没有可靠 `event_id`，可以作为一次性历史时间线读取，但不承诺在 legacy 区间提供精确断点恢复。

### 6. `run.json` 与 `state.json` 原子更新

创建 Run、状态变化、Phase 变化和进程退出时，writer 在目标文件同目录写入临时文件，完成序列化后 flush，再以原子替换发布完整文件。替换 `run.json` 时，在同一份新 JSON 中更新其 `updated_at`。

Reader 只读取最终路径，不消费临时文件。写入失败不得留下部分 JSON 覆盖上一份有效数据。`state.json` 仍是纯 workflow state，不新增 `updated_at` 保留字段；它独立执行原子替换，不与 `run.json` 构成跨文件事务，也不因 state-only 更新改写 `run.json.updated_at`。JSONL 仍使用只追加语义。

### 7. 进程身份使用 PID + `process_started_at`

Run 启动执行进程时，将 `pid` 与该进程可验证的 `process_started_at` 一起原子写入 `run.json`。读取 `status=running` 的 Run 时同时检查：

- PID 对应进程存在；
- 该进程的启动标识与 `process_started_at` 匹配。

任一条件不成立，读模型返回派生状态 `stale`，但读取操作不修改磁盘。仅检查 PID 不足以确认身份，因为操作系统可能复用 PID。

### 8. 陈旧状态只通过显式 reconcile 修复

`reconcile` 是显式命令，不是读取的副作用。它再次校验 PID 与启动标识；确认陈旧后，以原子写将持久化状态更新为：

- `status = failed`；
- 设置 `finished_at`、`updated_at` 和说明进程丢失的 `error_summary`；
- 清除 `pid` 与 `process_started_at`。

完成 reconcile 后，该 Run 才进入允许 resume 的持久化状态。若二次校验发现进程仍有效，返回冲突且不修改文件。WebUI 不自动 reconcile，也不把 stale 直接当作 failed。

## Alternatives

### 方案 A：`events.jsonl` 与缓存共用 v2 信封

- 优点：表面上只有一种 JSONL 格式。
- 缺点：改变稳定的 resume 缓存契约；`event_id`、`run_id` 和 `payload` 对缓存命中无用；Web 展示需求会污染执行恢复机制。

### 方案 B：仅使用 `phase` title，不引入 `phase_id`

- 优点：事件更短，聚合图实现简单。
- 缺点：`Review -> Fix -> Review` 无法区分两次 Review，Call 和事件会错误混合，循环是 loopflow 的核心语义，不能接受。

### 方案 C：按 JSONL 邻近位置推断 legacy 归属

- 优点：旧 Run 看起来关联更完整。
- 缺点：并行事件会交错，推断结果不可证明且可能误导排错；宁可明确 unattributed，也不能制造虚假因果。

### 方案 D：SSE 只推送内存事件

- 优点：实现简单、延迟低。
- 缺点：服务重启和断线期间会丢事件；与文件化崩溃恢复模型冲突；无法用同一事实源重建 UI。

### 方案 E：读取 running 时自动修复为 failed

- 优点：用户无需单独操作。
- 缺点：查询产生写入副作用，存在进程检查瞬时失败导致误修复的风险，也使多个 reader 竞争写 `run.json`。

### 方案 F：仅以 PID 判断 Run 存活

- 优点：跨平台实现最少。
- 缺点：PID 可复用，会把无关进程误认为 Run 进程，进而错误开放 stop 或阻止 resume。

## Consequences

### 正面

- v2 `events.jsonl` 足以可靠重建循环 Phase、occurrence 和 Agent Call 过程。
- Web 事件协议与 resume 缓存各自保持单一职责，既有序号重放语义不被破坏。
- SSE 以持久化游标恢复，浏览器断线和 Web 服务重启不丢已落盘事件。
- Legacy 数据保持可读，同时明确表达无法证明的关联。
- 原子元数据写入避免 Web reader 观察到半写 JSON；显式 reconcile 避免读操作意外改状态。
- PID 与启动标识组合降低 PID 复用导致的错误 stop/resume 风险。

### 负面

- 每个 Agent 事件需要同时写入扁平缓存和 v2 Run 时间线，并维护两个有意不同的序列化边界。
- 运行时必须在线程/并行调用下协调 Run 内 `event_id` 分配和追加顺序。
- 跨平台获取可靠进程启动标识需要平台适配和测试。
- Legacy Run 的部分事件只能显示为 unattributed，无法获得与 v2 相同的交互完整性。
- 用户在 stale 后需要显式 reconcile，才能 resume。

### 不做的

- 不原地迁移或重写 legacy `events.jsonl` 和既有 `<seq>.jsonl`。
- 不把 `state.json` 内容自动解释为某个 Phase 的 input/output/state diff。
- 不让 SSE 连接控制 Run 生命周期。
- 不在查询 Run 时隐式 reconcile。

## Architecture Boundary

本 ADR 约束 RunContext/事件 writer、事件 reader、resume cache reader、Run repository、进程探测器以及公开给 Web/CLI 的 Run application service。

Web adapter 只能消费 application service 提供的结构化事件与状态；不能直接补写 event_id、推断 Phase 归属、修改 run.json 或自行执行 reconcile。前端只能按服务端提供的 `event_id`、`phase_id`、`call_id` 建立关联。

## Verification

本 ADR 是事件、持久化和生命周期的机制/契约决策，不包含待确认的外部技术选型，不需要 spike。有效性在后续 TEST_INFRA/DEVELOP 阶段通过契约测试、并发测试、故障注入和跨平台进程探测测试验证。
