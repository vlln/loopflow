---
title: loopflow 调度 AC
description: loopflow 调度机制验收标准：loop.md 定义、dispatch、queue、resource lock
type: ac
status: active
created: 2026-07-18T00:00:00Z
---

# AC-010: loop.md 定义

验证 loop.md 作为 loop 声明式定义文件的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-010-N-1 | `~/.loopflow/loops/hello/loop.md` 存在，含 name、description，body 非空 | 执行 `loop list` | 输出中包含 hello loop，描述来自 loop.md | 自动化 |
| AC-010-N-2 | `~/.loopflow/loops/hello/loop.md` 不存在，但 workflow.py 含 meta 字典 | 执行 `loop list` | 回退到读取 workflow.py meta，输出正常 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-010-E-1 | loop.md frontmatter 缺少 name 字段 | 执行 `loop list` | 该 loop 被跳过，不影响其他 loop 扫描 | 自动化 |
| AC-010-E-2 | loop.md 存在但 frontmatter 格式错误（非合法 YAML） | 执行 `loop list` | 回退到读取 workflow.py meta | 自动化 |

---
# AC-011: 队列与入队

验证 `loop enqueue` 命令的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-011-N-1 | loop hello 存在 | 执行 `loop enqueue hello --args '{"key":"val"}'` | `~/.loopflow/queue/` 下生成一个 JSON 文件，含 loop=hello、args、priority、created，stdout 输出队列文件路径 | 自动化 |
| AC-011-N-2 | 队列中已有 2 个任务 | 执行 `loop list --queue` | 输出 2 个待执行任务，按 priority 排序 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-011-E-1 | loop 名称不存在 | 执行 `loop enqueue nonexistent --args '{}'` | CLI 报错退出，stderr 提示 loop 未找到 | 自动化 |

---
# AC-012: Dispatch

验证 `loop dispatch` 命令的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-012-N-1 | 队列中有 1 个任务（loop hello），资源锁空闲 | 执行 `loop dispatch` | 任务从队列移除，loop run hello 执行，完成后 stdout 输出 dispatch 结果 | 自动化 |
| AC-012-N-2 | 队列中有 2 个任务，不同资源 | 执行 `loop dispatch` | 两个任务都执行，按优先级顺序 | 自动化 |
| AC-012-N-3 | 队列为空 | 执行 `loop dispatch` | 正常退出，无报错，stdout 输出"no tasks" | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-012-B-1 | 队列中有 2 个任务，声明同一资源（repo=/same/path） | 执行 `loop dispatch` | 优先级高的先执行，第二个任务因资源锁跳过，留在队列 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-012-F-1 | 队列中任务执行时 loop run 失败（exit_code != 0） | 执行 `loop dispatch` | 任务从队列移除（不重试），stderr 记录失败原因，dispatch 继续处理下一个任务 | 自动化 |

---
# AC-013: 资源锁

验证资源锁机制的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-013-N-1 | 无锁 | dispatch 对资源 repo=/path/to/project 加锁 | `~/.loopflow/locks/repo-<hash>.lock` 创建，含 PID 和时间戳 | 自动化 |
| AC-013-N-2 | 同 AC-013-N-1，loop 执行完成 | 检查锁文件 | 锁文件已删除 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-013-B-1 | 锁文件存在但超过 30 分钟 | 执行 `loop dispatch`，尝试对同一资源加锁 | 旧锁被清理，新锁成功创建 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-013-F-1 | 进程 A 持有资源锁，进程 B 的 dispatch 尝试对同一资源加锁 | 进程 B 执行 `loop dispatch` | 对应任务被跳过，留在队列，stderr 提示资源被占用 | 自动化 |