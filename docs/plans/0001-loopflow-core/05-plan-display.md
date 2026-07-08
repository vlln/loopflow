---
title: 05-plan-display
description: 实现 TTY 进度渲染：phase 分组、agent 状态树、spinner、耗时
type: plan
status: pending
created: 2026-07-07T12:00:00Z
---

# 05-plan-display: TTY 进度渲染

## Context

loopflow 执行时需要实时显示进度：当前 phase、agent 状态（running/done/failed）、耗时。使用 rich 实现。

## Request

实现 `src/loopflow/display.py`，提供：

1. `Display(name, run_id)` — 初始化显示面板
2. `set_phases(topology)` — 设置阶段拓扑
3. `phase(title)` — 开始新阶段
4. `agent_start(label, prompt)` — agent 开始
5. `agent_done(label, success, elapsed)` — agent 完成
6. `agent_skip(label)` — agent 缓存命中
7. `start_auto_refresh()` / `stop()` — 自动刷新

## Output Format

`src/loopflow/display.py`，约 150-200 行。配套单元测试 `tests/unit/test_display.py`。

## Constraints

- 使用 rich 的 Live/Layout 实现
- 非 TTY 环境降级为简单文本输出
- 进度信息写入 stderr，不影响 stdout 输出

## Checkpoint

1. TTY 环境显示 phase 分组 + agent 状态树
2. 非 TTY 环境降级为文本
3. agent 状态实时更新
4. 耗时显示正确

## Steps

1. 实现 Display 类：rich Live + Layout
2. 实现 phase()：分组显示
3. 实现 agent_start/agent_done/agent_skip：状态更新
4. 实现非 TTY 降级
5. 编写单元测试