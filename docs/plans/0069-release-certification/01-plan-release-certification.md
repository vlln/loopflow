---
title: Release 0.19.1 Certification Plan
description: 执行 0.19.1 RELEASE 阶段的版本确认、CHANGELOG、release gate、Gitflow 合并和 tag
type: plan
status: done
created: 2026-07-24T02:32:29Z
---

# Goal

完成 0.19.1 本地 RELEASE 闭环：从已通过 SYSTEM_TEST 的 `develop` 创建 `release/0.19.1`，更新版本与 CHANGELOG，执行 release gate，通过后合并到 `main` 与 `develop` 并创建 `v0.19.1` tag。

# Inputs

- SYSTEM_TEST Report: `docs/plans/0068-system-test-certification/01-report-system-test-certification.md`
- 当前发布前版本：`0.19.0`
- 版本策略：0065/0067 是 bugfix，0066 是内部前端重构且不改变业务行为，按 SemVer 采用 patch release `0.19.1`

# Acceptance

1. `pyproject.toml`、`src/loopflow/__init__.py`、`uv.lock` 与 CHANGELOG 版本一致。
2. release 分支 `release/0.19.1` 从通过 SYSTEM_TEST 的 `develop` 创建。
3. release gate 通过。
4. wheel build/install smoke 通过，包内 Web static assets 存在。
5. `main` 与 `develop` 均包含 release 提交。
6. tag `v0.19.1` 已创建。

# Steps

1. 创建 `release/0.19.1` 分支。
2. 更新版本文件和 CHANGELOG。
3. 运行 `./scripts/mr-gate.sh`。
4. 合并 release 到 `main`，创建 `v0.19.1` tag。
5. 合并 release 回 `develop`。
6. 写 Report，标记 Plan/container done。

# Exit

本地 Gitflow 闭环完成后，更新 `docs/README.md` 为 RELEASE 完成，可开始下一轮 DESIGN 或等待远端发布。
