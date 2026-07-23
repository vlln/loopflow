---
title: Release Certification Plan
description: 执行 RELEASE 阶段的版本确认、CHANGELOG、release 分支、发布冒烟和 tag
type: plan
status: done
created: 2026-07-23T00:00:00Z
---

# Goal

完成本轮 RELEASE 闭环：从已通过 SYSTEM_TEST 的 `develop` 创建 release 分支，确认版本号，整理 CHANGELOG，执行发布冒烟，通过后合并到 `main` 与 `develop` 并创建 tag。

# Inputs

- SYSTEM_TEST Report: `docs/plans/0048-system-test-certification/01-report-system-test-certification.md`
- 当前发布前版本：`pyproject.toml` 为 `0.17.2`
- 已发现 release 检查点：`src/loopflow/__init__.py` 仍为 `0.17.1`，发布前必须与最终版本一致

# Acceptance

Report 必须记录：

1. 最终版本号和选择理由。
2. `pyproject.toml`、`src/loopflow/__init__.py`、CHANGELOG 版本一致。
3. release 分支名称、HEAD、合并提交和 tag。
4. release 分支上 MR gate 或等价 release gate 通过。
5. wheel build/install smoke 通过，包内 Web static assets 存在。
6. `main` 与 `develop` 均包含 release 提交。
7. 若发布中失败，按 devloop 分类并说明回退到 RELEASE/DEVELOP/TEST_INFRA/DESIGN 的原因。

# Steps

1. 审核版本策略：根据恢复、停止、介入、Grok backend/ACP 等增量，确认发布版本。初始建议为 minor release `0.18.0`，但需用户确认。
2. 创建 `release/<version>` 分支，基于当前 `develop`。
3. 更新版本文件：`pyproject.toml` 与 `src/loopflow/__init__.py`。
4. 整理 `CHANGELOG.md`，新增目标版本条目，覆盖 AC-020/021/022、Grok backend/ACP、Web/API 相关变更。
5. 运行 release gate：至少 `./scripts/mr-gate.sh`；如存在专用发布脚本，优先补跑。
6. 构建并安装 wheel，确认 CLI 和 Web static assets 可用。
7. 合并 release 到 `main`，创建 tag。
8. 合并 release 回 `develop`，确认两个分支状态。
9. 写 `01-report-release-certification.md`，回填命令、提交、tag 和发布判定。
10. 将 Plan/container 标记为 done，更新 `docs/README.md` 当前阶段为下一轮 DESIGN 或保持 RELEASE 等待人工发布确认。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Version | 版本号已确认，所有版本文件一致 | Report: PASS |
| CHANGELOG | 目标版本条目完整 | Report: PASS |
| Release branch | `release/<version>` 从通过 SYSTEM_TEST 的 develop 创建 | Report: PASS |
| Release gate | MR/release gate 通过 | Report: PASS |
| Wheel smoke | wheel 可安装，Web assets 存在 | Report: PASS |
| Gitflow | release 合并到 `main` 和 `develop`，tag 已创建 | Report: PASS |

# Review Points

1. 发布版本是否采用 `0.18.0`。
2. 是否需要先推送远端分支/tag，还是仅完成本地 Gitflow 闭环。
3. 是否需要人工 staging 环境冒烟；若没有 staging 环境，本地 wheel smoke 是否作为发布冒烟证据。

# Exit

版本文件、CHANGELOG、release gate、wheel smoke、Gitflow 合并和 tag 全部完成后，RELEASE 阶段完成。若用户选择不立即发布，则本 Plan 保持 pending，`docs/README.md` 维持 RELEASE。
