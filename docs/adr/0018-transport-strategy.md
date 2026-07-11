---
title: Transport Strategy — CLI-first, ACP opt-in
description: 禁用 ACP auto-detection，所有后端默认走 CLI 传输，ACP 仅在显式指定时启用
type: adr
status: accepted
created: 2026-07-11T13:00:00Z
---

# ADR 0018: Transport Strategy — CLI-first, ACP opt-in

## 动机

当前 5 个后端（kimi、opencode、qwen、gemini、kiro）在初始化时自动检测 ACP 可用性（`check_acp()`），如果可用则优先走 ACP 协议。压力测试中发现 ACP 模式存在死锁：

1. kimi 的 ACP 模式下，agent 发出 `Skill` tool call 后等待 client（loopflow）授权
2. `AcpBackend` 不处理 tool call 通知，导致 kimi 永久等待
3. `session/prompt` 调用阻塞，loopflow 也跟着卡死

根本原因是 ACP 协议要求 client 参与 tool call 授权/响应，但 loopflow 的 ACP 对接不完整。

## 决策

### 所有后端默认走 CLI 传输

```python
# 之前：自动检测 ACP，可用则优先
use_acp = transport == "acp" or (transport is None and check_acp("kimi"))

# 之后：仅显式指定时才走 ACP
use_acp = transport == "acp"
```

ACP 仅在调用方显式传入 `transport="acp"` 时启用。

### 适用范围

kimi、opencode、qwen、gemini、kiro —— 5 个同时支持 ACP 和 CLI 的后端。claude、codex、pi 本身只走 CLI，不受影响。

### 不删除 ACP 代码

`AcpBackend`、`AcpTransport`、`check_acp()` 等 ACP 基础设施保留，待未来引入标准 ACP client 库后重新启用。

## 备选方案

### 方案 A: 禁用 ACP auto-detection（推荐）

- 优点：最小改动（每后端改 1 行）；ACP 代码保留，未来可恢复；CLI 模式已充分验证
- 缺点：ACP 的功能优势（session 管理、resume 复用）暂时不可用

### 方案 B: 完善 ACP tool call 处理

- 优点：保留 ACP 的全部功能
- 缺点：工作量大，需要对接各后端不同的 tool call 机制；ACP 协议尚无标准 client 库，自研维护成本高

### 方案 C: 完全删除 ACP 代码

- 优点：减少代码量，降低维护负担
- 缺点：未来重新引入时需从零编写；删除动作不可逆

## 选择理由

1. 当前 ACP 对接不完整，CLI 模式已覆盖所有后端的核心功能（`-p` 一次性执行）
2. 最小改动，零风险
3. ACP 代码保留，ADR 中记录决策，未来引入标准库时可参考

## 后果

### 正面

- 消除 ACP tool call 死锁问题
- CLI 模式更透明（stderr 直接可见）
- 减少自动检测的启动开销

### 负面

- ACP 的 session 复用、增量消息等高级功能暂时不可用
- 未来需手动恢复 ACP 支持

### 未来恢复条件

当以下条件满足时，可新增 ADR 撤销本决策：
1. 有成熟的 ACP client 库（标准 JSON-RPC + tool call 处理）
2. loopflow 完成 tool call 授权/响应机制
3. 通过压力测试验证无死锁

## 约束范围

`src/loopflow/backends/kimi.py`、`opencode.py`、`qwen.py`、`gemini.py`、`kiro.py`。约束了这些模块的传输协议选择策略。

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | 后端默认走 CLI，ACP 仅显式启用 | backends/ | 代码审查：`use_acp` 表达式不含 `check_acp()` |
| AR-002 | `check_acp()` 和 ACP 基础设施保留不删除 | backends/ transports/ | 代码审查 |