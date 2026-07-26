---
title: CLI --work-dir 统一工作目录 Plan
description: BL-020 在 cli.py 加 --work-dir option + chdir 逻辑（缺省=cwd / ""=run_dir/work / <path>=该路径），框架 chdir，loop 用相对路径
type: plan
status: done
created: 2026-07-26T09:00:00Z
---

# Goal

在 CLI run 命令加 `--work-dir` option，由框架在执行前 chdir 到统一工作目录，loop 及其 agent 以此为 cwd、用相对路径，loop 自身不处理路径。代码已执行并验证，本 Plan 记录已执行计划。

# Constraints

- 不改 deep-research loop 代码：work-dir 是框架职责，loop 不感知
- 代码不返工：只加 `--work-dir` option + chdir，不重构 work_dir 传递链
- work_dir 传递链冗余删除不纳入本容器：context.py/runtime.py/execution.py 的 work_dir 字段/传递"先加又删"最终回到原状，本分支 diff 只含 cli.py
- 三态语义：omitted=cwd、`""`=run_dir/work（隔离）、`<path>`=该路径；不引入第四态

# Steps（已执行）

1. 建 `docs/plans/0092-work-dir/`（README + 本 Plan）
2. 分支 `feat/0092-work-dir` 从 develop
3. `cli.py` run 命令加 `--work-dir` option（default=None，help 说明三态）
4. run 函数加 chdir 逻辑：`work_dir is not None` 时，`""` → `run_dir/work`，`<path>` → `Path(work_dir)`，mkdir 后 `os.chdir(target)`
5. 验证：`pytest tests/unit` + mock `--work-dir ""` 确认 run_dir/work 隔离生效 + 三后端实测 deep-research
6. Report + README done
7. commit（2b4a8d2）

# Acceptance

- `pytest tests/unit -q` 364 passed，零回归
- `--work-dir ""`：框架创建 `run_dir/work` 并 chdir，loop 与 loopflow 内部隔离生效
- `--work-dir <path>`：chdir 到该路径
- 缺省 `--work-dir`：行为不变，用当前目录
- `git diff develop..feat/0092-work-dir --stat` 只含 cli.py

# Checkpoint

- unit 364 passed（chdir 不破坏既有契约）
- mock `--work-dir ""` 隔离生效（run_dir/work 创建 + chdir）
- 三后端实测端到端 deep-research（kimi/pi/pi-acp 各 24 claim，与 0091 共用证据）
- 分支隔离确认：diff 只含 cli.py，无 context/runtime/execution 泄漏

# Exit

全部 Acceptance 通过，写 Report，由用户合回 develop（--no-ff），不合并分支。
