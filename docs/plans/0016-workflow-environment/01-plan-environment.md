---
title: Workflow Environment Declaration
description: 实现 ADR 0016 — meta.requires.environment 环境文件声明与校验
type: plan
status: done
created: 2026-07-10T11:30:00Z
---

# Plan: Workflow Environment Declaration

## 范围

实现 `meta.requires.environment` 声明，`loop run`/`loop resume` 启动时校验文件存在。

## 步骤

### 1. `_check_environment()` 辅助函数

- 读取 `meta.requires.environment`
- 检查文件相对于 `loop_dir` 是否存在
- 不存在则报错退出

### 2. 集成到 `run` 和 `resume` 命令

- 在 `load_loop()` 后调用 `_check_environment()`

## 关联

- ADR 0016
- Spec v5 BR-014