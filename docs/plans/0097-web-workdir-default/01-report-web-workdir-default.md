---
title: WebUI/API 默认工作目录隔离 Report
description: BL-026 在 BackgroundRunExecutor.start() 中实现默认工作目录隔离，未提供 working_directory 时创建 run_dir/work，346 unit + 18 integration 全绿
type: report
status: complete
created: 2026-07-27T09:00:00Z
---

# 结果

## 修改范围

| 文件 | 变更 |
|------|------|
| `src/loopflow/application/execution.py` | `BackgroundRunExecutor.start()` 未提供 `working_directory` 时创建 `run_dir/work` 隔离目录 |
| `tests/unit/test_web_execution.py` | 更新 `test_background_executor_uses_shared_target`；新增 3 个测试覆盖 N-9/B-1/B-12/F-3 |

## AC 验收

| AC 编号 | 场景 | 结果 |
|---------|------|------|
| AC-025-N-9 | 未提供 working_directory → run.json 记录 run_dir/work，run 目录落在 lf_<server_cwd>/ 下 | PASS |
| AC-025-B-1 | 子进程 chdir 到 run_dir/work，observer 扫描 run_dir/work 而非 server cwd | PASS |
| AC-025-B-12 | 旧 run recover 沿用原 working_directory（server cwd），不创建 run_dir/work | PASS |
| AC-025-F-3 | 外部进程修改 server cwd 下的文件 → file_changes.jsonl 不记录 | PASS |

## 回归

- `pytest tests/unit -q`：346 passed，零回归
- `pytest tests/integration -q -k "working_directory or work_dir or file_change or run_file or create_run"`：18 passed

## 代码变更摘要

`BackgroundRunExecutor.start()` 核心改动：

1. 跟踪 `explicit = working_directory is not None`
2. recover 路径：从 run.json 读取 working_directory，若存在则 `explicit = True`
3. `base` = 显式值或 `Path.cwd()`（用于 run_dir 编码，保持目录分组不变）
4. run_dir 创建后，若 `not explicit`，创建 `run_dir/work` 作为 working_directory
5. `append_run_index` 和子进程 args 传入最终的 working_directory

CLI 路径不受影响（已有 `--work-dir ""` 独立处理）。`web.py` 不受影响（`working_directory` 为 None 时不校验、传 None 给 executor）。observer 不受影响（子进程 chdir 后 `Path.cwd()` 自然指向隔离目录）。
