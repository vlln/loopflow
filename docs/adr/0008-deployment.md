---
title: ADR-0008
description: 部署策略：本地型发布（release → main + tag + wheel 构建冒烟）；PyPI 路径保留为备选
type: adr
status: proposed
created: 2026-07-07T12:00:00Z
---

# ADR-0008: 部署策略

> 2026-08-03：修订为**本地型发布**。历史所有版本（0.24~0.27）实际均按本地型发布（release/* 分支 → 合并 main + 打 tag），无 PyPI publish 配置或执行记录；且 PyPI 上 `loopflow` 已被他人占用。原决策保留为备选方案（见「备选方案」）。

---

## 背景

loopflow 是 CLI 工具，需要确定用户安装方式和开发者发布流程。

---

## 决策内容

**本地型发布**：以 `release/*` 分支 → 合并 `main` + 打 tag 为发布锚点（tag 即版本归档）。发布门禁验证 `uv build` 产物可构建、wheel 可真实起服（见「验证」段）；部署目标从本地 editable 安装（`pip install --user -e .`）。

**PyPI 发布不再作为当前执行路径**：PyPI 上 `loopflow` 包名已被他人占用，且本仓库无 PyPI publish 配置、token 或执行记录。若未来需要公共分发，先解决包名问题再评估（见备选方案 A）。

---

## 备选方案

### 方案 A: PyPI 发布（备选，当前不执行）

- 优点：Python 生态标准，uv/pip 原生支持，`uv tool install` 提供隔离环境
- 缺点：需要维护 PyPI 账号和 token；**`loopflow` 包名已被他人占用**，需先解决包名问题；0.24~0.27 从未执行过该路径，链路未验证

### 方案 B: 本地型发布（当前决策）

- 优点：与既有 0.24~0.27 实际流程一致（release/* → main + tag），无外部账号依赖
- 缺点：公共可发现性弱，无公共分发渠道（仓库未发布 GitHub Releases）；外部用户需自行构建或联系维护者

### 方案 C: Homebrew

- 优点：macOS 用户友好
- 缺点：仅限 macOS，需要额外维护 formula，比 PyPI 复杂

---

## 选择理由

1. 与实际发布流程一致：0.24~0.27 全部按本地型发布，修订使 ADR 反映现实，避免文档与执行脱节（BL-056）
2. `loopflow` 包名在 PyPI 被占用，公共分发路径当前不可行
3. 本地型发布链路已在 0.24~0.27 的 RELEASE 阶段多次验证（tag + 构建 + 冒烟），风险最低

---

## 验证

无需独立 spike（约定/标准类 ADR，修订为与既有执行一致）。部署链路已在 0.24~0.27 的 RELEASE 阶段多次验证：`release/*` 合并 `main` + 打 tag + wheel 构建冒烟（`scripts/wheel-smoke.sh`、`scripts/verify-wheel-assets.py`，0.27.1 起含真实起服 curl 冒烟）。

---

## 后果

### 正面

- 发布流程与既有执行一致，无新账号/凭证依赖
- tag 即版本归档，可追溯、可回滚
- 版本号与 CHANGELOG 维护成本不变

### 负面

- 不提供 `pip install loopflow` 公共安装渠道，仓库也无 GitHub Releases 产物分发，外部用户需自行构建
- 若未来需要公共分发，需重新评估包名与 PyPI 流程（见备选方案 A）

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

## 修订记录

- 2026-08-03：决策从 PyPI 发布修订为本地型发布（BL-056，0.28.0 DESIGN）。依据：0.24~0.27 全部实际按本地型发布，无 PyPI publish 配置/执行记录；PyPI 上 `loopflow` 包名已被他人占用。PyPI 路径保留为备选方案 A，当前不执行。