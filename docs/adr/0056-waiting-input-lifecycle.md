---
title: waiting_input 生命周期：CLI 应答通道与无人值守策略
description: CLI 前台内联应答 intervention、新增 loopflow respond 命令、intervene 支持 default/timeout、--unattended 无人值守模式，扩展 ADR 0036 §5
type: adr
status: proposed
created: 2026-07-28T10:45:00Z
---

# ADR 0056: waiting_input 生命周期：CLI 应答通道与无人值守策略

## Context

ADR 0036 §5 定义了人工介入的持久化模型：请求落盘、执行进程退出、应答后重放恢复。但应答通道只有 WebUI/HTTP API，产生两个实测痛点：

1. **CLI 用户无应答通道**（BL-044）：`loopflow run` 前台执行进入 `waiting_input` 后进程退出，终端没有任何提示和应答手段，用户以为 run 卡死，只能另开 WebUI 应答。CLI 进程在前台执行期间持有 tty stdin 且无任何消费者。
2. **无人值守环境死等**（BL-045）：headless/CI/benchmark 环境中 run 进入 `waiting_input` 无人应答，只能空等到外部墙钟超时，浪费整个执行窗口。`intervene()` 没有 default/timeout 机制，启动时也无法声明"不要等我"。

ADR 0036 否决"worker 阻塞等待回答"的理由（占用进程与锁、重启丢调用栈）仍然成立，本 ADR 不改变"请求落盘 + 进程退出 + 重放恢复"的执行模型，只在其上扩展应答通道与无人值守策略。

## Decision

### 1. CLI 前台内联应答

前台 `loopflow run` 捕获 `InterventionPending` 后，若 stdin 是 tty：

1. 列出本次 pending 的请求（key、prompt、options）；
2. 逐题内联提问：`options` 非空显示编号选择，`allow_custom=true` 接受自由文本，校验规则与 `answer_requests()` 完全一致；
3. 通过**应用层应答路径**（与 Web handler 相同的 `answer_requests()` + recover 命令，不经 HTTP）持久化回答并就地开始恢复；
4. 恢复仍命中新的 pending 请求时重复上述循环，直到 run 到达 done/failed 或用户中断（Ctrl-C 保持 `waiting_input` 退出，回答不落盘）。

每次内联应答后的恢复仍是一次完整的从头重放（等价于 Web 应答后的 recover），worker 阻塞等待的架构约束不被破坏。

### 2. `loopflow respond <run-id>` 命令

新增 CLI 命令，对任何处于 `waiting_input`（或有 pending 请求的 `cancelled`）的 Run 执行与第 1 节相同的交互式问答 + 恢复，用于应答非前台产生的等待（WebUI 创建、后台执行、之前退出的前台 run）。Spec 的 CLI 模块能力清单已包含 `respond`，本决策使实现与 Spec 对齐。stdin 非 tty 时拒绝交互并提示使用 Web API。

### 3. `intervene()` 支持 default 与 timeout

```python
intervene(key, prompt, schema=None, *, options=None, allow_custom=True,
          default=None, timeout=None)
```

| 参数 | 约束 | 语义 |
|------|------|------|
| `default` | 必须在调用时通过 options/allow_custom/schema 校验，否则 `ValueError` | 无人值守或超时时的兜底回答 |
| `timeout` | 秒数；仅在声明 `default` 时有效，否则 `ValueError` | 请求创建后超过该时长未获人工回答，取 `default` 继续 |

**timeout 采用惰性求值**，与"等待期无存活进程"的架构一致：

- 重放/恢复到达一个 pending 请求时，若 `created_at + timeout` 已过且声明了 `default`，自动以 `default` 回答并返回，无需任何守护进程或定时器；
- CLI 前台内联提问时 timeout 即时生效（倒计时，超时取 `default`）；
- WebUI 可据 `created_at + timeout` 展示倒计时，本期不做服务端自动触发。

`default`/`timeout` 参与请求的一致性校验：重放时与已持久化请求比对（同 key/prompt/schema  digest 的现有机制），变更按 `replay_diverged` 处理。

