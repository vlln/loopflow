---
title: 01-report-cli-rename
description: CLI 重命名执行报告：loop → loopflow，保留 loop 别名
type: report
status: complete
created: 2026-07-21T00:00:00Z
---

# 01-report-cli-rename: CLI 重命名执行报告

## 执行摘要

在 `pyproject.toml` 中新增 `loopflow` 入口点，保留 `loop` 别名。同步更新所有文档中的 CLI 命令引用。

## 改动清单

### 代码（2 文件）

| 文件 | 改动 |
|------|------|
| `pyproject.toml` | 新增 `loopflow = "loopflow.presentation.cli:main"`，保留 `loop` |
| `src/loopflow/presentation/cli.py` | docstring 更新为主名 `loopflow`，注明 `loop` 别名 |

### 文档（22 文件）

| 文件 | 改动 |
|------|------|
| `README.md` | 所有 CLI 示例改为 `loopflow` |
| `CHANGELOG.md` | 版本记录中的 CLI 引用 |
| `docs/ac/0001-loopflow.md` | 验收标准中的 CLI 用例 |
| `docs/ac/0004-scheduling.md` | 调度相关 CLI 用例 |
| `docs/ac/0009-phase-graph.md` | 执行图相关 CLI 用例 |
| `docs/adr/0011-agent-output-error.md` | `loopflow resume` |
| `docs/adr/0016-workflow-environment.md` | `loopflow run` |
| `docs/adr/0031-loop-definition.md` | `loopflow list`/`loopflow run` |
| `docs/adr/0032-dispatch-queue.md` | `loopflow enqueue`/`loopflow dispatch`/launchd plist 路径 |
| `docs/adr/0033-webui-architecture.md` | `loopflow web` |
| `docs/adr/0035-webui-test-infrastructure.md` | `loopflow web` |
| `docs/interface/0001-web-api.md` | `loopflow web` |
| `docs/plans/0001-loopflow-core/04-plan-cli.md` | 历史 Plan CLI 引用 |
| `docs/plans/0016-workflow-environment/01-plan-environment.md` | 历史 Plan CLI 引用 |
| `docs/plans/0031-scheduling/01-plan-scheduling.md` | 历史 Plan CLI 引用 |
| `docs/plans/0031-scheduling/01-report-scheduling.md` | 历史 Report CLI 引用 |
| `docs/plans/0035-webui-test-infra/README.md` | 历史 Plan CLI 引用 |
| `docs/plans/0038-web-api/01-plan-web-api.md` | 历史 Plan CLI 引用 |
| `docs/plans/0038-web-api/01-report-web-api.md` | 历史 Report CLI 引用 |
| `docs/spec/0001-loopflow.md` | 需求规格中的 CLI 引用 |
| `docs/vision.md` | 愿景文档中的 CLI 引用 |

## 验证

- `loopflow --help` 正常运行，输出 8 个子命令
- `loop --help` 正常运行，别名保留
- 275 个测试全部通过（1 skipped）
- 148 处文档引用已更新

## 未改动

- 测试文件 — 使用 `click.testing.CliRunner` 直接调用 `main`，不引用二进制名
- 源代码中的概念性 "loop" 引用（`queue.py` 模块 docstring 等）
- `loop` 别名在 `pyproject.toml` 和 `cli.py` 中保留