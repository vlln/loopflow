# 0001-loopflow-core

## 子任务

| 编号 | 任务 | 状态 | 分支 | 关联 AC |
|------|------|------|------|---------|
| 01 | 后端层精简 | pending | feat/0001-core | — |
| 02 | Workflow Runtime | pending | feat/0001-core | AC-001, AC-002, AC-004, AC-005, AC-006 |
| 03 | Loop Discovery | pending | feat/0001-core | AC-007 |
| 04 | CLI 命令 | pending | feat/0001-core | AC-001, AC-002, AC-003, AC-008 |
| 05 | Display TUI | pending | feat/0001-core | — |

## 依赖关系

```
01-backend → 02-runtime → 03-discovery → 04-cli
                                     ↘ 05-display
```

## 架构说明

单体 CLI 工具，所有模块在一个 feat 分支中实现。模块间通过 import 引用，无需容器间依赖管理。执行顺序为代码依赖的自然顺序。