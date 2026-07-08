---
title: ADR-0001
description: 技术栈选型：Python 3.10+，零外部依赖，仅标准库
type: adr
status: proposed
created: 2026-07-07T12:00:00Z
---

# ADR-0001: 技术栈选型

---

## 背景

loopflow 需要选择编程语言和运行时。核心约束：复用 subagent-skills 的现有后端适配层（Python 实现），CLI 工具形态，需要跨平台（macOS/Linux）。

---

## 决策内容

使用 **Python 3.10+**，**零外部依赖**（仅标准库）。不引入任何 pip 包。

---

## 备选方案

### 方案 A: Python 3.10+，零依赖

- 优点：安装成本为零（系统自带 Python），subagent-skills 后端代码可直接复用，无依赖冲突风险
- 缺点：部分功能需手写（如 YAML frontmatter 解析），并发能力受限于 threading

### 方案 B: Python + rich/click/pyyaml

- 优点：TUI 效果更好（rich），CLI 更规范（click），YAML 解析更健壮（pyyaml）
- 缺点：引入依赖管理负担，安装门槛提高，与 subagent-skills 零依赖哲学不一致

### 方案 C: Node.js / TypeScript

- 优点：与 Claude Code Workflow 生态一致
- 缺点：无法复用 subagent-skills 的全部后端代码，需重写 8 个后端适配器

---

## 选择理由

1. subagent-skills 已有 8 个后端适配器（~2000 行 Python），方案 A 零成本复用
2. 零依赖意味着 `python3` 即可运行，无安装步骤
3. YAML frontmatter 解析可手写（仅需解析 `key: value` 和列表，不需要完整 YAML 1.2 规范）
4. TUI 可通过 ANSI escape codes 手写，subagent-skills 已有可用的 progress 渲染器

---

## 验证

| 验证项 | 复现步骤 | 结论 | 经验 | 验证 Branch |
|--------|---------|------|------|------------|
| 标准库 YAML 解析足够 | 编写 agent 定义文件的 frontmatter 解析器，测试 name/description/requires 字段提取 | 可行 | 仅需解析简单 KV 对和字符串列表，无需完整 YAML 库 | spike/0001-tech-stack |
| ANSI TUI 可行 | 运行 subagent-skills 的 progress 渲染器 demo | 可行 | subagent-skills 已实现 braille 进度条、TTY 树形渲染，可直接复用 | spike/0001-tech-stack |

---

## 后果

### 正面

- 零安装成本，`git clone` 后即用
- 与 subagent-skills 代码完全兼容，复制粘贴即可
- 无外部依赖冲突，用户环境兼容性最大化

### 负面

- TUI 手写维护成本高于使用 rich
- 需自行处理 Python 版本兼容性（3.10 的 match/case 语法 → 可选使用 3.10 特性，保持 3.9 兼容）

---

## 约束范围

全部模块。约束了整个项目的语言选择、依赖策略、安装方式。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | 禁止引入任何 pip 外部依赖 | 全部源码 | CI 检查 `pip list` 或 import 分析 |
| AR-002 | 代码必须在 Python 3.10 上运行 | 全部源码 | CI 运行 3.10 版本 |
| AR-003 | 所有 import 必须来自标准库或项目内部 | 全部源码 | lint 规则检查 |