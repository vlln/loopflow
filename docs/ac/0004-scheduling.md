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
| AC-010-N-1 | `~/.loopflow/loops/hello/loop.md` 存在，含 name、description，body 非空 | 执行 `loopflow list` | 输出中包含 hello loop，描述来自 loop.md | 自动化 |
| AC-010-N-2 | `~/.loopflow/loops/hello/loop.md` 不存在，但 workflow.py 含 meta 字典 | 执行 `loopflow list` | 回退到读取 workflow.py meta，输出正常 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-010-E-1 | loop.md frontmatter 缺少 name 字段 | 执行 `loopflow list` | 该 loop 被跳过，不影响其他 loop 扫描 | 自动化 |
| AC-010-E-2 | loop.md 存在但 frontmatter 格式错误（非合法 YAML） | 执行 `loopflow list` | 回退到读取 workflow.py meta | 自动化 |

---
# AC-011: 队列与入队

验证 `loopflow enqueue` 命令的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-011-N-1 | loop hello 存在 | 执行 `loopflow enqueue hello --args '{"key":"val"}'` | `~/.loopflow/queue/` 下生成一个 JSON 文件，含 loop=hello、args、priority、created，stdout 输出队列文件路径 | 自动化 |
| AC-011-N-2 | 队列中已有 2 个任务 | 执行 `loopflow list --queue` | 输出 2 个待执行任务，按 priority 排序 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-011-E-1 | loop 名称不存在 | 执行 `loopflow enqueue nonexistent --args '{}'` | CLI 报错退出，stderr 提示 loop 未找到 | 自动化 |

---
# AC-012: Dispatch

验证 `loopflow dispatch` 命令的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-012-N-1 | 队列中有 1 个任务（loop hello），资源锁空闲 | 执行 `loopflow dispatch` | 任务从队列移除，loopflow run hello 执行，完成后 stdout 输出 dispatch 结果 | 自动化 |
| AC-012-N-2 | 队列中有 2 个任务，不同资源 | 执行 `loopflow dispatch` | 两个任务都执行，按优先级顺序 | 自动化 |
| AC-012-N-3 | 队列为空 | 执行 `loopflow dispatch` | 正常退出，无报错，stdout 输出"no tasks" | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-012-B-1 | 队列中有 2 个任务，声明同一资源（repo=/same/path） | 执行 `loopflow dispatch` | 优先级高的先执行，第二个任务因资源锁跳过，留在队列 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-012-F-1 | 队列中任务执行时 loopflow run 失败（exit_code != 0） | 执行 `loopflow dispatch` | 任务从队列移除（不重试），stderr 记录失败原因，dispatch 继续处理下一个任务 | 自动化 |

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
| AC-013-B-1 | 锁文件存在但超过 30 分钟 | 执行 `loopflow dispatch`，尝试对同一资源加锁 | 旧锁被清理，新锁成功创建 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-013-F-1 | 进程 A 持有资源锁，进程 B 的 dispatch 尝试对同一资源加锁 | 进程 B 执行 `loopflow dispatch` | 对应任务被跳过，留在队列，stderr 提示资源被占用 | 自动化 |

---
# AC-027: Loop 失败熔断

验证 loop 连续失败自动暂停调度（loop_state）的正确性。对应 Spec v15 BR-050/BR-051、ADR-0045。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-027-N-1 | loop hello 的 run 执行失败（failed 终态） | run 结束后检查 `~/.loopflow/loop_state/hello.json` | consecutive_failures=1，paused=false，last_run_id 为该 run | 自动化 |
| AC-027-N-2 | AC-027-N-1 之后 loop hello 的 run 执行成功（done） | 检查 loop_state/hello.json | consecutive_failures=0，paused=false | 自动化 |
| AC-027-N-3 | loop hello 连续 5 次 run 失败 | 第 5 次失败后检查 loop_state/hello.json | paused=true，paused_reason 含 `failure_streak:5`，paused_at 非空 | 自动化 |
| AC-027-N-4 | loop hello 已 paused，队列中有 hello 的任务 | 执行 `loopflow dispatch` | 该任务标记 deferred 留队（status_reason 含暂停原因），不计入 dispatch errors | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-027-B-1 | loop hello 的 loop.md frontmatter 声明 `failure_threshold: 2` | 连续 2 次 run 失败后检查 loop_state/hello.json | 第 2 次失败即 paused=true（阈值覆盖默认值 5） | 自动化 |
| AC-027-B-2 | loop hello 已 paused | 执行 loop 恢复操作（CLI/Web 解除暂停）后检查 loop_state/hello.json | paused=false，consecutive_failures=0，dispatch 恢复消费该 loop 任务 | 自动化 |
| AC-027-B-3 | loop hello 已 paused | 执行 `loopflow run hello`（手动触发） | run 正常执行，不被熔断拦截 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-027-E-1 | loop_state/hello.json 内容损坏（非法 JSON）或不存在 | 执行 `loopflow dispatch` | 按初始状态（consecutive_failures=0、paused=false）处理，dispatch 正常执行，不报错退出 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-027-F-1 | loop hello 的 run 由 `loopflow run` 手动触发并失败（非 dispatch） | 检查 loop_state/hello.json | 手动触发的失败同样计入 consecutive_failures（熔断与触发方式无关） | 自动化 |

---
# AC-028: 队列任务显式状态

验证队列任务状态机 pending/deferred/superseded 的正确性。对应 Spec v15 BR-053、ADR-0047。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-028-N-1 | loop hello 存在 | 执行 `loopflow enqueue hello` 后检查队列文件 | 任务 JSON 含 status=pending | 自动化 |
| AC-028-N-2 | 队列中有任务声明资源 repo=/same/path，该资源锁被持有 | 执行 `loopflow dispatch` | 任务标记 status=deferred、status_reason 非空，留在队列；锁释放后再次 dispatch 该任务被正常执行 | 自动化 |
| AC-028-N-3 | 队列中有 loop hello 的 pending 任务 A | 执行 `loopflow enqueue hello --supersede`（生成任务 B） | 任务 A 标记 status=superseded、superseded_by=B 的 uuid；任务 B 为 pending | 自动化 |
| AC-028-N-4 | 队列中有 superseded 任务 A 和 pending 任务 B（同 loop） | 执行 `loopflow dispatch` | A 被跳过并清理（文件删除），仅 B 执行；dispatch summary 含 superseded 计数且不计入 errors | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-028-B-1 | 队列中没有 loop hello 的任务 | 执行 `loopflow enqueue hello --supersede` | 与正常入队一致：新任务 pending，无 supersede 动作 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-028-E-1 | 队列文件含未知 status 值（如 "unknown_state"）或缺失 status 字段 | 执行 `loopflow dispatch` | 按 pending 处理，任务正常消费，不阻塞 dispatch | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-028-F-1 | 队列中同时存在 deferred 和 superseded 任务 | 执行 `loopflow dispatch` | 两者均不计入 dispatch errors；summary 中 deferred、superseded 分别计数 | 自动化 |
