---
title: System Test Certification Plan
description: 0070/0071/0072 系统级验证认证计划
type: plan
status: done
created: 2026-07-24T00:00:00Z
---

# Goal

在 `develop` 分支上对 0070/0071/0072 三个执行容器的实现进行系统级全量验证，确认无阻塞级缺陷，可进入 RELEASE。

# Scope

1. Python 全量测试 + 覆盖率
2. 前端全量测试 + typecheck + build
3. AC manifest strict 模式验证（0 planned nodes）
4. CLI 集成测试 + smoke 测试
5. 失败原因分类 + 阻塞级缺陷判定

# Exit

全量测试通过，无阻塞级缺陷，写 Report 并推进到 RELEASE。
