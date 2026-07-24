---
title: ADR 0039 — 工作目录文件变化观察层
description: 以 phase 边界快照 diff 追踪工作目录文件变化，独立 file_changes.jsonl 持久化，不参与业务事件流和确定性重放
type: adr
status: accepted
created: 2026-07-23T12:00:00Z
---

# ADR 0039: 工作目录文件变化观察层

## Context

loopflow 的 workflow 在工作目录（pwd）下执行，Agent 调用可能创建、修改或删除文件。用户希望在 WebUI 中实时看到每个 Phase 完成后工作目录的文件变化——哪些文件被新增、修改或删除——以直观感知 workflow 的产出进度。

现有契约明确将文件副作用排除在框架责任之外（ADR-0036 §7：loopflow 不保证任意 Python 或外部系统副作用 exactly-once）。文件变化不是业务语义，不参与控制流、不参与确定性重放、不影响 Call 缓存命中。因此文件变化观察是**纯观察层**，与 `events.jsonl` 的业务事件流严格分离。

需要决定：观察数据的采集时机、存储格式、与 Phase 的关联方式、以及与现有事件契约的边界。

## Decision

### 1. 采集时机：Phase 边界快照 diff

在每次 `phase()` 调用时（即 Phase 切换边界），runtime 对工作目录拍摄文件系统快照，与上一个快照 diff，记录该 Phase 期间发生的文件变化。

```text
phase("采集") 开始
  → snapshot_0 = scan(pwd)
  → Agent 执行，可能创建/修改/删除文件
phase("处理") 开始
  → snapshot_1 = scan(pwd)
  → diff(snapshot_0, snapshot_1) → file_changes for "采集" phase
  → 追加到 file_changes.jsonl
```

首次 `phase()` 调用时建立基线快照，不产生 diff（因为还没有前一个 Phase 可对比）。Run 启动时也建立初始基线快照。

**快照内容：** 文件路径（相对 pwd）、大小（bytes）、mtime（ns）。不读取文件内容，不做行级 diff。

**扫描范围：** pwd 下的所有文件，排除：
- `.agents/worktrees/`（loopflow 自身的 worktree 隔离目录）
- `.git/`（版本控制元数据）
- `__pycache__/`、`.pyc` 文件
- 用户可通过 `meta.file_observation.exclude` 声明额外排除路径（glob 模式）

### 2. 存储格式：独立 `file_changes.jsonl`

文件变化记录在 Run 目录下独立的 `file_changes.jsonl`，**不写入 `events.jsonl`**：

```
~/.loopflow/runs/lf_<pwd-path>/<uuid>/
├── run.json
├── state.json
├── events.jsonl          # 业务事件流（phase + agent），不变
├── file_changes.jsonl    # 新增：文件变化观察数据
├── interventions/
└── <call-id>.jsonl
```

每行一个 JSON 记录：

| 字段 | 类型 | 必填 | 语义 |
|------|------|------|------|
| seq | integer | 是 | Run 内从 1 开始严格递增的序号，作为 SSE `file_changes` topic 的游标（详见 [ADR-0041](0041-sse-multi-topic-transport.md)） |
| phase | string | 是 | 产生这些变化的 Phase title |
| phase_id | string | 是 | 对应的 Phase occurrence 标识，与 events.jsonl 中的 phase_id 一致 |
| ts | ISO 8601 | 是 | 快照拍摄时间 |
| changes | object[] | 是 | 文件变化列表 |
| changes[].path | string | 是 | 相对 pwd 的文件路径 |
| changes[].action | string | 是 | `created` / `modified` / `deleted` |
| changes[].size | integer | created/modified 时必填 | 变化后的文件大小（bytes） |
| changes[].prev_size | integer | modified/deleted 时必填 | 变化前的文件大小（bytes） |

示例：

```jsonl
{"seq":1,"phase":"采集","phase_id":"phase-1","ts":"2026-07-23T12:00:05Z","changes":[{"path":"data/raw.json","action":"created","size":1024}]}
{"seq":2,"phase":"处理","phase_id":"phase-2","ts":"2026-07-23T12:00:10Z","changes":[{"path":"data/raw.json","action":"modified","size":2048,"prev_size":1024},{"path":"data/clean.json","action":"created","size":512}]}
```

### 3. 与业务事件流的边界

| 维度 | events.jsonl | file_changes.jsonl |
|------|-------------|-------------------|
| 性质 | 业务事件（控制流语义） | 观察数据（无控制流语义） |
| 参与重放 | 是（确定性重放的事实源） | 否（recover 时不重现文件变化） |
| 参与缓存命中 | 是（通过 phase_id/call_id 关联） | 否 |
| 序号 | event_id（严格递增） | seq（严格递增，独立于 event_id） |
| SSE 推送 | `event: run_event` topic，event_id 为游标 | `event: file_changes` topic，seq 为游标（详见 [ADR-0041](0041-sse-multi-topic-transport.md)） |
| 读取方式 | application service 结构化查询 | application service 独立查询 + SSE 实时推送 |

**file_changes.jsonl 不参与 ADR-0034 的 v2 事件信封、不参与 ADR-0036 的确定性重放契约。** 文件变化通过 SSE 的 `file_changes` topic 实时推送（ADR-0041 多 topic transport），不进入 events.jsonl，不影响 run_event topic 的 event_id 游标。

### 4. WebUI 展示

Runs 工作台新增文件变化区域，位于 Phase 详情下方：

- 按所选 Phase occurrence 展示该 Phase 期间的文件变化列表
- 每行显示：文件路径、action 图标（+/-/~）、大小变化
- created 文件高亮（视觉 token 来自 DESIGN.md）
- 文件变化区域有独立滚动，不影响 Phase 图和 Calls/Events 布局
- 无 file_changes.jsonl 的 Run（legacy 或未启用）显示空状态，不报错

