---
title: 0.28.0 系统测试
description: 在 develop 上验证 0.28.0 增量（BL-056/057/058/059）的集成、系统、视觉与专项质量
type: plan
status: pending
created: 2026-08-03T00:00:00Z
---

# Context

0.28.0 迭代增量：ADR-0008 修订（BL-056，文档）、demo loop 黑盒（BL-057/058，测试资产）、子进程测试确定性（BL-059，测试基建）。所有增量已合入 develop，DEVELOP 无新业务特性。

# Request

1. 记录 develop HEAD 与工作树状态。
2. 按层级执行全量测试：集成 → 系统（CLI E2E + demo loop 黑盒）→ 视觉（Playwright）→ 专项（strict manifest、性能、安全）。
3. 对所有失败分类（基建缺陷/设计缺陷/局部 bug），判定阻塞级缺陷。
4. 生成 Report：HEAD、命令摘要、失败分类、阻塞判定、证据路径。

# Constraints

- 不重复 DEVELOP 单元/组件测试，不修改冻结 Spec/AC/ADR。
- 不调用付费外部 Agent（demo loop 用 mock bash，可入 CI）。
- 失败先分类；局部 bug 用 `fix/*`，基建/设计缺陷按 devloop 退回对应阶段。

# Checkpoint

- [ ] 集成层通过
- [ ] 系统层（CLI E2E + demo loop 黑盒）通过
- [ ] 视觉/浏览器层通过
- [ ] strict manifest 全 profile 通过
- [ ] 专项（性能/安全）通过或有据豁免
- [ ] 无阻塞级缺陷

# Steps

1. 记录 develop HEAD 与工作树状态。
2. 运行 `tests/integration`、`tests/e2e`、`tests/` 全量。
3. 运行六 profile strict manifest（SYSTEM_TEST 阶段 strict 模式）。
4. 运行 Playwright 三视口黑盒/视觉测试。
5. 运行性能专项（Runs 首屏 p95 < 500ms）。
6. 生成 Report。
