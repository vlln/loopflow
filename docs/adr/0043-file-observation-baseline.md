---
title: ADR 0043 — 文件观察基线快照语义
description: run 启动时建立基线快照，phase diff 针对基线或上一快照，使"created"真正表示 phase 期间新建；实现向 AC-024-B-1 的文档语义对齐，纠正首次快照全量标记 created 的权宜行为
type: adr
status: superseded
created: 2026-07-24T05:30:00Z
---

# ADR 0043: 文件观察基线快照语义

## Context

AC-024-B-1 的文档语义是：**首次 phase() 建立基线快照，不产生 diff 记录**。但当前实现与之矛盾：

- `FileChangeObserver.observe()` 首个快照与空集 diff，把工作目录**全部既有文件**标记为 `created`
- 对应测试 `test_first_observe_marks_all_files_as_created` 固化了这个权宜行为
- 0072 交接时将其实合理化描述为"预期行为"

人工验收确认了真实需求：**区分"目录中原本存在的东西"和"phase 执行后新增的东西"**；且切换 phase 查看时，上一个 phase 新增的文件在下一个 phase 不应再是 Created 状态。文档（AC-024-B-1）写的本来就是对的，是实现偏离了文档。

## Decision

### 1. run 启动时建立基线快照

observer 初始化后、workflow 执行前，立即对工作目录拍一次快照作为基线（内存态，不写入 `file_changes.jsonl`）。之后每次 `observe()` 始终与上一快照 diff：

- 第一个 phase 的记录只含相对基线的**真 diff**（phase 期间真正新建/修改/删除的文件）
- 无变化则无记录——与 AC-024-B-1 文档语义一致
- 预先存在的文件出现在后续 phase 的 diff 中时，按真实动作标记（修改 = `modified` 带 `prev_size`，不会是 `created`）

### 2. 存储格式不变

`file_changes.jsonl` 的记录结构、seq 语义不变；基线不产生记录行。legacy run 的既有记录（含全量 created 的首记录）原地保留，不重写、不迁移。

### 3. 前端显示语义随基线自然正确

0074 已交付的目录树机制（per-phase `byPhase` 映射）不需要结构变更：选中 phase P 时，P 内变更显示动作 chip（高亮），其余被跟踪文件显示中性"已存在"态（弱化、无 chip）。基线语义落地后，"上一个 phase 新增的，在下一个 phase 不再是 Created"自然成立。

## Alternatives

| 方案 | 评估 |
|------|------|
| 基线写入 `file_changes.jsonl` 作为 seq=0 特殊行 | 不采纳。污染数据文件，REST/SSE 读模型需额外过滤；基线是执行期内存态，无需持久化 |
| 保持 all-created 行为，仅前端过滤首记录 | 不采纳。数据层语义错误不应由呈现层打补丁；且首记录的 seq 游标会推高后续所有序号 |
| 修订 AC-024-B-1 文档以匹配实现 | 不采纳。人工验收确认文档语义才是真实需求；应修正实现而非修改契约 |

## Consequences

- AC-024-B-1 文档文本**不变**（实现向文档对齐）；其映射测试改为基线断言（`test_first_observe_establishes_baseline_no_record`）
- AC-024-U-1（空集 → created 的单元 diff）保持有效：`_diff` 语义不变，变化的是首个快照的比较对象
- AC-024-N-1/N-2 场景不变：phase 期间真正创建的文件仍标记 `created`
- 新增 AC-024-B-8：第一个 phase **修改**预先存在的文件时标记 `modified`（prev_size 来自基线），不得标记 `created`
- 新增 AC-024-N-8：WebUI 目录树标记随选中 phase 切换（0074 已交付机制，本 ADR 补齐语义契约）
- ADR-0039 保持 accepted 不被修改；本 ADR 是对其观察语义的细化

## Architecture Boundary

基线建立发生在执行层（`application/execution.py` observer 初始化后调用 `seed()`）；观察层（`infrastructure/file_observation.py`）提供 `seed()` 能力但不知道 run 生命周期；前端显示语义由既有 `byPhase` 机制承载。

## Verification

非技术选型类 ADR：快照与 diff 复用 ADR-0039 已验证的既有机制，仅改变首次比较对象，豁免 spike 验证。正确性由 0076 容器的 AC-024-B-1/B-8 自动化测试直接证明。
