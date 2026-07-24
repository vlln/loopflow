---
title: Intervention WebUI Design Report
description: 记录用户回答问题介入链路 WebUI 设计审核结果
type: report
status: complete
created: 2026-07-23T15:00:00Z
---

# Summary

0056 DESIGN 已完成审核。用户同意 Intervention WebUI 把回答 pending request 作为主操作、首版只支持顶层 schema type、多个 request 先以最早 pending 为主。同时收敛第 3 点：不单独建模“回答成功但自动恢复失败”，提交回答后的 worker/agent 失败归入普通 Run execution failure。

# Decisions

| 问题 | 结论 |
|------|------|
| `cancelled + pending request` 的主操作 | `respond` 是最高优先级主操作，`recover_retry` 降为次要动作 |
| schema UI 范围 | 首版只支持顶层 type，不做完整 JSON Schema form renderer |
| answer saved vs recovery failed | 不建模为 Intervention 特殊状态；后续失败按普通 Run execution failure 展示 |
| 多 request | 最早 pending 为主，其他只读折叠 |

# Framework Business Boundary

提交回答的错误边界是框架层 respond command 必须保证的业务不变量：schema 校验失败、request 不存在、request 已 answered、Run 当前不允许 respond。前端只消费这些错误和 Run/read model，不自行推断业务合法性。

不引入 `response_persisted`、`recovery_started`、`respond_status` 或新 lifecycle state。

# Verification

DESIGN 阶段未运行产品测试。本容器通过用户审核完成。

# Next

进入 TEST_INFRA，先补 respond 错误边界与 WebUI DOM contract，然后再进入 DEVELOP 调整实现。
