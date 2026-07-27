---
title: CLI --work-dir 统一工作目录 Report
description: BL-020 完成，cli.py 加 --work-dir option + chdir 三态逻辑，unit 364 passed，mock 隔离生效，三后端实测跑通
type: report
status: complete
created: 2026-07-26T09:30:00Z
---

# Summary

在 CLI run 命令新增 `--work-dir` option，由框架在执行前 chdir 到统一工作目录。三态语义：缺省=当前目录、`""`=框架托管 `run_dir/work`（与 loopflow 内部隔离）、`<path>`=该路径。loop 及其 agent 以此为 cwd 用相对路径，loop 自身不处理路径。unit 364 passed，mock `--work-dir ""` 隔离生效，三后端实测端到端跑通 deep-research。

# Changes

| BL | 文件 | 改动 | commit |
|----|------|------|--------|
| BL-020 | `src/loopflow/presentation/cli.py` | 加 `--work-dir` option（default=None，help 说明三态）；run 函数在 run_dir 建立后、写 run.json 前做 chdir：`work_dir is not None` 时 `""`→`run_dir/work`、`<path>`→`Path(work_dir)`，mkdir 后 `os.chdir(target)` | 2b4a8d2 |

# 改动细节

## --work-dir 三态

`@click.option("--work-dir", default=None, help=...)` 声明。run 函数签名加 `work_dir` 参数。chdir 逻辑：

```python
if work_dir is not None:
    target = run_dir / "work" if work_dir == "" else Path(work_dir)
    target.mkdir(parents=True, exist_ok=True)
    os.chdir(target)
```

- omitted（default=None）→ 不进分支，cwd 不变（loop-run 当前目录）
- `""` → `run_dir/work`，框架托管，与 loopflow 内部（src/docs/tests）隔离
- `<path>` → 该路径

chdir 在 `append_run_index` 之后、写 `run.json` 之前 —— run_dir 已建立，loop 执行前完成切换。loop 及其 agent 以此为 cwd，用相对路径读写文件，loop 自身不处理路径。

## work_dir 传递链不纳入

context.py 的 work_dir 字段、runtime.py/execution.py/cli.py 的 work_dir 传递在迭代中"先加又删"，最终回到原状 —— `git diff develop..feat/0092-work-dir` 只含 cli.py 的 `--work-dir` 新增，无传递链泄漏。框架 chdir 后各层用 cwd 即可，不需要显式 work_dir 字段。

# Verification Results

| 验证 | 结果 |
|------|------|
| `pytest tests/unit -q` | 364 passed |
| `--work-dir ""` mock | 框架创建 `run_dir/work` 并 chdir，与 loopflow 内部隔离生效 |
| `--work-dir <path>` | chdir 到该路径 |
| 缺省 `--work-dir` | 行为不变，用当前目录 |
| kimi/pi/pi-acp 实测 deep-research | 各 24 claim 跑通（与 0091 共用三后端实测证据） |
| 分支隔离 `git diff develop..feat/0092-work-dir --stat` | 只含 cli.py（1 file, +16 -1） |

# Notes

- **三后端实测证据与 0091 共用**：本轮三后端实测端到端 deep-research（kimi 4 phase 24 claim、pi 修 text_end 后 24 claim、pi-acp 24 claim）同时验证了 0091 的框架修复与 0092 的 `--work-dir`（loop 在 chdir 后的 cwd 下跑通）。
- **不合并分支**：由用户合并，本容器只交付代码 + 文档。
