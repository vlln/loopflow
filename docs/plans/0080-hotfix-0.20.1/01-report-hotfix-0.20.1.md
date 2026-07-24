---
title: Hotfix 0.20.1 Report
description: 修复 v0.20.0 三个产品级缺陷的执行结果留档
type: report
status: done
created: 2026-07-24T08:35:00Z
---

# Summary

0.20.1 hotfix 闭环完成。三个修复均为发布同步期 CI 排查中发现（v0.20.0 已发布代码在 Linux CI 首次全量运行时暴露），经 Docker Linux 复现定位、develop 修复验证后 cherry-pick 至 hotfix 分支。

# Fixes

| 缺陷 | 修复 | 提交 |
|------|------|------|
| recover 时 `execution_options` 的 mock 不生效：`set_mock` 在 frozen options 合并**之前**执行，无 backend 机器上 `agent()` 解析真实后端并 `sys.exit(1)`（之前开发机有 CLI 从未暴露，剥离 PATH 可复现） | mock 应用移到合并之后 | fdc748f（cherry-pick 自 60ba63a） |
| 子进程启动信号窗口 2s，CI 低配机器误报 `run_process_start_failed` | 窗口提升为 15s | 同上 |
| Python 3.14 Linux 默认 forkserver：server 进程懒创建后环境冻结，后续 `setenv` 不传播，子进程拿到陈旧环境（macOS spawn 每子进程全新所以未暴露） | executor 默认显式 `spawn`，跨平台行为确定 | 同上 |
| `test_smoke` 直接 import `tomllib`（3.11+），3.10 收集期崩溃 | 3.10 回退正则解析 | 32a8719（cherry-pick 自 6898991） |
| CI 门禁：web profile AC manifest 漂移（21 缺失 + 2 断言不一致） | cases.json 60→80（14 real + 6 planned） | c7a563b（cherry-pick 自 ce066eb） |

# Verification

| 层 | 结果 |
|----|------|
| hotfix 分支全量 | 410 passed, 1 skipped；前端 36 passed |
| develop 侧（修复合入前） | CI 5/5 全绿（python 3.10/3.14、frontend、browser、wheel）；macOS + Docker Linux 双平台 410 passed |
| 复现验证 | `env PATH=/usr/bin:/bin` 下 recover mock run：修复前 DID NOT RAISE（sys.exit），修复后正常 replay_diverged |

# Release

- `main`：Merge hotfix 0.20.1 + tag `v0.20.1`
- `develop`：回并（1fd4004）
- CHANGELOG 0.20.1 条目已归档

# Notes

- 调试环境教训：Docker 绑定挂载仓库后容器内 `uv sync` 会覆盖宿主机 `.venv`（应使用 `UV_PROJECT_ENVIRONMENT` 隔离）。
- 流程教训：develop 长期未 push（100+ commits）导致这批缺陷直到发布同步才经 Linux CI 暴露；CI 保护现已生效，后续提交每次都会过 5 项检查。
