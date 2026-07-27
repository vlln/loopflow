# 0092 — CLI --work-dir 统一工作目录（BL-020）

对应阶段：`DEVELOP`（0.23.0 迭代）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [CLI --work-dir](01-plan-work-dir.md) | [Report](01-report-work-dir.md) | done |

## 范围

- BL-020：`cli.py` 新增 `--work-dir` option + chdir 逻辑
  - 缺省（omitted）→ 当前目录
  - `""`（空串）→ 框架托管：`run_dir/work`（与 loopflow 内部隔离）
  - `<path>` → 该路径
- 框架在执行前 chdir 到目标目录；loop 及其 agent 以此为 cwd，loop 自身不处理路径

## 非范围

- 不改 deep-research loop 代码
- 不动 context.py/runtime.py/execution.py 的 work_dir 传递链（"先加又删"回到原状，diff 无泄漏）

## 依据

- BL-020（backlog）
- [0076](../0076-run-working-directory/) run working directory 既有设计的 CLI 侧补齐