### 5. worktree 隔离场景

当 Agent 使用 `isolation="worktree"` 时，文件变化发生在 worktree 路径而非 pwd。快照仍扫描 pwd，worktree 内的变化不纳入观察（worktree 是隔离执行空间，其变化在 worktree 合并回 pwd 时才对 pwd 可见）。这与 BR-011 的 worktree 语义一致——worktree 不自动合并，合并是 workflow 的显式操作。

### 6. 性能边界

- 快照使用 `os.scandir` 递归遍历，不使用 watchdog/fs watcher
- 大目录（>10k 文件）时快照可能耗时；快照在 phase 边界同步执行，不阻塞 Agent 调用
- `meta.file_observation.enabled` 可设为 `false` 禁用观察（默认 `true`）
- 禁用时不创建 file_changes.jsonl，WebUI 显示空状态

## Alternatives

### 方案 A：文件变化写入 events.jsonl（拒绝）

- 优点：单一事件流，SSE 自动推送。
- 缺点：污染业务事件契约；文件变化不是业务语义，不应参与确定性重放；违反 ADR-0034 的事件信封设计意图；SSE 推送大列表影响实时事件延迟；recover 重放时会产生重复记录或 event_id 空洞。

### 方案 B：使用 watchdog/fs watcher 实时监听（拒绝）

- 优点：实时性更高，不依赖 phase 边界。
- 缺点：引入新依赖（watchdog）；watcher 需要常驻线程/进程，与 loopflow 的进程模型复杂化；实时事件量大，无法按 Phase 聚合；与 worktree 隔离的交互复杂。

### 方案 C：worktree diff 方式（部分场景保留）

- 优点：最精确，可做行级 diff。
- 缺点：要求 workflow 使用 worktree 隔离；只展示 Run 结束后的累计 diff，不是运行中实时；worktree 不一定启用。
- 决策：作为未来可选增强保留，不作为首版方案。当 workflow 全部使用 worktree 隔离时，可额外提供 worktree diff 视图。

### 方案 D：框架提供 write_file() API 追踪（拒绝）

- 优点：精确关联到 Call。
- 缺点：打破"框架不追踪副作用"哲学；workflow 作者必须改用框架 API 而非原生 open()；侵入性强，限制 Python 原生能力。

### 方案 E：独立 REST 轮询（拒绝）

- 优点：不动 SSE。
- 缺点：非实时，前端需要轮询或 phase 事件触发拉取；体验差；不符合"文件变化是实时数据"的定位。SSE 多 topic transport（ADR-0041）已解决此问题。

## Consequences

### 正面

- 用户可直观看到每个 Phase 的文件产出，理解 workflow 的工作进展。
- 与业务事件流严格分离，不破坏确定性重放契约。
- 纯 stdlib 实现，无新依赖。
- 通过 SSE `file_changes` topic 实时推送，无需轮询。

### 负面

- phase 边界快照对大目录有性能开销。
- 只追踪文件级变化，不提供行级 diff。
- worktree 隔离的 Agent 变化在 worktree 内不可见。
- 非文件副作用（数据库、网络调用等）不在观察范围。
- 依赖 ADR-0041 的 SSE 多 topic transport 实现。

### 不做的

- 不追踪文件内容 diff（行级）。
- 不进入 events.jsonl（不参与 run_event topic）。
- 不参与确定性重放和缓存命中。
- 不追踪 worktree 内部变化。
- 不引入 fs watcher 依赖。

## Architecture Boundary

本 ADR 约束 runtime 的 phase 边界快照采集、file_changes.jsonl 的写入，以及 application service 的文件变化查询读模型。SSE 传输层由 [ADR-0041](0041-sse-multi-topic-transport.md) 约束。

- runtime 在 `phase()` 调用时执行快照和 diff，追加到 `file_changes.jsonl`（含 `seq` 序号）；
- application service 提供按 run_id 和 phase_id 查询文件变化的读模型，以及按 `seq` 的 replay 查询；
- Web adapter 通过 SSE `file_changes` topic 推送（ADR-0041），不进入 events.jsonl；
- 前端按服务端提供的结构化变化列表渲染，不自行扫描文件系统。

## Verification

不需要外部技术选型 spike。纯 stdlib 实现，在 TEST_INFRA/DEVELOP 阶段通过以下测试验证：

| 验证项 | 复现步骤 | 预期结论 |
|--------|---------|---------|
| phase 边界快照 diff 正确 | workflow 在 Phase A 创建文件、Phase B 修改文件 | file_changes.jsonl 中 Phase A 记录 created，Phase B 记录 modified |
| seq 严格递增 | 检查 file_changes.jsonl | seq 从 1 开始严格递增，无空洞 |
| 不写入 events.jsonl | 运行 workflow 后检查 events.jsonl | events.jsonl 中无文件变化相关事件 |
| SSE file_changes topic 推送 | 建立 SSE 连接，workflow 产生文件变化 | 收到 `event: file_changes`，`id:` 为 seq，data 含 changes 列表 |
| 不参与重放 | failed Run recover 后检查 file_changes.jsonl | recover 不追加新的 file_changes 记录 |
| 大目录性能 | pwd 含 10k 文件的 workflow | phase 边界快照 < 500ms |
| exclude 规则 | meta.file_observation.exclude 声明排除 `*.tmp` | .tmp 文件不出现在 changes 中 |
| worktree 隔离 | Agent 使用 isolation=worktree 在 worktree 内创建文件 | pwd 快照不包含 worktree 内变化 |
| legacy Run 兼容 | 无 file_changes.jsonl 的旧 Run | SSE file_changes topic 不推送，WebUI 显示空状态，不报错 |
