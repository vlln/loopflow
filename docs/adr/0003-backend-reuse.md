---
title: ADR-0003
description: 后端复用策略：从 subagent-skills 复制代码 vs pip 包依赖
type: adr
status: accepted
created: 2026-07-07T12:00:00Z
---

# ADR-0003: 后端代码复用策略

---

## 背景

loopflow 需要调用 8 种 AI Agent 后端（kimi/claude/codex/pi/opencode/qwen/kiro/gemini）。subagent-skills 已有完整的后端适配层实现（`backends/` + `transports/` + `registry.py` + `lock.py`）。需要决定复用方式。

---

## 决策内容

**从 subagent-skills 复制代码**到 loopflow 的 `src/loopflow/` 下，然后**大幅重构**。不保留向后兼容性，不建立 pip 依赖。

---

## 备选方案

### 方案 A: 复制 + 重构（推荐）

- 优点：loopflow 独立演进，不受 subagent-skills 接口变更影响；可大幅简化（去掉 goal、swarm、send、cancel 等 loopflow 不需要的 CLI 命令）；无外部依赖
- 缺点：两套代码需分别维护 bug 修复；初期复制约 2000 行代码

### 方案 B: pip 包依赖

- 优点：共享 bug 修复，后端升级自动同步
- 缺点：subagent-skills 是 skill 不是 pip 包，需要额外打包；接口变更可能破坏 loopflow；引入外部依赖违背 ADR-0001

### 方案 C: Git submodule

- 优点：版本锁定，可追溯
- 缺点：用户体验差（需要 `--recursive` clone），增加安装复杂度

---

## 选择理由

1. 与 ADR-0001（最小依赖）一致——复制代码不引入额外运行时依赖
2. loopflow 和 subagent-skills 的演进方向不同：loopflow 面向循环编排，subagent-skills 面向一次性任务分发
3. 复制时可大幅精简：移除 goal、swarm、send、cancel、queue_worker 等 loopflow 不需要的功能
4. subagent-skills 的后端层本身设计为独立模块（`base.py` 抽象 + 各后端实现），复制后接口不变

---

## 验证

| 验证项 | 复现步骤 | 结论 | 经验 | 验证 Branch |
|--------|---------|------|------|------------|
| 后端代码可独立运行 | 复制 subagent-skills 的 backends/ 到独立目录，mock 调用 kimi backend | 可行 | 后端层与 CLI 层解耦，copy 后 import 路径调整即可 | spike/0003-backend-reuse |
| 可精简 | 统计 loopflow 需要的后端 API：create_session/resume_session/close，移除其他方法 | 可行 | 约 40% 代码可移除（goal/swarm/send/cancel 在 CLI 层，不在后端层） | spike/0003-backend-reuse |

---

## 后果

### 正面

- loopflow 完全独立，不受上游变更影响
- 可自由重构后端接口以适配 loopflow 的编排模型

### 负面

- subagent-skills 的后端 bug 修复需手动同步到 loopflow
- 初始复制工作量大（约 2000 行，但大部分不需要改动）

---

## 约束范围

`src/loopflow/backends/`、`src/loopflow/transports/`、`src/loopflow/registry.py`、`src/loopflow/lock.py`。约束了这些模块的来源和演进方式。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | 后端代码从 subagent-skills 复制，不禁用 pip 安装 | backends/ transports/ | CI 无 pip install 步骤 |
| AR-002 | 后端 `BaseBackend` 接口仅保留 create_session/resume_session/close | backends/ | 代码审查 |
| AR-003 | 移除 goal/swarm/send/cancel 相关 CLI 命令 | cli.py | 代码审查 |