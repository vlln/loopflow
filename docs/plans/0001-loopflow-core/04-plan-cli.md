---
title: 04-plan-cli
description: 实现 CLI 命令：loopflow run / resume / status / list / stop
type: plan
status: pending
created: 2026-07-07T12:00:00Z
---

# 04-plan-cli: CLI 命令

## Context

loopflow 的 CLI 入口，使用 click 实现。命令：`loopflow run` / `loopflow resume` / `loopflow status` / `loopflow list` / `loopflow stop`。

## Request

实现 `src/loopflow/cli.py`，提供以下命令：

1. **loopflow run <name> [--args '<json>']** — 启动 loop 实例
2. **loopflow resume <run-id>** — 恢复崩溃的实例
3. **loopflow status <run-id>** — 查看实例状态
4. **loopflow list** — 列出所有 loop 定义和运行实例
5. **loopflow stop <run-id>** — 停止运行中的实例

## Output Format

`src/loopflow/cli.py`，约 200-300 行。配套集成测试 `tests/integration/test_cli.py`。

## Constraints

- 使用 click 实现命令路由
- `loopflow run` 创建 run 实例目录，写入 run.json，启动 runtime
- `loopflow resume` 检查 run.json status，重新执行 workflow.py
- `loopflow list` 输出 loop 定义和运行实例两张表
- `loopflow status` 输出 run.json 的核心字段 + agent 调用进度
- `loopflow stop` 发 SIGTERM 给后台进程，清理 pid 文件

## Checkpoint

1. `loopflow run hello` 启动实例，产生 run.json + jsonl 缓存
2. `loopflow resume <id>` 正确恢复，已完成 agent 跳过
3. `loopflow list` 显示 loop 定义和运行实例
4. `loopflow status <id>` 显示进度
5. `loopflow stop <id>` 终止进程

## Steps

1. 实现 `loopflow run` — 发现 loop → 创建 run → 加载 workflow → 执行
2. 实现 `loopflow resume` — 加载 run → 设置 resume 标志 → 执行 workflow
3. 实现 `loopflow list` — 扫描 loops/ + runs/
4. 实现 `loopflow status` — 读取 run.json + jsonl 缓存
5. 实现 `loopflow stop` — 读取 pid 文件 → kill + 清理
6. 编写集成测试