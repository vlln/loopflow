---
title: Release 0.20.0 Certification Report
description: 0.20.0 RELEASE 阶段执行结果留档
type: report
status: done
created: 2026-07-24T05:20:00Z
---

# Summary

0.20.0 发布闭环完成。期间发布两次暂停扩展范围（0076 工作目录/观察语义、0078 对话框 UX、0079 版本同步/args 预填/主题相继并入），最终内容：0070-0072 + 0074 + 0076 + 0078 + 0079，经 0073/0077 两次 SYSTEM_TEST 认证与多轮 staging 冒烟，人工验收通过后合并 `main` + `develop` 并打 `v0.20.0` tag。

# Gate Results

| 门禁项 | 结果 |
|--------|------|
| staging 冒烟（自动化） | [PASS] wheel 0.20.0 构建 + 安装 + 资产验证；Python 410 passed, 1 skipped；前端 36 vitest + typecheck + e2e 10/2 |
| production 冒烟（自动化） | [PASS] 本地工具与 staging 同源：release 分支全量测试 + wheel 验证 + 用户人工验收（工作目录/基线/预览/目录选择器/args 编辑器/版本号/主题） |
| 发布策略与监控 | [PASS] 上级确认：本地工具一次性发布，无灰度；监控不适用 |
| 版本 tag | [PASS] `v0.20.0` 在 `main`（ed1e601） |
| CHANGELOG | [PASS] 0.20.0 条目完整（Added 9 / Changed 5 / Fixed 4） |
| release 合并 | [PASS] `main`（Merge release 0.20.0）+ `develop`（ec60f3c 回并），release/0.20.0 分支已删除 |

# 失败与回退记录

| 事件 | 处理 |
|------|------|
| 首次发布确认前用户暂停，范围扩展（0076） | release 分支撤下，RELEASE → DESIGN 增量迭代（ADR-0042/0043、AC-025） |
| 手测发现对话框 UX 缺陷（0078）、版本号/args/主题（0079） | 按规则在 develop 修复后重新拉 release（共 4 次），每轮重跑冒烟 |
| `test_smoke` 版本断言失败 | release 分支内修复（`__init__.py` 版本号漏改，并入 prepare 提交） |
| web profile manifest 漂移（0077 发现） | 分类为非阻塞基建缺口（预先存在，0070-0072 时期），遗留待立 `test/*` 容器 |

# 迭代复盘

- 范围控制：单版本从 3 个功能扩展到 7 个容器，人工验收驱动的修复走了 4 轮 release 重拉。教训：验收反馈集中批量处理后再进 RELEASE，而非逐个进入。
- 流程教训：契约冻结新增 AC 时必须同步登记 ac_manifest TARGETS（0078/0079 均出现契约提交导致 manifest 测试预先失败）。
- 遗留：① web profile（AC-015/016）manifest 漂移，另立 `test/*` 容器；② develop/main 未 push（98/72 commits），待用户确认。
