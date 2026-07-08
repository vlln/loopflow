---
title: ADR-0005
description: 测试框架选型：pytest + coverage.py
type: adr
status: proposed
created: 2026-07-07T12:00:00Z
---

# ADR-0005: 测试框架选型

---

## 背景

loopflow 需要单元测试和集成测试框架。ADR-0001 已确定 pytest 为开发依赖，本 ADR 细化测试分层和目录结构。

---

## 决策内容

使用 **pytest** 作为唯一测试框架，**coverage.py** 采集覆盖率。三层测试结构：

```
tests/
├── unit/              # 单元测试（纯函数，无外部依赖）
├── integration/       # 集成测试（需 mock backend）
└── conftest.py        # 共享 fixtures
```

---

## 备选方案

### 方案 A: pytest + coverage.py（推荐）

- 优点：Python 生态标准，社区成熟，零学习成本，与 ADR-0001 一致
- 缺点：无

### 方案 B: unittest + coverage.py

- 优点：标准库，零额外依赖
- 缺点：编写繁琐，缺少 fixture/parametrize 等特性，pytest 已是 dev 依赖

---

## 选择理由

1. pytest 已是 ADR-0001 确定的开发依赖
2. 与 subagent-skills 测试结构一致，降低迁移成本
3. coverage.py 是 Python 覆盖率采集的事实标准

---

## 验证

无需验证（约定/标准类 ADR）。

---

## 后果

### 正面

- 测试框架统一，配置简单
- 与 subagent-skills 测试结构兼容

### 负面

- 无

---

## 约束范围

全部测试代码。约束了测试框架、测试目录结构、覆盖率工具。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | 所有测试使用 pytest 编写 | tests/ | CI 检查测试框架 |
| AR-002 | 单元测试放在 tests/unit/，集成测试放在 tests/integration/ | tests/ | 目录结构检查 |
| AR-003 | 覆盖率目标 ≥ 80% | 全部源码 | CI coverage 检查 |
| AR-004 | 测试文件命名：test_<模块名>.py | tests/ | 目录结构检查 |