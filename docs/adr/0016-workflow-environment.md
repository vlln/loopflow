---
title: Workflow Environment Declaration — conda environment file as lightweight dependency contract
description: meta.requires.environment 声明环境文件路径，松散校验（存在性），不强制激活。先 workflow 级，与 isolation 形成隔离层级体系
type: adr
status: accepted
created: 2026-07-10T11:00:00Z
---

# ADR 0016: Workflow Environment Declaration

## 动机

当前 workflow 对环境依赖无框架支持。bio-reproducer 使用 Bootstrap agent 手动检查 Java/Nextflow/Docker，结果写入 `bootstrap.md`。每个 workflow 作者重复造轮子。

需要一种声明式机制，让 workflow 表达"我需要什么环境"，同时保持轻量——不强制安装，不构建容器。

## 决策

### 1. 声明位置：`meta.requires.environment`

```python
meta = {
    "name": "bio-reproducer",
    "requires": {
        "environment": "environment.yml",   # 相对路径，指向 workflow 目录下
    },
}
```

`environment` 指向环境文件，格式通常是 `environment.yml`（conda）或 `Dockerfile`（容器，未来扩展）。loopflow 不解析文件内容，只校验文件存在。

### 2. 松散校验：声明存在，不强制激活

- `loop run` 启动时检查 `environment` 指向的文件是否存在
- 存在 → 通过，记录日志
- 不存在 → 报错退出
- **不执行** `conda env create` 或 `conda activate`
- 环境激活由 agent 或用户完成

**理由**：
- 环境激活可能涉及网络下载（conda create），耗时不确定
- 不同平台激活方式不同（conda vs mamba vs micromamba）
- loopflow 保持 orchestrator 定位，不管理环境生命周期

### 3. 作用域：先 workflow 级

当前设计为 workflow 级声明——一个 environment.yml 覆盖所有 agent。如果未来某个 agent 需要独立环境，可以在 agent 的 `requires` 中扩展：

```yaml
# 未来设计（不做）
---
name: run
requires:
  environment: run-env.yml    # agent 级覆盖
---
```

### 4. 与 isolation 的关系

环境声明是隔离层级体系的一部分：

```
声明层（本 ADR）：
  meta.requires.environment → 环境文件存在性校验

执行层（现有）：
  isolation="worktree"      → 文件系统隔离（git worktree）

未来层：
  isolation="conda"         → 自动激活 conda 环境
  isolation="container"     → Docker/Singularity 容器隔离
```

声明层和执行层是互补的——声明回答"需要什么"，执行回答"如何隔离"。

### 5. 当前不做的事

- **不自动激活环境**：`loop run` 不调用 conda
- **不解析环境文件内容**：不检查 java 版本、nextflow 版本
- **不安装依赖**：不执行 `conda env create`
- **不做 agent 级环境声明**：`requires.environment` 仅在 workflow 级

## 影响

- `cli.py`：`run()` 启动时读取 `meta.requires.environment`，检查文件存在
- `discovery.py`：`load_loop()` 返回的 meta 已包含 `requires` 字段
- Workflow 作者：可在 workflow 目录下放置 `environment.yml`，`meta.requires.environment` 指向它

## 替代方案

**方案 B：程序列表声明。**
```python
meta = {"requires": {"programs": ["java", "nextflow"], "env": ["HOME"]}}
```
- 优点：更简单，不依赖外部文件
- 缺点：太模糊（版本不可知），无法校验（不知道用什么命令检查）
- 决策：不采用。环境文件更精确、可复现

**方案 C：严格校验 + 自动激活。**
- 优点：一键运行
- 缺点：loopflow 需要知道 conda 路径、管理 env 生命周期、处理跨平台差异
- 决策：不采用。偏离 orchestrator 定位，留给未来 `isolation="conda"`