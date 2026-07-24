---
title: Hotfix 0.20.1 Plan
description: 修复 v0.20.0 三个产品级缺陷：recover mock 失效、启动信号窗口过短、forkserver 环境陈旧
type: plan
status: done
created: 2026-07-24T08:30:00Z
---

# Goal

从 `main` 拉 `hotfix/0.20.1`，cherry-pick 已在 develop 验证的三个修复，打 v0.20.1 补丁 tag，合并回 `main` + `develop`。

# Inputs

- 修复提交（develop，CI 5/5 全绿 + macOS/Docker Linux 双平台 410 passed）：
  - `60ba63a` fix(execution)：mock 移到 frozen execution_options 合并后应用；启动信号窗口 2s→15s；默认 spawn
  - `6898991` test(infra)：test_smoke 兼容 Python 3.10（tomllib 为 3.11+）
  - `ce066eb` test(infra)：补齐 web profile AC manifest（CI 门禁需要）
- 复现证据：`env PATH=/usr/bin:/bin` 下 recover mock run 复现 sys.exit(1)（修复后通过）

# Steps

1. cherry-pick 三个提交到 hotfix/0.20.1
2. 版本号 0.20.0 → 0.20.1（pyproject + `__init__.py`）+ CHANGELOG 0.20.1 条目
3. 全量回归（pytest 410、前端 36、e2e）
4. 合并 main + tag v0.20.1 + 合并回 develop + push

# Exit

v0.20.1 tag 在 main，hotfix 合并回 develop，CHANGELOG 归档。
