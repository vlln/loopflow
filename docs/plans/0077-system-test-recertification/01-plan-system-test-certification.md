---
title: System Test Recertification Plan
description: 0076 合并后 develop 全量系统级验证与 0.20.0 重新发布就绪判定
type: plan
status: pending
created: 2026-07-24T06:05:00Z
---

# Goal

在 `develop` 分支上对 0076（显式工作目录、基线快照、文件预览）及全部待发布内容（0070-0074）进行系统级全量验证，确认无阻塞级缺陷，可重新进入 RELEASE 执行 0.20.0。

# Scope

1. Python 全量测试 + 覆盖率（阈值 59%）
2. 前端 vitest + typecheck + build + Playwright e2e
3. AC manifest strict（file_changes / recovery / web 全部 profile）
4. wheel 冒烟（scripts/wheel-smoke.sh）
5. 失败原因分类（基建缺陷/设计缺陷/局部 bug）+ 阻塞级缺陷判定
6. 预先存在的 web profile（AC-014..019）manifest 漂移分类

# Exit

全量测试通过、无阻塞级缺陷，写 Report 并重新进入 RELEASE（0075 容器继续）。