已回答请求记录 `response_source`：`human`（人工应答）/ `default`（无人值守兜底）/ `timeout_default`（惰性超时兜底），事件仍复用 `intervention_responded`，读模型不变。

### 4. `--unattended` 无人值守模式

`loopflow run --unattended` 将 `unattended` 冻结进 Run 的执行选项（与 ADR 0036 的执行选项冻结规则一致，recover 继承，WebUI 创建入口本期不暴露）。无人值守执行中遇到 intervention 请求：

- 声明了 `default` → 直接以 `default` 回答并继续（`response_source=default`），Run 不进入 `waiting_input`；
- 未声明 `default` → Run 以 `intervention_unattended` 失败（明确错误，不挂起、不空等）。

前台 stdin 非 tty 且未声明 `--unattended` 时保持现有语义但改善提示：打印 pending 请求数、run_id、`loopflow respond <run-id>` 与 WebUI 应答入口后以 `waiting_input` 退出——不隐式套用无人值守策略，是否失败由调用方显式声明。

### 5. 范围边界

本期只扩展 workflow 侧 `intervene()`。Agent 结构化请求（`resume_mode=continue`）的 default/timeout 声明依赖 agent 侧协议的可发现性设计（BL-046），待其方向裁决后再议。CLI 内联提问的首期目标平台为 POSIX tty（timeout 用 stdlib `select` 实现）；其他平台回退到第 4 节的指引输出。

## Alternatives

### CLI 只打印应答指引，不做内联提问

实现最小，但前台用户仍要切换到另一个工具（WebUI 或另一条命令）完成一次问答，"run 卡死"的第一印象没有消除。stdin 在前台执行期间完全空闲，内联提问的成本可控。

### 服务端定时器实现 timeout

由常驻 server 扫描到期请求并自动应答 + 恢复。能覆盖"无人值守的长时间等待"，但引入新的后台调度组件，且 CLI 纯前台场景（无常驻 server）仍需惰性求值兜底。惰性求值以零常驻成本覆盖全部恢复路径，定时器留待真实需求出现。

### timeout 无 default 时让请求过期失败

"超时即失败"看似完备，但 BL-045 的原始需求是"不要空等、拿兜底值继续"；无兜底的超时失败等价于 `intervention_unattended`，已由 `--unattended` 表达，不引入第三种过期语义。

### agent 侧请求一并支持 default/timeout

agent 控制结果协议当前对 agent 不可见（BL-046），在其方向（正式化 vs 移除）裁决前扩展该协议会放大沉没成本。

## Consequences

### Positive

- 前台 CLI 用户无需离开终端即可完成人工门，"卡死"误解消除。
- headless 环境有确定行为：有 default 拿兜底继续，无 default 明确失败，都不再空等。
- timeout 惰性求值不引入任何常驻组件，与 ADR 0036 的进程退出模型自洽。
- `loopflow respond` 补齐 Spec 已声明的 CLI 能力。

### Negative

- CLI 内联应答是 presentation 层的第二个应答入口，需与 Web handler 严格共用应用层校验与恢复路径，否则行为漂移。
- timeout 在纯后台且无恢复触发的场景下不会"主动"生效——语义是"下次重放时生效"，需在文档与 WebUI 文案中明确。
- `response_source` 与 `default/timeout` 扩展了 intervention 数据模型，旧文件读取需兼容缺省。

## Architecture Boundary

本 ADR 扩展 ADR 0036 §5 的 intervention 模型（不替代）。约束 CLI presentation（内联提问、respond 命令、指引输出）、`runtime.intervene()` 签名与校验、intervention 持久化（新字段与惰性超时求值）、应用层 recover 命令复用。Presentation 不得自行实现应答校验、绕过 `answer_requests()` 写盘，或为 timeout 引入常驻调度。

## Verification

不需要外部技术选型 spike（无新依赖；stdin 超时使用 stdlib `select`，POSIX 为既有支持平台）。进入 TEST_INFRA 后通过 CLI 集成测试（tty 模拟）、intervention 持久化契约测试与恢复语义测试验证；场景以 AC-0011 新增场景为准。
