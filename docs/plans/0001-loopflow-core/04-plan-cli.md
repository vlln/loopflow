---
title: 04-plan-cli
description: 实现 CLI 命令：loop run / resume / status / list / stop
type: plan
status: pending
created: 2026-07-07T12:00:00Z
---

# 04-plan-cli: CLI 命令

## Context

loopflow 的 CLI 入口，使用 click 实现。命令：`loop run` / `loop resume` / `loop status` / `loop list` / `loop stop`。

## Request

实现 `src/loopflow/cli.py`，提供以下命令：

1. **loop run <name> [--args '<json>']** — 启动 loop 实例
2. **loop resume <run-id>** — 恢复崩溃的实例
3. **loop status <run-id>** — 查看实例状态
4. **loop list** — 列出所有 loop 定义和运行实例
5. **loop stop <run-id>** — 停止运行中的实例

## Output Format

`src/loopflow/cli.py`，约 200-300 行。配套集成测试 `tests/integration/test_cli.py`。

## Constraints

- 使用 click 实现命令路由
- `loop run` 创建 run 实例目录，写入 run.json，启动 runtime
- `loop resume` 检查 run.json status，重新执行 workflow.py
- `loop list` 输出 loop 定义和运行实例两张表
- `loop status` 输出 run.json 的核心字段 + agent 调用进度
- `loop stop` 发 SIGTERM 给后台进程，清理 pid 文件

## Checkpoint

1. `loop run hello` 启动实例，产生 run.json + jsonl 缓存
2. `loop resume <id>` 正确恢复，已完成 agent 跳过
3. `loop list` 显示 loop 定义和运行实例
4. `loop status <id>` 显示进度
5. `loop stop <id>` 终止进程

## Steps

1. 实现 `loop run` — 发现 loop → 创建 run → 加载 workflow → 执行
2. 实现 `loop resume` — 加载 run → 设置 resume 标志 → 执行 workflow
3. 实现 `loop list` — 扫描 loops/ + runs/
4. 实现 `loop status` — 读取 run.json + jsonl 缓存
5. 实现 `loop stop` — 读取 pid 文件 → kill + 清理
6. 编写集成测试