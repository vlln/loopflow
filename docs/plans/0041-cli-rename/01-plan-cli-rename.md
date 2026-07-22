---
title: 01-plan-cli-rename
description: 将 CLI 二进制名称从 `loop` 改为 `loopflow`，保留 `loop` 别名向后兼容。同步更新所有文档中的 CLI 命令引用。
type: plan
status: pending
created: 2026-07-21T00:00:00Z
---

# 01-plan-cli-rename: CLI 命令重命名

## Context

当前 CLI 二进制名称为 `loop`（`pyproject.toml: [project.scripts] loop = "loopflow.presentation.cli:main"`），与项目名 `loopflow` 不一致。用户期望 `pip install loopflow` 后可直接使用 `loopflow` 命令。

## Request

将 CLI 命令从 `loop` 改为 `loopflow`，保持向后兼容。

## Steps

1. `pyproject.toml` — 新增 `loopflow` 入口，保留 `loop` 别名
2. `src/loopflow/presentation/cli.py` — docstring 更新为主名 `loopflow`，注明 `loop` 别名
3. 文档批量更新 — 所有 CLI 命令引用从 `loop <cmd>` 改为 `loopflow <cmd>`：
   - `README.md`
   - `CHANGELOG.md`
   - `docs/ac/` — 验收标准中的 CLI 用例
   - `docs/adr/` — 架构决策中的 CLI 引用
   - `docs/interface/` — Web API 接口文档
   - `docs/plans/` — 历史 Plan/Report 中的 CLI 引用
   - `docs/spec/` — 需求规格中的 CLI 引用

## Constraints

- 不修改测试代码（测试使用 `click.testing.CliRunner` 直接调用 `main` 函数）
- `loop` 别名保留，现有用户不受影响
- 不修改源代码中的概念性 "loop" 引用（如 "loop 定义"、"loop discovery" 等）

## Checkpoint

1. `loopflow --help` 正常输出，子命令与 `loop --help` 一致
2. 所有文档中 `loop run/resume/status/list/stop/enqueue/dispatch/web` 改为 `loopflow` 版本
3. 现有测试全部通过（275 passed）
4. `loop` 别名仍可用