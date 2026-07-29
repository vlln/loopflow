---
title: 0.27.0 系统测试
description: 在 develop 上验证 BL-046/051/052/054 的集成、系统、视觉和专项质量
type: plan
status: pending
created: 2026-07-29T14:50:00Z
---

# Context

0107 已通过 DEVELOP MR 与提测门禁并合入 develop。当前只执行 SYSTEM_TEST 所属层，不重复单元测试或新增功能。

# Request

1. 依次执行服务/API/CLI 集成、CLI E2E、strict manifest 和浏览器黑盒验证。
2. 验证图片/PDF预览、append prompt、declared args 与 Agent intervention 的成品链路。
3. 执行性能、安全、兼容性专项并对所有失败分类。

# Output Format

- `01-report-system-test.md` 记录 HEAD、命令摘要、失败分类、阻塞级缺陷判定和证据路径。
- 测试层全绿且无阻塞级缺陷时给出 RELEASE 建议。

# Constraints

- 不重复 DEVELOP 单元/组件测试，不修改冻结 Spec/AC/ADR。
- 失败先分类；局部 bug 使用 `fix/*`，基建/设计缺陷按 devloop 退回对应阶段。
- 不调用付费外部 Agent；ACP 兼容性使用本地 mock server。

# Checkpoint

- [ ] 集成层通过
- [ ] CLI/API 系统层与六 profile strict manifest 通过
- [ ] 浏览器/视觉层通过
- [ ] 性能、安全、兼容专项通过或有据豁免
- [ ] 无阻塞级缺陷

# Steps

1. 记录 develop HEAD 与工作树状态。
2. 运行 `tests/integration`，通过后运行 `tests/e2e`。
3. 运行六 profile strict manifest。
4. 运行 Playwright 三视口黑盒/视觉测试。
5. 对照 Spec 非功能指标执行适用专项，生成 Report。
