---
title: Worktree Isolation for Agent Calls
description: agent() 支持 isolation='worktree'，在独立 git worktree 中执行 agent，并发安全
type: adr
status: accepted
created: 2026-07-09T13:00:00Z
---

# ADR 0013: Worktree Isolation for Agent Calls

## Context

`parallel()` 中多个 agent 共享同一个工作目录，并发修改文件会冲突。bio-reproducer 的 Provision 和 Data 阶段可以并行执行独立任务，但共享文件系统会互相干扰。

Claude Code workflow 的 `agent(..., {isolation: 'worktree'})` 提供了隔离执行环境。loopflow 需要同样的能力。

## Decision

### isolation 参数

```python
agent("fix bug", isolation="worktree")
```

| 规则 | 说明 |
|------|------|
| 创建 | `git worktree add .agents/worktrees/lf_<run_id>_<seq>/` |
| 分支 | 从当前 HEAD 创建，命名 `lf/<run_id>/<seq>` |
| 执行 | agent 子进程的 cwd 设置为 worktree 目录 |
| 清理 | **不自动清理**——创建和清理解耦，workflow 作者决定 |
| 非 git 仓库 | 忽略 `isolation` 参数，在当前目录执行 |

### 为什么不做自动清理

ADR 0010 原则：loopflow 不关心业务语义。worktree 是否有变更、是否值得保留——这是业务判断。自动清理在"应该保留但被误删"的场景下出错。

Workflow 作者可以通过 `log()` 输出 worktree 路径，自行决定保留或删除。

### 与其他 API 的兼容

| 场景 | 行为 |
|------|------|
| `parallel()` + isolation | 每个 agent 独立 worktree，无冲突 |
| `pipeline()` + isolation | 同 parallel |
| resume + isolation | 已完成的 agent 缓存命中，不重新创建 worktree |

## Consequences

### 正面

- 并行 agent 完全隔离，安全并发
- 与 CC workflow 语义一致，迁移成本低
- 不自动清理 = 最小化设计，不越界

### 代价

- 每个 worktree 消耗磁盘（通常 ~100MB）
- 非 git 仓库不适用
- Workflow 作者需要理解 worktree 的概念和清理责任