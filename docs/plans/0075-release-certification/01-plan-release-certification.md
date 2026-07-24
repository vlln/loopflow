---
title: Release 0.20.0 Certification Plan
description: 执行 0.20.0 RELEASE 阶段的版本确认、CHANGELOG、release gate、Gitflow 合并和 tag
type: plan
status: done
created: 2026-07-24T05:20:00Z
---

# Goal

完成 0.20.0 本地 RELEASE 闭环：从已通过 SYSTEM_TEST（0073）的 `develop`（含 0070-0074）创建 `release/0.20.0`，更新版本与 CHANGELOG，执行 release gate，通过后合并到 `main` 与 `develop` 并创建 `v0.20.0` tag。

# Inputs

- `develop` HEAD：72b4aab（Merge 0074）
- SYSTEM_TEST 认证：0073 通过；0074（WebUI 呈现层）前端全量验证通过
- 待发布内容：0070 SSE 多 topic（ADR-0041）、0071 Declared phases（ADR-0040）、0072 文件变化观察（ADR-0039）、0074 WebUI 信息架构收敛、0076 per-run working directory 与观察语义（发布暂停后范围扩展并入本版本，需重新 SYSTEM_TEST 认证）

# Steps

1. 从 `develop` 拉 `release/0.20.0`
2. `chore(release): prepare 0.20.0`：`pyproject.toml` 0.19.1 → 0.20.0 + CHANGELOG 0.20.0 条目
3. Staging 冒烟（自动化）：`scripts/wheel-smoke.sh` + Python 全量测试 + 前端 vitest/typecheck/build/e2e
4. 发布策略确认（上级审查）：本地工具一次性发布（merge + tag + push）
5. 合并 `release/0.20.0` 到 `main` 与 `develop`，在 `main` 上打 `v0.20.0` tag，删除 release 分支
6. `docs(release): certify 0.20.0` 收尾，推进到 DESIGN（下一轮迭代 0076）

# Exit

`v0.20.0` tag 落在 `main`，CHANGELOG 含 0.20.0 正式条目，`develop` 包含 release 合并，RELEASE 门禁逐项通过。
