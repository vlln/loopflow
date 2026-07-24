---
title: Release 0.19.0 Certification Report
description: 记录 0.19.0 release 分支、版本、CHANGELOG、发布门禁、Gitflow 合并和 tag
type: report
status: complete
created: 2026-07-23T19:55:00Z
---

# Summary

RELEASE 完成。本地 Gitflow 已闭环：从 `develop` 创建 `release/0.19.0`，更新版本与 CHANGELOG，release gate 通过，合并到 `main` 并创建 `v0.19.0` tag，再合并回 `develop`。

# Version

| 项 | 值 |
|----|----|
| 最终版本 | `0.19.0` |
| 选择理由 | Agent structured intervention vNext 新增多 request、options/custom、batch respond 和多问题 WebUI，属于向后兼容功能新增，按 SemVer 采用 minor release |
| `pyproject.toml` | `0.19.0` |
| `src/loopflow/__init__.py` | `0.19.0` |
| `uv.lock` | `0.19.0` |
| CHANGELOG | `0.19.0 — 2026-07-23` |

# Gitflow

| 项 | 值 |
|----|----|
| Release branch | `release/0.19.0` |
| Release branch HEAD | `7bf769a` |
| Main merge commit | `8a4726c` |
| Develop merge commit | `8c3fe5f` |
| Tag | `v0.19.0` |
| Tag target | `main` merge commit `8a4726c` |
| Remote push | 未执行；本次只完成本地 Gitflow 闭环 |

# Gate Evidence

| 命令 | 结果 |
|------|------|
| `./scripts/mr-gate.sh` on `release/0.19.0` | PASS |
| Python tests | PASS: `348 passed, 1 skipped`; coverage `81.12%` |
| AC manifest | PASS: global `60 scenarios`，recovery `55 scenarios` |
| Frontend typecheck | PASS |
| Frontend unit coverage | PASS: `15 passed` |
| Frontend build | PASS |
| Browser tests | PASS: `10 passed, 2 skipped` |
| npm audit | PASS: `found 0 vulnerabilities` |
| Wheel smoke | PASS: built and installed `loopflow-0.19.0-py3-none-any.whl`; `index.html + 2 hashed assets` present |

# Failure Classification

| 项 | 分类 | 处置 |
|----|------|------|
| npm deprecated warnings | 外部依赖提示 | 非阻塞；audit 为 0 vulnerabilities |
| Vite chunk size warning | 构建提示 | 非阻塞；生产构建成功 |
| Playwright `NO_COLOR` warning | 环境提示 | 非阻塞；浏览器测试通过 |
| Playwright fixture 404 log | 测试夹具行为 | 非阻塞；被测流程通过 |

# Recommendation

本地 RELEASE 完成。若需要对外发布，还需推送 `main`、`develop`、`release/0.19.0` 和 `v0.19.0` tag 到远端，并执行远端/生产环境发布流程。
