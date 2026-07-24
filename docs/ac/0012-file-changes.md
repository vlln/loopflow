---
title: loopflow AC-0012 — 工作目录文件变化观察
description: 验收 phase 边界快照 diff、file_changes.jsonl 持久化、与业务事件流分离、WebUI 文件变化展示
type: ac
status: proposed
created: 2026-07-23T12:00:00Z
---

# AC-024: 工作目录文件变化观察

验证 phase 边界文件变化采集、独立持久化和 WebUI 展示。详见 [ADR-0039](../adr/0039-file-change-observation.md) 和 [BR-043](../spec/0001-loopflow.md)。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-N-1 | workflow 在 Phase A 创建 `data/raw.json`（1024 bytes），Phase B 修改该文件（2048 bytes）并创建 `data/clean.json`（512 bytes） | 执行 `loopflow run <name>`，检查 `file_changes.jsonl` | Phase A 记录含 `{"path":"data/raw.json","action":"created","size":1024}`；Phase B 记录含 `{"path":"data/raw.json","action":"modified","size":2048,"prev_size":1024}` 和 `{"path":"data/clean.json","action":"created","size":512}` | 自动化 |
| AC-024-N-2 | workflow 在 Phase C 删除 `data/raw.json` | 检查 `file_changes.jsonl` Phase C 记录 | 含 `{"path":"data/raw.json","action":"deleted","prev_size":2048}`，无 size 字段 | 自动化 |
| AC-024-N-3 | 同 AC-024-N-1 | 检查 `events.jsonl` | events.jsonl 中无文件变化相关事件；phase 事件和 agent 事件正常记录 | 自动化 |
| AC-024-N-4 | Run 有 `file_changes.jsonl`，WebUI 已打开该 Run | 选择 Phase A occurrence | Phase 详情下方显示文件变化列表：`data/raw.json` created（+图标，1024 bytes） | 自动化 |
| AC-024-N-5 | 同 AC-024-N-4 | 选择 Phase B occurrence | 显示 `data/raw.json` modified（~图标，1024→2048）和 `data/clean.json` created（+图标，512 bytes） | 自动化 |
| AC-024-N-6 | `file_changes.jsonl` 中 phase_id 与 `events.jsonl` 中 phase 事件的 phase_id 一致 | 对比两个文件中相同 Phase 的 phase_id | phase_id 完全匹配，可建立关联 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-B-1 | workflow 只调用一次 phase()，无文件变化 | 检查 `file_changes.jsonl` | 首次 phase() 建立基线快照，不产生 diff 记录；文件为空或只有基线行 | 自动化 |
| AC-024-B-2 | workflow 不调用 phase() | 检查 Run 目录 | 无 `file_changes.jsonl` 或文件为空；Run 正常完成 | 自动化 |
| AC-024-B-3 | `meta.file_observation.exclude = ["*.tmp", "build/"]`，workflow 在 Phase A 创建 `a.tmp` 和 `src/main.py` | 检查 `file_changes.jsonl` | `a.tmp` 不在 changes 中；`src/main.py` 在 changes 中；`build/` 下文件不被扫描 | 自动化 |
| AC-024-B-4 | `meta.file_observation.enabled = false` | 执行 `loopflow run <name>` | 不创建 `file_changes.jsonl`；Run 正常完成 | 自动化 |
| AC-024-B-5 | Agent 使用 `isolation="worktree"`，在 worktree 内创建文件 | 检查 `file_changes.jsonl` | pwd 快照不包含 worktree 内的文件变化 | 自动化 |
| AC-024-B-6 | 无 `file_changes.jsonl` 的 legacy Run | 在 WebUI 打开该 Run | 文件变化区域显示空状态或禁用状态，不报错，不返回 500 | 自动化 |
| AC-024-B-7 | Phase 期间无文件变化 | 在 WebUI 选择该 Phase | 文件变化区域显示空状态（"无文件变化"），不报错 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-E-1 | `file_changes.jsonl` 最后一行仅写入一半 | WebUI 请求文件变化 | 完整行全部返回；半行暂不返回，不报 500 | 自动化 |
| AC-024-E-2 | pwd 含 `.git/` 和 `__pycache__/` 目录，workflow 创建文件 | 检查 `file_changes.jsonl` | `.git/` 和 `__pycache__/` 下的文件不出现在 changes 中 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-F-1 | failed Run 执行 recover | 检查 recover 后的 `file_changes.jsonl` | recover 不追加新的 file_changes 记录；文件变化观察不参与重放 | 自动化 |
| AC-024-F-2 | pwd 含 10000 个文件，workflow 调用 phase() | 测量 phase 边界快照耗时 | 快照耗时 < 500ms，不阻塞 Agent 调用 | 自动化 |

---

## 模块级验收

以下不依赖运行时，纯单元测试验证。

| 编号 | 测试目标 | 预期结果 | 验证方式 |
|------|---------|---------|---------|
| AC-024-U-1 | 快照 diff：snapshot_0 为空，snapshot_1 含 `a.py` (100 bytes) | diff 返回 `[{"path":"a.py","action":"created","size":100}]` | 自动化 |
| AC-024-U-2 | 快照 diff：snapshot_0 含 `a.py` (100)，snapshot_1 含 `a.py` (200) | diff 返回 `[{"path":"a.py","action":"modified","size":200,"prev_size":100}]` | 自动化 |
| AC-024-U-3 | 快照 diff：snapshot_0 含 `a.py` (100)，snapshot_1 不含 `a.py` | diff 返回 `[{"path":"a.py","action":"deleted","prev_size":100}]` | 自动化 |
| AC-024-U-4 | exclude 规则匹配 `*.tmp` | 扫描结果不含 `.tmp` 文件 | 自动化 |
| AC-024-U-5 | file_changes.jsonl 不 import rich 或任何第三方库 | `import file_observation; "rich" not in sys.modules` | 自动化 |
