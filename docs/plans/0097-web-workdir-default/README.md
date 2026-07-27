# 0097 — WebUI/API 默认工作目录隔离（BL-026）

对应阶段：`DEVELOP`（增量迭代）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [WebUI/API 默认工作目录隔离](01-plan-web-workdir-default.md) | [Report](01-report-web-workdir-default.md) | done |

## 范围

- BL-026：`BackgroundRunExecutor.start()` 在 `working_directory` 未提供时，默认创建 `run_dir/work` 隔离目录
- ADR-0054：与 CLI `--work-dir ""` 语义对齐
- AC-0013：N-9/B-1修订/B-12/E-5/F-3 场景

## 非范围

- 不改 CLI 路径（已有 `--work-dir ""`）
- 不改 `web.py` 的 `create_run` 验证逻辑（`working_directory` 为 None 时不校验、传 None 给 executor）
- 不改 file observer 代码（observer 用 `Path.cwd()` 初始化，子进程 chdir 后自然扫描隔离目录）
- 不改前端（New Run 对话框 working directory 输入行为不变，留空=默认隔离）
