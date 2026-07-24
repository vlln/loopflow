---
title: Release Certification Report
description: 记录 0.18.0 release 分支、版本、CHANGELOG、发布门禁、Gitflow 合并和 tag
type: report
status: complete
created: 2026-07-23T13:55:00Z
---

# Summary

RELEASE 完成。本地 Gitflow 已闭环：从 `develop` 创建 `release/0.18.0`，更新版本与 CHANGELOG，release gate 通过，合并到 `main` 并创建 `v0.18.0` tag，再合并回 `develop`。

# Version

| 项 | 值 |
|----|----|
| 最终版本 | `0.18.0` |
| 选择理由 | 本轮新增 Grok backend/ACP，并引入可靠恢复、取消与人工介入的用户可见能力，属于 minor release |
| `pyproject.toml` | `0.18.0` |
| `src/loopflow/__init__.py` | `0.18.0` |
| `uv.lock` | `0.18.0` |
| CHANGELOG | `0.18.0 — 2026-07-23` |

# Gitflow

| 项 | 值 |
|----|----|
| Release branch | `release/0.18.0` |
| Release branch HEAD | `7d35466` |
| Main merge commit | `f720685` |
| Develop merge commit | `ed70c97` |
| Tag | `v0.18.0` |
| Tag target | `main` merge commit `f720685` |
| Remote push | 未执行；本次只完成本地 Gitflow 闭环 |

# Gate Evidence

| 命令 | 结果 |
|------|------|
| `./scripts/mr-gate.sh` on `release/0.18.0` | PASS after release test fix |
| Python tests | PASS: `340 passed, 1 skipped`; coverage `81.37%` |
| AC manifest | PASS: global `60 scenarios`，recovery `37 scenarios` |
| Frontend typecheck | PASS |
| Frontend unit coverage | PASS: `11 passed` |
| Frontend build | PASS |
| Browser tests | PASS: `10 passed, 2 skipped` |
| Wheel smoke | PASS: built and installed `loopflow-0.18.0-py3-none-any.whl`; `index.html + 2 hashed assets` present |

# Failure Classification

| 项 | 分类 | 处置 |
|----|------|------|
| 首次 release gate 失败：`tests/unit/test_smoke.py` 硬编码 `0.17.1` | 局部测试缺陷 | 改为从 `pyproject.toml` 读取版本，并提交 `3d600f2` |
| npm deprecated warnings | 外部依赖提示 | 非阻塞；audit 为 0 vulnerabilities |
| Vite chunk size warning | 构建提示 | 非阻塞；生产构建成功 |
| Playwright `NO_COLOR` warning | 环境提示 | 非阻塞；浏览器测试通过 |
| Playwright fixture 404 log | 测试夹具行为 | 非阻塞；被测流程通过 |

# Checkpoints

| 检查点 | 结果 | 证据 |
|--------|------|------|
| Version | PASS | 版本文件、lock、CHANGELOG 一致 |
| CHANGELOG | PASS | 新增 0.18.0 条目 |
| Release branch | PASS | `release/0.18.0` at `7d35466` |
| Release gate | PASS | MR gate 全部通过 |
| Wheel smoke | PASS | wheel 安装与 Web assets 验证通过 |
| Gitflow | PASS | `main` 和 `develop` 均已合并 release，tag 已创建 |

# Recommendation

本地 RELEASE 完成。若需要对外发布，还需推送 `main`、`develop`、`release/0.18.0` 和 `v0.18.0` tag 到远端，并执行远端/生产环境发布流程。
