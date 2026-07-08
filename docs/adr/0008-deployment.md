---
title: ADR-0008
description: 部署策略：PyPI 发布，uv tool install 安装
type: adr
status: proposed
created: 2026-07-07T12:00:00Z
---

# ADR-0008: 部署策略

---

## 背景

loopflow 是 CLI 工具，需要确定用户安装方式和开发者发布流程。

---

## 决策内容

发布到 **PyPI**，用户通过 `uv tool install loopflow` 或 `pip install loopflow` 安装。使用 **uv** 构建和发布。

---

## 备选方案

### 方案 A: PyPI 发布（推荐）

- 优点：Python 生态标准，uv/pip 原生支持，`uv tool install` 提供隔离环境
- 缺点：需要维护 PyPI 账号和 token

### 方案 B: 仅 GitHub Releases

- 优点：简单，与源码托管一致
- 缺点：用户需手动下载和配置 PATH，不符合 Python CLI 工具惯例

### 方案 C: Homebrew

- 优点：macOS 用户友好
- 缺点：仅限 macOS，需要额外维护 formula，比 PyPI 复杂

---

## 选择理由

1. `uv tool install` 提供隔离环境，是 Python CLI 工具的推荐安装方式
2. PyPI 是 Python 包分发的唯一标准渠道
3. 与 pyproject.toml 工程化一致

---

## 验证

无需验证（约定/标准类 ADR）。部署链路在 RELEASE 阶段验证。

---

## 后果

### 正面

- 标准 Python 包分发，用户安装简单
- uv 构建和发布流程成熟

### 负面

- 需要 PyPI 账号和 token 管理
- 发布前需要版本号和 CHANGELOG 维护

---

## 约束范围

`pyproject.toml` 的 `[project]` 段。约束了安装方式和发布流程。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | pyproject.toml 的 [project] 段完整（name/version/requires-python/dependencies） | pyproject.toml | CI 检查 |
| AR-002 | `uv build` 可成功构建 | pyproject.toml | CI 构建步骤 |
| AR-003 | 发布前 CHANGELOG 已更新 | CHANGELOG.md | RELEASE gate 检查 |