---
title: loopflow AC-0012 — 工作目录文件变化观察
description: 验收 Agent Call 完成边界快照 diff、file_changes.jsonl 持久化、与业务事件流分离、WebUI 文件变化展示
type: ac
status: proposed
created: 2026-07-23T12:00:00Z
---

# AC-024: 工作目录文件变化观察

验证 Agent Call 完成边界的文件变化采集、独立持久化和 WebUI 展示。关联语义以 ADR-0052 和 [BR-043](../spec/0001-loopflow.md) 为准。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-N-1 | call-a 完成前创建 `data/raw.json`（1024 bytes），call-b 完成前将其改为 2048 bytes 并创建 `data/clean.json`（512 bytes） | 执行 Run，检查 `file_changes.jsonl` | call-a 记录 created raw.json；call-b 记录 modified raw.json（含 prev_size=1024）和 created clean.json；两条分别含正确 call_id/label | 自动化 |
| AC-024-N-2 | call-c 完成前删除 `data/raw.json` | 检查 call-c 的记录 | changes 含 deleted raw.json、prev_size=2048 且无 size；记录 call_id=call-c | 自动化 |
| AC-024-N-3 | 同 AC-024-N-1 | 检查 `events.jsonl` | events.jsonl 中无文件变化事件；Agent/fork/join 事件正常记录 | 自动化 |
| AC-024-N-4 | Run 有 call-a 的 file change，WebUI 已打开 | 选择 AgentGraph 的 call-a | 文件面板高亮 raw.json created（1024 bytes） | 自动化 |
| AC-024-N-5 | 同一 Run 有 call-b 的两项变化 | 选择 call-b | 高亮 raw.json modified（1024→2048）和 clean.json created（512 bytes） | 自动化 |
| AC-024-N-6 | file_changes 与 events 中均存在 call-a | 对比两个文件 | call_id 完全一致，label 仅展示且不作为关联主键 | 自动化 |
| AC-024-N-7 | WebUI 已建立 SSE，workflow 产生文件变化 | 观察连接 | 收到 `event: file_changes`，id 为 seq，data 含 call_id/label/changes | 自动化 |
| AC-024-N-8 | 同 AC-024-N-1，WebUI 已打开 | 先选择 call-a，再切换 call-b | 每次只高亮所选 call_id 的动作；其他已跟踪文件弱化为无动作的已存在态 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-B-1 | workflow 只完成一次 Agent Call，工作目录无变化 | 检查 `file_changes.jsonl` | 启动基线和 Call 完成观察均不产生记录；文件不存在或为空 | 自动化 |
| AC-024-B-2 | workflow 不调用 Agent | 检查 Run 目录 | 无 `file_changes.jsonl` 或文件为空；Run 正常完成 | 自动化 |
| AC-024-B-3 | exclude 为 `*.tmp`、`build/`，call-a 创建 a.tmp、src/main.py、build/x | 检查记录 | 只包含 src/main.py；其他两项不被扫描 | 自动化 |
| AC-024-B-4 | `meta.file_observation.enabled = false` | 执行 `loopflow run <name>` | 不创建 `file_changes.jsonl`；Run 正常完成 | 自动化 |
| AC-024-B-5 | Agent 使用 `isolation="worktree"`，在 worktree 内创建文件 | 检查 `file_changes.jsonl` | pwd 快照不包含 worktree 内的文件变化 | 自动化 |
| AC-024-B-6 | 无 `file_changes.jsonl` 的 legacy Run | 在 WebUI 打开该 Run | 文件变化区域显示空状态，不报错，不返回 500 | 自动化 |
| AC-024-B-7 | 所选 Call 无文件变化 | 在 WebUI 选择该 Call | 文件变化区域显示空状态，不报错 | 自动化 |
| AC-024-B-8 | Run 启动前已有 config.yaml=100 bytes，call-a 将其改为 150 bytes | 检查首条记录 | 标记 modified、size=150、prev_size=100，不得标记 created；未变化文件不出现 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-E-1 | `file_changes.jsonl` 最后一行仅写入一半 | WebUI 请求文件变化 | 完整行全部返回；半行暂不返回，不报 500 | 自动化 |
| AC-024-E-2 | pwd 含 `.git/` 和 `__pycache__/` 目录，workflow 创建文件 | 检查 `file_changes.jsonl` | `.git/` 和 `__pycache__/` 下的文件不出现在 changes 中 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-024-F-1 | failed Run 执行 recover，前序成功 Call 从缓存重放，目标 Call 实际重试 | 检查记录 | 缓存命中的前序 Call 不重复追加；只有目标 Call 实际执行产生的新变化可追加；观察记录不参与结果重放 | 自动化 |
| AC-024-F-2 | pwd 含 10000 个文件，Agent Call 完成 | 测量完成边界快照耗时 | 快照耗时 < 500ms，不阻塞后续 Call | 自动化 |

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
| AC-024-U-6 | 连续追加 3 条 file_changes 记录 | 检查 seq | seq 为 1、2、3，严格递增，无空洞 | 自动化 |
