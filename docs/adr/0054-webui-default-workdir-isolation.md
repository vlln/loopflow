---
title: ADR 0054 — WebUI/API 默认工作目录隔离
description: WebUI/API 创建 run 时未提供 working_directory，默认创建 run_dir/work 隔离目录而非 fallback 到 server cwd，与 CLI --work-dir "" 对齐，防止 file observer 误捕获外部进程的文件变更
type: adr
status: accepted
created: 2026-07-27T08:00:00Z
---

# ADR 0054: WebUI/API 默认工作目录隔离

## Context

[ADR-0042](0042-run-working-directory.md) 将 `working_directory` 提升为 run 的显式属性。REST API `POST /api/v1/runs` 接受可选 `working_directory`，缺省时 fallback 到 `Path.cwd()`（server 进程 cwd）。[BL-020](../backlog.md) 为 CLI 添加了 `--work-dir ""` 隔离模式（框架创建 `run_dir/work`）。

但 WebUI/API 路径缺少等价的默认隔离机制。当 server 启动于项目根目录（常见场景），所有未指定 `working_directory` 的 run 都以项目根为工作目录。后果：

1. **file observer 误捕获**：`FileChangeObserver` 扫描整个工作目录（`os.walk`），无法区分 run agent 写的文件和外部进程写的文件。另一个 Agent 同时修改 `src/loopflow/application/runner.py`，变更被归因到当前 run 的 agent call。
2. **文件预览指向错误目录**：run 结束后产物文件被清理，但 `resolve_working_directory` 仍解析到项目根，预览 404。

实测案例：run `bf862b1d` 的 `file_changes.jsonl` seq=2 记录了 `src/loopflow/application/runner.py` 的 modified（25648→25698 B），label 为 `evidence-verifier-0`——该 agent 不应修改源码，变更是外部 Agent 造成的。

## Decision

### 1. 未提供 working_directory 时默认隔离

`BackgroundRunExecutor.start()` 当 `working_directory` 参数为 `None`（未显式提供）时：

- **run_dir 命名**：仍用 server cwd（`Path.cwd()`）编码，保持目录分组不变（`lf_{encoded_cwd}/`）
- **实际工作目录**：在 `run_dir/work` 下创建隔离目录，作为子进程 chdir 目标
- **持久化**：`run.json` 的 `working_directory` 字段记录 `run_dir/work` 绝对路径（子进程 chdir 后 `Path.cwd()` 自然正确）
- **索引**：`append_run_index` 记录 `run_dir/work` 为 working directory

这与 CLI `--work-dir ""` 语义一致：框架管理的隔离目录，agent 产出落在 `run_dir/work` 而非 server cwd。

### 2. 显式提供 working_directory 时不变

用户提供 `working_directory` 时，行为与 ADR-0042 完全一致：校验绝对路径 + 已存在 + 是目录，子进程 chdir 到该路径。

### 3. recover/rerun 沿用原目录

recover/rerun 从 `run.json` 读取已持久化的 `working_directory`。旧 run（ADR-0042 时代创建）的 `working_directory` 是 server cwd——recover 时沿用，不强制隔离。新 run（本 ADR 生效后）的 `working_directory` 是 `run_dir/work`——recover 时沿用，自然正确。

### 4. 实现边界

修改仅限 `BackgroundRunExecutor.start()`（`execution.py`）。CLI 路径不经过 `BackgroundRunExecutor`，已有独立的 `--work-dir` 处理，不受影响。`web.py` 的 `create_run` 验证逻辑不变（`working_directory` 为 None 时不校验、不填充，传 None 给 executor）。

## Alternatives

| 方案 | 评估 |
|------|------|
| **前端默认填充 server cwd** | 不采纳。用户大概率不想让 run 在 server cwd 执行；填充 cwd 只是把隐式 fallback 变成显式传参，不解决隔离问题 |
| **file observer 排除 src/** | 不采纳。排除 `src/` 是项目特定行为，且不解决根因——任何外部文件修改都会被捕获。工作目录隔离才是正解 |
| **process-level 文件监控（inotify + PID 追踪）** | 不采纳。复杂度过高，平台差异大，与 snapshot-diff 架构不兼容 |

## Consequences

- **正面**：WebUI 创建的 run 不再捕获外部进程的文件变更；file changes 面板只展示 run 自身 agent 的产出
- **正面**：与 CLI `--work-dir ""` 语义统一
- **代价**：行为变更——旧 run 默认在 server cwd 执行，新 run 默认在 `run_dir/work` 执行。需要更新 AC-025-B-1 的预期
- **兼容**：显式提供 `working_directory` 的 run 不受影响；旧 run recover 沿用原目录

## Architecture Boundary

默认隔离逻辑在执行层（`application/execution.py` `BackgroundRunExecutor.start()`）；API 层（`application/web.py`）不感知本 ADR；observer 与 workflow 不变。

## Verification

非技术选型类 ADR：复用既有 `os.chdir` + `Path.mkdir` 标准库，无新依赖。可行性由 0097 容器的 AC 自动化测试证明（REST 不传 working_directory → run_dir/work 创建 → 子进程 chdir → observer 扫描隔离目录 的端到端链路）。
