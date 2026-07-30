---
title: Agent intervention 控制协议与 capability preflight
description: 正式化 Agent waiting_input 提示、业务 schema 联合类型、ACP capability preflight、请求分组与多 session continue
type: adr
status: accepted
created: 2026-07-29T11:24:49Z
---

# ADR 0057: Agent intervention 控制协议与 capability preflight

## Context

ADR-0036 和 AC-023 已允许 Agent 返回 `__loopflow.status=waiting_input`，但当前实现存在三个断点：

1. 协议没有注入 Agent prompt，Agent 无法发现；
2. 业务 output schema 先于控制结果处理，required 字段或 `additionalProperties=false` 会拒绝 waiting_input；
3. Agent request 只能通过原 session continue，动态 ACP transport 却在 initialize 前报告默认 capabilities，prompt 组装时无法可靠判断是否可用。

此外，现有 respond 路径只保留一个 continue target，无法正确恢复 parallel 中同时等待输入的多个 Agent session。BL-046 要求把这条路径从隐藏实现正式化，同时不允许能力不足时静默新建 session 重跑，因为 Agent 可能已经产生外部副作用。

## Decision

### 1. 在 marshalling 前显式准备 capabilities

Backend 增加幂等的 capability preparation 生命周期（实现名可为 `prepare_capabilities()`）：

- 静态 CLI backend 默认直接返回既有 `Capabilities`，不执行 I/O；
- 动态 ACP backend 只完成 transport start + initialize handshake，不创建 session、不发送业务 prompt；
- Runner 在组装 prompt 和有效 schema 前调用一次，后续 create/resume 复用已初始化 transport；
- preparation 失败按 backend unavailable 处理，不退回“未知能力但仍宣告 intervention”。

Agent intervention 可用条件由准备后的 `resume_session && durable_session_id` 派生，不新增与恢复能力重复的布尔字段。

### 2. 只向可安全续接的 Agent 暴露协议

能力满足时，在最终用户 prompt 中注入一个稳定、最小的 `<loopflow-intervention>` 段，说明：

- 仅在完成任务所必需的人类信息缺失时使用；
- 普通回答保持原业务格式；
- waiting_input 的精确 JSON 结构、key/options/allow_custom 约束；
- 不允许 default/timeout；回答将以 input_received 信封返回原 session。

能力不满足时不注入该段。若 Agent 因自带知识仍返回控制对象，框架以 `agent_intervention_not_supported` 失败，不创建 pending request，并给出 workflow `intervene()` / 更换 backend 的行动提示。Capabilities 只决定是否宣告协议；合法控制对象转为 pending 前还必须确认本次 Call 已取得非空 session_id，并已随 Call 缓存落盘。缺失或落盘失败同样立即返回 `agent_intervention_not_supported`，不得先让用户回答再于恢复时失败。

本 ADR 显式修订 ADR-0036 §5 的一项错误语义：Agent control 在能力或本次 durable session_id 不满足时，从 `continue_not_supported` 改为 `agent_intervention_not_supported`，因为失败发生在创建 intervention 前，而不是用户主动执行 recover continue。一般 failed/cancelled Run 的 `recover --mode continue` 仍使用 `continue_not_supported`。

### 3. 框架控制是业务输出的互斥联合类型

定义严格的 waiting_input control schema。业务 schema 存在时，有效 schema 是互斥联合：

1. 业务分支：原 schema，并禁止出现保留字段 `__loopflow`；
2. 控制分支：根对象只承载合法 `__loopflow` waiting_input 对象，不要求业务字段。

业务 schema 自己声明 `__loopflow` 时在 backend 调用前拒绝。解析后先识别并严格验证控制分支；正常结果才进入既有业务校验/coercion。goal 模式将“带 `__goal` 的正常业务结果”作为业务分支，控制分支保持独立并优先处理。

无业务 schema 时不强制所有正常输出改为 JSON；普通文本保持原样，只有可解析且严格匹配 control schema 的完整对象触发 intervention。

### 4. 持久化请求组与原始顺序

每个 Agent 控制输出生成稳定的 `request_group_id`；同组 requests 共享 group id，按数组位置写 `request_index=0..n-1`，并保留 call_id/session_id。组内 key 必须唯一。

Run 当前全部 pending requests 仍通过一个 batch 全有或全无地回答。恢复时按 request_group_id 分组、request_index 排序，每组构造自己的回答信封：

```json
{"__loopflow":{"status":"input_received","responses":[{"key":"scope","response":"扩大"}]}}
```

信封只发送给该组的 session_id，不包含 request_id、digest、文件路径或内部状态。

### 5. 一次重放支持多个 continue targets

恢复上下文从单个 target 扩展为以 call_id 为键的 continue target 集合。workflow 重放时：

