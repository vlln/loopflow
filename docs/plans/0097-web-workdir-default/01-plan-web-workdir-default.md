---
title: WebUI/API 默认工作目录隔离 Plan
description: BL-026 在 BackgroundRunExecutor.start() 中，working_directory 未提供时默认创建 run_dir/work 隔离目录，与 CLI --work-dir "" 对齐
type: plan
status: pending
created: 2026-07-27T08:30:00Z
---

# Goal

修改 `BackgroundRunExecutor.start()`，当 `working_directory` 参数为 `None`（未显式提供）时，在 `run_dir/work` 下创建隔离目录作为子进程 chdir 目标，而非 fallback 到 server cwd（`Path.cwd()`）。

# Constraints

- 修改仅限 `execution.py` `BackgroundRunExecutor.start()`；不改 `web.py`、CLI、observer、workflow
- `run_dir` 命名仍按 server cwd 编码（`lf_{encoded_cwd}/`），保持目录分组不变
- `append_run_index` 记录 `run_dir/work` 为 working directory（resolve_working_directory 优先读 run.json，索引是 fallback）
- recover/rerun 从 `run.json` 读取已持久化的 `working_directory`，行为不变
- 显式提供 `working_directory` 时行为不变（ADR-0042 原逻辑）

# Steps

1. 建 `docs/plans/0097-web-workdir-default/`（README + 本 Plan）
2. 修改 `execution.py` `BackgroundRunExecutor.start()`：
   - 跟踪 `working_directory` 是否为显式提供（`explicit = working_directory is not None`）
   - recover 路径：从 `run.json` 读取 `working_directory`，若存在则 `explicit = True`
   - `base` = 显式值或 `Path.cwd()`（用于 run_dir 编码）
   - `run_dir` 创建后，若 `not explicit`，创建 `run_dir/work` 作为 `working_directory`
   - `append_run_index` 和子进程 args 传入最终的 `working_directory`
3. 编写/更新测试：
   - 未提供 `working_directory` → `run.json` 的 `working_directory` 为 `run_dir/work` 路径
   - 未提供 `working_directory` → 子进程 `Path.cwd()` 为 `run_dir/work`
   - 未提供 `working_directory` → `file_changes.jsonl` 不记录 server cwd 下的外部文件变更（F-3）
   - 显式提供 `working_directory` → 行为不变（N-1 回归）
   - recover 旧 run（run.json 有 server cwd）→ 沿用原值，不创建 `run_dir/work`（B-12）
4. 运行 `pytest tests/unit -q` 确认零回归
5. 运行 `pytest tests/integration -q -k "working_directory or work_dir or file_change"` 确认集成测试
6. Report + README done

# Acceptance

- AC-025-N-9：未提供 `working_directory` → `run.json` 记录 `run_dir/work`，run 目录落在 `lf_{server_cwd}/` 下
- AC-025-B-1：子进程 chdir 到 `run_dir/work`，observer 扫描 `run_dir/work` 而非 server cwd
- AC-025-B-12：旧 run recover 沿用原 `working_directory`（server cwd），不创建 `run_dir/work`
- AC-025-F-3：外部进程修改 server cwd 下的文件 → `file_changes.jsonl` 不记录
- `pytest tests/unit -q` 零回归
- `git diff develop..fix/0097 --stat` 只含 `execution.py` + 测试文件

# Checkpoint

- unit 全绿
- 新增测试覆盖 N-9/B-1/B-12/F-3 四个场景
- 显式提供 `working_directory` 的既有测试（N-1 等）无回归

# Exit

全部 Acceptance 通过，写 Report，由用户合回 develop（--no-ff）。
