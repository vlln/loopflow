---
title: 单 agent 运行入口
description: loopflow run --agent 直接运行 loop 中的单个 agent_def，服务于评测与调试场景，不恢复 --only-phase
type: adr
status: accepted
created: 2026-07-28T10:45:00Z
---

# ADR 0055: 单 agent 运行入口

## Context

ADR 0052 删除 `--only-phase`/`--from-phase` 后，CLI 只能运行完整 workflow。两类场景失去官方入口：

1. **评测**：component 级评测需要对 loop 中的某个 agent_def 单独喂入准备好的输入（fixture 工作目录 + 任务 prompt），验证其业务逻辑，而非跑完整 workflow。bio-reproducer 的 12 个 component case 因此全部失效，只能手写临时 workflow 绕行。
2. **调试**：修改某个 agent 定义后只想重跑该 agent 看输出，不愿触发完整 workflow 的上游调用。

`--only-phase` 的旧语义是 workflow 内部过滤（workflow 代码全跑、部分调用被跳过），既依赖已删除的 Phase 抽象，又把"跑什么"的决定藏在引擎而非 workflow，ADR 0052 已否决，不恢复。

现有机制已具备最小调用路径：`runtime.agent(prompt, agent_def=...)` 只依赖 `RunContext`（run_dir、loop_dir、execution_options），不依赖 workflow.py；`workflow_digest` 在无 workflow 时为 `None`，digest 照常工作。

## Decision

### 1. CLI 形态：`loopflow run <loop> --agent <name>`

复用 `run` 命令而非新增子命令，`--work-dir`、`--mock`、`--transport`、`--backend`、`--model` 等现有标志语义不变。新增：

| 标志 | 约束 | 说明 |
|------|------|------|
| `--agent <name>` | required（启用本模式） | loop `agents/` 下的 agent_def 名；不存在即以明确错误退出，不启动 Run |
| `--prompt <text>` | 与 `--prompt-file` 二选一，必填 | 传给 agent 的动态任务指令 |
| `--prompt-file <path>` | 与 `--prompt` 二选一，必填 | 从文件读取任务指令（评测 harness 生成场景） |
| `--param <key=value>` | optional，可重复 | 渲染 agent_def body 中的 `{{param}}` 占位符，映射为 `agent()` 的模板参数 |

### 2. 完整 Run 语义，不执行 workflow.py

单 agent 运行是一个正常 Run：创建 run_dir、run.json、events.jsonl、`<call_id>.jsonl` 缓存，WebUI 可观察，失败后可 `recover`（目标 Call 即 `0001`）。loop 定义照常加载（loop.md 提供 backend/model 默认值），但**不导入、不执行 workflow.py**；该 Run 的 workflow digest 为 `None`。

`agent_def` 声明的 `output` schema 按现有 `agent()` 行为自动应用，返回结构化结果。运行结果打印到 stdout（schema 模式下为 JSON），供 harness 捕获；退出码沿用 run 语义（done=0，failed=1）。

agent 在单 agent 运行中返回 `waiting_input` 控制结果时，与 workflow 运行行为一致：Run 进入 `waiting_input`，可走正常应答与恢复通道。

### 3. 与评测 harness 的边界

框架只提供"运行一个 agent_def"的入口；prompt 的构造、fixture 的准备、结果的断言全部由调用方（评测 harness、开发者）负责。引擎不从 loop 的 workflow.py 推导该 agent 的上游上下文，也不提供 phase 输入的自动注入。

## Alternatives

### 生成临时 workflow.py 再执行

在 run_dir 生成只含一次 `agent()` 调用的临时 workflow 走标准路径。多一层间接：workflow digest 绑定临时文件内容，调试输出里出现用户没写过的代码，且与"不执行 workflow"的心智模型相悖。直接调用 `runtime.agent()` 已是现成最小路径。

### 独立子命令 `loop agent <loop> <name>`

命令面更直白，但要完整复制 `run` 的标志集（work-dir/mock/transport/backend/model）才能可用，两处维护必然漂移。作为 `run` 的模式标志只有一个入口。

### 恢复 `--only-phase`

见 Context。该语义把"跑哪些调用"的决定放在引擎而非 workflow，与 ADR 0052 的删除理由冲突，且无法服务"不跑 workflow"的评测场景。

## Consequences

### Positive

- 评测与调试有官方入口，bio-reproducer 类 harness 不再需要临时 workflow 绕行。
- 复用全部现有 Run 基础设施（缓存、事件、WebUI、recover），无并行实现。
- workflow digest 为 `None` 使单 agent Run 的缓存语义自洽，不与任何 workflow Run 混淆。

### Negative

- prompt 构造责任转移给调用方：agent_def 的输入契约（需要哪些文件、上游产物）没有任何框架校验，输入不足时表现为 agent 业务失败而非启动错误。
- `--agent` 模式下 `--args` 无消费者，需在 CLI 明确拒绝或忽略（避免静默误导）。

## Architecture Boundary

本 ADR 约束 CLI `run` 命令的模式分派和 `runtime.agent()` 的直接调用路径。单 agent 运行不得导入 workflow.py，不得伪造 workflow digest；presentation 层不得绕过 RunContext 直接构造 AgentRunner。

## Verification

不需要外部技术选型 spike（无新依赖，全部复用现有 runtime 路径）。进入 TEST_INFRA 后通过 CLI 集成测试与缓存/恢复契约测试验证；场景以 AC-0014 为准。
