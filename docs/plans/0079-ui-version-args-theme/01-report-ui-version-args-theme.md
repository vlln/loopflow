---
title: UI 版本同步 / Args 声明预填 / 日夜主题 Report
description: system/meta 版本端点、loop meta.args 声明预填、light/dark 主题切换实现结果留档
type: report
status: done
created: 2026-07-24T07:30:00Z
---

# Summary

三条 RELEASE 验收意见全部实现：rail 版本号改为运行时从 `GET /system/meta` 拉取（消除硬编码 v0.17，版本号单一事实源为 `loopflow.__version__`）；loop frontmatter `meta.args` 声明驱动 New Run 对话框键值预填；日夜主题切换（light 调色板 + 持久化 + 系统偏好默认），dark 外观零变化。

# Changes

| 层 | 内容 |
|----|------|
| `infrastructure/web_resources.py` | `_extract_declared_args()`（复用 declared_phases 模式；非法项静默忽略）；Loop summary + detail 暴露 `declared_args`（缺省空列表） |
| `application/web.py` | `system_meta()` 返回 `{"version": loopflow.__version__}` |
| `presentation/web/server.py` | `GET /system/meta` 路由 |
| `web/` | rail 版本拉取（失败静默 `v—`）+ 主题切换按钮（Sun/Moon，localStorage `lf-theme`，默认 prefers-color-scheme）；NewRunDialog 按 `declared_args` 预填（未触碰时预填首 loop、切换 loop 重置、required 标 `*`）；styles.css 全部硬编码 hex 提升为变量 + `[data-theme="light"]` 调色板（dark 原值不变） |

# AC Results

| AC | 结果 | 测试 |
|----|------|------|
| AC-014-N-10 | [PASS] | 前端预填 + 切换重置 2 条；后端 `test_loop_summary_and_detail_include_declared_args` |
| AC-014-N-11 | [PASS] | 前端 rail 版本显示 + 失败占位 2 条；后端 `test_system_meta_returns_version` |
| AC-014-B-5 | [PASS] | 前端空白起始；后端无声明/非法声明 3 条（空列表、静默忽略、非 list） |
| AC-019-N-5 | [PASS] | 前端主题切换 + data-theme + localStorage 持久化 |
| AC-019-B-3 | [PASS] | light 调色板全量变量覆盖；agent 手动截图核验（dark 与现状一致、light 可读）；e2e dark 截图断言未受影响 |

# Verification Results

| 层 | 结果 |
|----|------|
| Python 全量 | 410 passed, 1 skipped（405 → 410） |
| 前端 vitest | 36 passed（30 → 36，既有未破坏） |
| typecheck / build | clean / 成功，静态资源已同步 |
| Playwright e2e | 10 passed, 2 skipped |

# Notes

- ac_manifest 流程教训：契约冻结新增 AC 后必须同步登记 `tests/web_support/ac_manifest.py` TARGETS（0078/0079 均出现契约提交导致 manifest 测试预先失败，已在本次补齐 AC-014-N-10/N-11/B-5、AC-019-N-5/B-3 映射）。
- 预填策略：loops 加载完成时若用户已手动编辑则不覆盖；仅切换 loop 强制重置为声明预填。
- `declared_args` 未持久化进 run.json（契约只要求 Loop API 暴露；declared_phases 的 run 持久化是 0071 另一链路）。
- light 主题例外：modal 遮罩两主题通用；React Flow Background 为 SVG presentation attribute，light 用 CSS 覆盖。
