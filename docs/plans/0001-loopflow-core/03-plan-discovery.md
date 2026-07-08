---
title: 03-plan-discovery
description: 实现 Loop 发现与加载：扫描 ~/.loopflow/loops/，解析 workflow.py 和 agent 定义
type: plan
status: pending
created: 2026-07-07T12:00:00Z
---

# 03-plan-discovery: Loop 发现与加载

## Context

loop 定义存储在 `~/.loopflow/loops/<name>/`。Discovery 模块负责扫描已安装的 loop，解析 workflow.py 的 meta 块和 agents/ 下的 agent 定义文件。

## Request

实现 `src/loopflow/discovery.py`，提供：

1. `list_loops()` — 扫描 `~/.loopflow/loops/`，返回所有 loop 的 (name, meta, path)
2. `load_loop(name)` — 加载指定 loop：验证 workflow.py 存在、解析 meta、加载 agents
3. `list_agents(loop_name)` — 返回 loop 下的 agent 列表

## Output Format

`src/loopflow/discovery.py`，约 100-150 行。配套单元测试 `tests/unit/test_discovery.py`。

## Constraints

- `~/.loopflow/` 不存在时自动创建
- `meta` 必须是纯字面量（检查：无变量引用、无函数调用）
- Agent 定义文件必须含 `name` 和 `description` 字段
- 使用 pyyaml 解析 frontmatter

## Checkpoint

1. 空目录 → 返回空列表，不报错
2. 合法 loop 目录 → 正确解析 meta 和 agents
3. workflow.py 缺少 run() → 报错
4. agent 定义缺少 name → 报错
5. meta 非纯字面量 → 报错

## Steps

1. 实现 `list_loops()`：扫描目录，解析 meta
2. 实现 `load_loop()`：验证 + 加载
3. 实现 `list_agents()`：解析 agents/ 目录
4. 实现 meta 纯字面量检查
5. 编写单元测试