---
title: Report 0031 — 调度机制实现
description: 调度机制实现完成报告：loop.md 支持、queue、dispatch、resource lock、CLI 命令
type: report
status: complete
created: 2026-07-18T00:00:00Z
---

# Report 0031: 调度机制实现

## 交付物

| 模块 | 文件 | 变更 |
|------|------|------|
| discovery | `infrastructure/discovery.py` | 新增 `_load_loop_md()`，优先读 loop.md，回退到 workflow.py meta |
| queue | `infrastructure/queue.py` | 新增：enqueue / dequeue / list_queue / queue_size |
| lock | `infrastructure/lock.py` | 新增 resource 粒度锁 + TTL 清理 |
| dispatch | `infrastructure/dispatch.py` | 新增：扫描队列、排序、加锁、执行（可注入 run_func） |
| CLI | `presentation/cli.py` | 新增 `loop enqueue`、`loop dispatch` |

## 测试

| 层级 | 新增 | 覆盖 |
|------|------|------|
| 单元测试 | +18 | queue(5), dispatch(5), lock(4), discovery/loop.md(4) |
| E2E | +5 | enqueue→dispatch 完整链路、资源冲突、失败处理 |
| 总计 | 195→218 | 全绿，无回归 |

## AC 覆盖

| AC | 状态 |
|-----|------|
| AC-010 loop.md 定义 | PASS |
| AC-011 队列与入队 | PASS |
| AC-012 Dispatch | PASS |
| AC-013 资源锁 | PASS |

## 未完成

- 不做常驻 daemon（pull 模型足够）
- 不做 webhook 触发（留到 `loop serve`）
- 不做优先级抢占