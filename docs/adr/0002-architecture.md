---
title: ADR-0002
description: 架构模式：目录结构、模块划分、~/.loopflow/ 用户目录布局
type: adr
status: accepted
created: 2026-07-07T12:00:00Z
---

# ADR-0002: 架构模式与目录结构

---

## 背景

loopflow 有两个"目录"概念：程序源码目录和用户数据目录（`~/.loopflow/`）。需要定义两者的结构和模块边界，确保各模块职责清晰、可独立测试。

---

## 决策内容

**程序源码**采用扁平模块结构（非多层 package），每个模块一个文件。**用户数据**采用 `loops/`（定义）+ `runs/`（实例）两层结构。

---

## 备选方案

### 方案 A: 扁平模块 + 文件系统实例

```
src/loopflow/
├── cli.py              # 入口
├── runtime.py          # 编排运行时
├── registry.py         # 实例管理
├── lock.py             # 文件锁
├── display.py          # TUI
├── discovery.py        # loop 扫描
├── backends/           # 后端适配器
│   ├── base.py
│   ├── claude.py
│   └── ...
└── transports/
    ├── cli.py
    └── acp.py

~/.loopflow/
├── loops/              # 定义
│   └── <name>/
│       ├── workflow.py
│       └── agents/
└── runs/               # 实例
    └── <run-id>/
        ├── run.json
        └── <seq>.jsonl
```

- 优点：简单，模块边界清晰，subagent-skills 后端代码可直接复制
- 缺点：模块多时文件数量增长

### 方案 B: 多层 package 结构

```
src/loopflow/
├── cli/
│   ├── __init__.py
│   ├── run.py
│   ├── resume.py
│   └── ...
├── core/
│   ├── runtime.py
│   └── registry.py
└── ...
```

- 优点：按功能分组，大规模项目更易管理
- 缺点：过度设计，loopflow 代码量不足以支撑多层结构

---

## 选择理由

1. subagent-skills 已验证扁平结构在 ~2000 行级别项目中足够清晰
2. 每个模块文件 200-500 行，职责单一，无需嵌套
3. `~/.loopflow/` 布局与 Claude Code 的 `~/.claude/` 风格一致，用户熟悉

---

## 验证

无需验证（约定/标准类 ADR）。

---

## 后果

### 正面

- 源码结构简单，新人可快速定位
- 用户数据目录清晰：loops = 模板，runs = 实例

### 负面

- 如果未来模块数超过 15 个，扁平结构需要重构为 package

---

## 约束范围

全部模块。约束了源码目录结构、用户数据目录布局、模块间引用方式。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | 源码模块为单文件，非 package | src/loopflow/ | 检查 `__init__.py` 不存在（除 backends/transports 外） |
| AR-002 | ~/.loopflow/loops/ 下每个目录是一个 loop 定义 | 用户数据 | loop discovery 扫描时检查 |
| AR-003 | ~/.loopflow/runs/<run-id>/ 下 run.json 必须存在 | 运行实例 | registry 创建实例时保证 |
| AR-004 | 模块间禁止循环引用 | src/loopflow/ | import 分析 |