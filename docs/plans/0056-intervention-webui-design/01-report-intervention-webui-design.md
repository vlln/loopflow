---
title: Intervention WebUI Design Report
description: 记录用户回答问题介入链路 WebUI 设计审核结果
type: report
status: complete
created: 2026-07-23T15:00:00Z
---

# Summary

0056 DESIGN 已完成审核。用户同意 Intervention WebUI 把回答 pending request 作为主操作、首版只支持顶层 schema type、多个 request 先以最早 pending 为主，同时要求回答成功但自动恢复失败时 UI 明确区分“answer 已保存”和“Run 恢复失败”。

# Decisions

| 问题 | 结论 |
|------|------|
| `cancelled + pending request` 的主操作 | `respond` 是最高优先级主操作，`recover_retry` 降为次要动作 |
| schema UI 范围 | 首版只支持顶层 type，不做完整 JSON Schema form renderer |
| answer saved vs recovery failed | 必须区分；需要补后端错误响应或 read model 契约 |
| 多 request | 最早 pending 为主，其他只读折叠 |

# Backend Gap

当前后端已经先持久化 response 再启动恢复，但恢复失败时只返回普通错误码。前端无法直接知道 response 是否已保存。下一阶段必须先在接口/AC/contract 中定义 `response_persisted` 或等价字段，再实现 UI 的 panel-level error 状态。

# Verification

DESIGN 阶段未运行产品测试。本容器通过用户审核完成。

# Next

进入 TEST_INFRA，先补 AC 与 Web API/WebUI contract，然后再进入 DEVELOP 调整实现。
