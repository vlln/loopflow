---
title: 单 agent 运行入口 AC
description: 验收 loop run --agent 单 agent_def 运行的完整 Run 语义、schema 应用、错误处理与恢复
type: ac
status: proposed
created: 2026-07-28T10:45:00Z
---

# AC-032: 单 agent 运行入口

验证 `loopflow run <loop> --agent <name>` 直接运行单个 agent_def。对应 Spec v17 BR-058、ADR-0055。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-032-N-1 | loop 含 `agents/reader.md`；以 `--mock bash` 运行 | 执行 `loopflow run <loop> --agent reader --prompt "任务"` | 创建完整 Run（run.json/run_dir/events.jsonl/`0001.jsonl` 缓存）；不导入 workflow.py（workflow digest 为 None）；Run done；agent 结果打印到 stdout；退出码 0 | 自动化 |
| AC-032-N-2 | agent_def 声明 `output` schema（如 `{"type":"object","required":["verdict"]}`） | 执行 `--agent` 运行（mock auto） | `output` 自动作为 schema 应用；返回结构化结果并以 JSON 打印到 stdout | 自动化 |
| AC-032-N-3 | 单 agent Run A 因 backend transient 错误 failed | 对 A 执行 recover mode=retry | 沿用 A.run_id；Call 0001 重新执行；Run 最终 done | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-032-B-1 | agent_def body 含 `{{topic}}`，`requires.params` 声明 `topic` 必填 | 执行 `--agent reader --prompt "任务" --param topic=rna-seq` | body 渲染后作为 system prompt；运行成功。未传 `--param topic` 时以明确错误退出，不创建 Run | 自动化 |
| AC-032-B-2 | agent 在单 agent 运行中返回 `__loopflow.status=waiting_input` 且 durable session 可用 | 执行 `--agent` 运行 | Run 进入 waiting_input；可经既有应答通道（WebUI / `loop respond`）恢复同一 Run | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-032-E-1 | loop 的 `agents/` 下不存在 `ghost.md` | 执行 `--agent ghost --prompt "任务"` | 以明确错误（agent_def 不存在）退出；不创建 Run | 自动化 |
| AC-032-E-2 | `--agent` 与 `--args` 同时传入 | 执行命令 | 拒绝执行并提示 `--args` 在单 agent 模式无消费者；不创建 Run | 自动化 |
| AC-032-E-3 | `--prompt` 与 `--prompt-file` 同传，或两者皆缺 | 执行命令 | 以用法错误退出（二选一必填）；不创建 Run | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-032-F-1 | agent 执行失败（backend 非零退出，task 类别） | 执行 `--agent` 运行 | Run failed；error_category 与 run 语义一致；退出码 1；缓存含 failed 段，可 recover | 自动化 |
