---
title: AC 0003 — Agent 层抽象
description: Agent 类封装 Backend + Capabilities，能力 marshalling 遵循"尽力而为"原则，runtime.py 的 agent() 简化为薄封装
type: ac
status: active
created: 2026-07-13T00:00:00Z
---

# AC 0003: Agent 层抽象

## AC-001: Agent 类基本功能

**描述**：`Agent` 类封装 `AgentDef`，提供 `call()` 方法。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-N-1 | Agent 创建并调用 | `ad = parse_agent(...)`; `agent = Agent(ad)`; `agent.call("task", backend)` | 返回 agent 执行结果，行为与当前 `agent()` 一致 |
| AC-001-N-2 | 无 agent_def 时 | `Agent(None).call("task", backend)` | 直接调用 backend，无额外能力注入 |
| AC-001-N-3 | Agent 携带 skills | ad 声明 `skills: [paperutils]`，backend 不支持 native skill | skills 文本注入到 system prompt |

### 边界场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-B-1 | 空 skills 列表 | `skills: []` | 不注入任何 skill 内容 |
| AC-001-B-2 | 无 output schema | ad 无 `output` 字段 | 不注入 schema hint，返回原始文本 |

### 失败场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-001-F-1 | Skill 文件不存在 | ad 声明 `skills: [nonexistent]` | 抛 RuntimeError（与当前行为一致） |

---

## AC-002: 能力 Marshalling 尽力而为

**描述**：每种能力检查 backend 支持度，选择最优路径。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-002-N-1 | Goal 原生支持 | backend 支持 native goal | 注入 `/goal ...` 到 prompt，单次调用 |
| AC-002-N-2 | Goal 降级 | backend 不支持 native goal | loopflow goal 循环，`__goal` schema wrapper |
| AC-002-N-3 | Schema 原生支持 | backend 支持 structured output | 传 schema 给 backend，不注入文本 hint |
| AC-002-N-4 | Schema 降级 | backend 不支持 structured output | 注入 schema hint 文本到 prompt |

---

## AC-003: runtime.py 简化

**描述**：`runtime.agent()` 变成 `Agent` 类的薄封装。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-003-N-1 | agent() 调用等价 | 任意参数组合 | 行为与重构前完全一致 |
| AC-003-N-2 | agent() 函数签名不变 | 现有 workflow 代码 | 所有现有 workflow 无需修改 |

---

## AC-004: 向后兼容

**描述**：重构不破坏现有功能。

### 正常场景

| 编号 | 场景 | 前置条件 | 预期结果 |
|------|------|---------|---------|
| AC-004-N-1 | 全量测试通过 | 195 tests | 全部 pass |
| AC-004-N-2 | Goal mode 功能不变 | loopflow goal + native goal | 均正常工作 |
| AC-004-N-3 | Skills 功能不变 | 声明 skills 的 agent | 注入行为不变 |

---

# AC-030: ACP 后端 loop 端到端

验证 ACP 后端通过官方 Python SDK 承载 loop 端到端运行，含 streaming 事件映射、permission auto-approve 和 continue 能力门控。对应 Spec v16 BR-054~057、ADR-0049。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-030-N-1 | 环境装了 agent-client-protocol（extra acp），pi-acp 可用 | `loopflow run <简单 loop> --backend pi --transport acp` | run 正常完成（done），events.jsonl 含 agent_start→agent_session→agent_message→agent_done(exit_code=0) | 自动化 |
| AC-030-N-2 | ACP 后端 session/update 发 thought/tool_call/usage 多类通知 | 同上运行 | events.jsonl 对应映射出 thought/tool_call/usage 事件，无通知类型被静默丢弃 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-030-B-1 | ACP 后端发 request_permission | 同上运行 | auto-approve-all 放行，不阻塞、不死锁，run 继续 | 自动化 |
| AC-030-B-2 | 未安装 agent-client-protocol extra | `loopflow run <loop> --transport acp` | 报错退出，stderr 提示安装 extra（如 `pip install loopflow[acp]`），不 crash | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-030-E-1 | ACP 后端进程启动失败或 initialize 超时 | 同上运行 | run failed，error_summary 含后端不可用信息 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-030-F-1 | failed 的 ACP run，后端声明 loadSession/resume | `loopflow recover --mode continue` | session/load 续接成功，run 恢复继续；后端不声明时返回 continue_not_supported | 自动化 |