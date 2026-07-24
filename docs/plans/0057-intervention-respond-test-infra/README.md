# 0057 Intervention respond 错误边界测试契约

对应阶段：`TEST_INFRA`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Intervention respond 错误边界测试契约](01-plan-intervention-respond-test-infra.md) | [Report](01-report-intervention-respond-test-infra.md) | done |

## 背景

0056 已明确 `respond` 的 4 类前置条件失败是框架层 application command 业务边界，不是 WebUI 推断逻辑，也不是特殊 Run execution failure。进入 DEVELOP 前，AC、Interface 和 contract tests 必须能分别验证这 4 类错误的错误码与无副作用边界。

## 范围

- 补 AC-022 respond 错误边界。
- 补 Web API interface 对 `respond` 的无副作用契约说明。
- 拆分/补充 application contract tests，显式覆盖 schema validation、request not found、already answered、invalid run transition。
- 更新 recovery manifest 映射和生成文件。

## 非范围

- 不修改 `src/` 产品实现。
- 不修改 Web 前端业务行为。
- 不引入 `response_persisted`、`recovery_started`、`respond_status` 或新 lifecycle state。
