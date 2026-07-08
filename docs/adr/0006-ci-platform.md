---
title: ADR-0006
description: CI 平台选型：GitHub Actions
type: adr
status: accepted
created: 2026-07-07T12:00:00Z
---

# ADR-0006: CI 平台选型

---

## 背景

loopflow 需要 CI 流水线来运行测试、检查覆盖率、执行 MR 门禁。项目托管在 GitHub。

---

## 决策内容

使用 **GitHub Actions** 作为 CI 平台。单 workflow 文件覆盖：测试 + 覆盖率 + MR 门禁。

---

## 备选方案

### 方案 A: GitHub Actions（推荐）

- 优点：与 GitHub 深度集成，免费额度足够，社区生态成熟，setup-python 官方 action 可用
- 缺点：仅限 GitHub 平台

### 方案 B: GitLab CI / Drone CI / 其他

- 优点：跨平台
- 缺点：项目在 GitHub 上，无需额外配置外部 CI

---

## 选择理由

1. 项目托管在 GitHub，GitHub Actions 零配置成本
2. 免费额度对开源项目充足
3. 官方 `actions/setup-python` + `uv` 支持完善

---

## 验证

无需验证（约定/标准类 ADR）。

---

## 后果

### 正面

- CI 配置简单，一个 YAML 文件
- 与 GitHub PR/MR 流程无缝集成

### 负面

- 平台锁定（GitHub），但迁移成本低（CI 配置可移植）

---

## 约束范围

`.github/workflows/` 目录。约束了 CI 平台和 workflow 结构。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | CI 每次 push 和 PR 触发 | .github/workflows/ | CI 未触发则报错 |
| AR-002 | CI 必须运行在 Python 3.10+ | .github/workflows/ | CI 配置检查 |
| AR-003 | MR 门禁必须包含：单元测试 + 集成测试 + 覆盖率 | .github/workflows/ | CI 配置检查 |