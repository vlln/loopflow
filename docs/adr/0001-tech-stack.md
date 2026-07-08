---
title: ADR-0001
description: 技术栈选型：Python 3.10+，uv 管理项目，最小运行时依赖（pyyaml/click/rich）
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

使用 **Python 3.10+**，**uv** 管理项目和依赖，**最小运行时依赖**（pyyaml、click、rich），**pytest** 作为开发依赖。通过 `pyproject.toml` 标准 Python 项目管理。

---

## 备选方案

### 方案 A: Python 3.10+，零依赖

- 优点：零安装成本，无依赖冲突风险
- 缺点：YAML frontmatter 需手写解析器（~100 行，易出 bug），CLI 需手写 argparse 子命令路由（~200 行），TUI 需手写 ANSI（~300 行，subagent-skills 的 progress 渲染器有已知 bug）

### 方案 B: Python + uv + pyyaml/click/rich（推荐）

- 优点：YAML 解析健壮（pyyaml），CLI 清晰自动 help（click），TUI 可维护（rich），uv 管理依赖快速可靠，pyproject.toml 标准工程化
- 缺点：引入 3 个运行时依赖 + 1 个开发依赖，安装需要 `uv sync` 或 `pip install`

### 方案 C: Node.js / TypeScript

- 优点：与 Claude Code Workflow 生态一致
- 缺点：无法复用 subagent-skills 的全部后端代码，需重写 8 个后端适配器

---

## 选择理由

1. subagent-skills 已有 8 个后端适配器（~2000 行 Python），方案 B 零成本复用
2. loopflow 是独立工具（非 skill），用户通过 `pip install` 或 `uv tool install` 安装是标准期望
3. pyyaml/click/rich 是 Python 生态的事实标准，稳定、轻量、维护成本为零
4. uv 是当前最快的 Python 包管理器，pyproject.toml 是 PEP 标准
5. 3 个运行时依赖 + 1 个开发依赖，总量可控，不引入重量级框架

---

## 验证

| 验证项 | 复现步骤 | 结论 | 经验 | 验证 Branch |
|--------|---------|------|------|------------|
| uv + pyproject.toml 初始化 | `uv init loopflow`，添加 pyyaml/click/rich/pytest 依赖，`uv run python -c "import yaml, click, rich"` | 待验证 | — | spike/0001-tech-stack |
| subagent-skills 后端代码可导入 | 复制 backends/ 到 src/loopflow/，`uv run python -c "from loopflow.backends import kimi"` | 待验证 | — | spike/0001-tech-stack |

---

## 后果

### 正面

- 标准 Python 项目工程化（pyproject.toml + uv），社区熟悉
- pyyaml/click/rich 健壮且零维护成本
- 与 subagent-skills 后端代码完全兼容

### 负面

- 非零安装成本（需 `uv sync` 或 `pip install`）
- 3 个运行时依赖需要关注安全更新

---

## 约束范围

全部模块。约束了整个项目的语言选择、依赖策略、安装方式。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | 使用 uv 管理依赖，pyproject.toml 声明所有依赖 | 全部源码 | CI 检查 pyproject.toml 存在且 [project] 段完整 |
| AR-002 | 代码必须在 Python 3.10 上运行 | 全部源码 | CI 运行 3.10 版本 |
| AR-003 | 运行时依赖仅限 pyyaml、click、rich | 全部源码 | pyproject.toml dependencies 审查 |
| AR-004 | 开发依赖仅限 pytest | 全部源码 | pyproject.toml dev-dependencies 审查 |