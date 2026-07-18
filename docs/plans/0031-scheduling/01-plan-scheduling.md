---
title: Plan 0031 — 调度机制实现
description: 实现 loop.md 支持、queue、dispatch、resource lock、CLI 命令
type: plan
status: done
created: 2026-07-18T00:00:00Z
---

# Plan 0031: 调度机制实现

## 目标

实现 ADR 0031 + ADR 0032 定义的调度机制。

## 执行单元

| 序号 | 任务 | 产出 |
|------|------|------|
| 01 | loop.md 支持：discovery 读取 loop.md frontmatter，回退到 workflow.py meta | 修改 `discovery.py` |
| 02 | queue 模块：enqueue / dequeue / list 操作 | 新增 `infrastructure/queue.py` |
| 03 | resource lock 扩展：lock.py 支持 resource 粒度锁 + TTL 清理 | 修改 `lock.py` |
| 04 | dispatch 模块：扫描队列、排序、加锁、执行 | 新增 `infrastructure/dispatch.py` |
| 05 | CLI 命令：`loop enqueue`、`loop dispatch` | 修改 `presentation/cli.py` |

## Constraints

- 不 import workflow.py 做 dispatch——只读 loop.md frontmatter 和 queue 文件
- dispatch 幂等——可被 cron/launchd 反复调用
- 文件锁复用现有 `lock.py` 的 O_CREAT|O_EXCL 模式
- 保持向后兼容：loop.md 不存在时回退到 workflow.py meta

## Checkpoint

- 所有 AC-010 ~ AC-013 场景通过
- 现有 195 个测试无回归
- `loop enqueue` + `loop dispatch` 端到端手动穿越