- 前序已提交 Call 继续命中缓存；
- 到达 target Call 时校验 input_digest、session_id 与 capability，向对应 session 发送该组回答；
- parallel 中多个 target 各自恢复，不共享回答；
- execution 结束时任一 target 未到达即 `replay_diverged`，不得标记 done。

旧 Agent request 缺少 group/index 时按 Spec v18 的兼容规则派生稳定顺序，并把恢复证据标为 unverified，不改写原文件。

### 6. Agent 不拥有无人值守批准策略

Agent control schema 不接受 default/timeout。默认答案和自动继续属于 workflow/运行者策略，不能由正在请求批准的模型自行决定。`--unattended` 遇到 Agent request 时继续沿用明确失败语义；需要默认值的流程必须使用 workflow `intervene()`。

## Alternatives

### 对所有 Backend 无条件注入协议

Agent 容易在不支持 continue 的 backend 上进入无法恢复的等待，错误发生在用户回答之后，成本和困惑都更高。拒绝。

### 能力不足时新建 session 并附上回答重跑

无法保证新 session 具有提问前上下文，还可能重复文件写入、网络请求或其他副作用；这不是 continue 的等价降级。拒绝。

### 从自然语言问题推断 intervention

误报不可控，也无法稳定提取 options、key 和批量边界。继续遵守 ADR-0036 的结构化控制原则。

### 允许 Agent 声明 default/timeout

模型可自行构造自动批准路径，越过运行者策略边界。默认值继续只由 workflow `intervene()` 声明。

## Consequences

### Positive

- Agent 能在实际可恢复时发现协议，业务 schema/goal 模式不再阻断控制对象。
- 回答始终回到原 session，不以不等价重跑掩盖能力缺失。
- 请求顺序和并行 session 目标可持久化、可审计、可在进程重启后恢复。

### Negative

- Backend 生命周期增加 capability preparation；ACP 会更早启动子进程并执行 initialize。
- 恢复上下文从单 target 变为集合，parallel 重放和完成判定复杂度上升。
- 有效 schema 成为联合类型，mock auto、schema hint 和 validation 都必须识别框架控制分支。

## Architecture Boundary

本 ADR 扩展 ADR-0036 的 Agent intervention 与 ADR-0049 的动态 ACP capabilities，不改变 workflow `intervene()` 的 replay 模型。Domain marshalling 拥有提示和 schema 组合规则；Backend preparation 只提供可靠能力，不拼接协议；Application recovery 拥有多 target 调度；Infrastructure intervention 拥有请求组、顺序和回答信封。Presentation 不得自行构造恢复信封或绕过 batch validation。

## Verification

验证已于 2026-07-29 在保留分支 `spike/0105-agent-intervention-capabilities` 的 commit `6eb383f6fbeb22fbb21f5e08005ed837392976e1` 完成。环境使用 Python 3.14.6（项目约束为 Python 3.10+）、agent-client-protocol 0.11.0、jsonschema 4.26.0，均来自仓库 `uv.lock`。验证脚本为 `spikes/0105_agent_intervention_capabilities.py`，ACP fixture 复用 `tests/agent_support/mock_acp_server.py`。执行：

```bash
uv run python spikes/0105_agent_intervention_capabilities.py
```

| 命题 | 可判定通过标准 | 证据产物 |
|------|----------------|----------|
| ACP preflight | initialize 后 capabilities 反映 loadSession；session/new 计数仍为 0；随后 create 只新增一次 session 且 transport start/initialize 计数不增加；close 后子进程退出 | 脚本 stdout `ACP_PREFLIGHT PASS` + 计数 JSON |
| 联合 schema | business、goal complete、waiting_input 三个合法 fixture 均通过；缺业务字段的普通结果、含 `__loopflow` 的业务结果、重复 key/default/timeout 控制 fixture 均拒绝 | stdout `SCHEMA_UNION PASS` + fixture 计数 |
| 多 target 分组 | 两个 call_id、三个 request 打乱文件输入顺序后，输出两个 target；每组按 request_index 排序，信封不含另一组 key 或内部字段；missing target 检查失败 | stdout `MULTI_TARGET PASS` + target JSON |

实际执行 exit 0，stdout 摘要：

```text
ACP_PREFLIGHT PASS {"session_new": 1, "transport_start": 1}
SCHEMA_UNION PASS {"accepted": 3, "rejected": 5}
MULTI_TARGET PASS [{"call_id": "call-a", ...}, {"call_id": "call-b", ...}]
```

结论：**可行**。initialize 可在不创建 session 的前提下发现 `loadSession`，后续 create 复用同一 transport；业务/goal/control 联合类型的合法与非法边界可判定；多个 Call group 可生成顺序稳定且相互隔离的回答信封，并能拒绝缺失 continue target。脚本任一断言失败均 exit 1。
