---
title: 0.27.0 迭代复盘
description: 工期偏差、问题总结、改进点
type: report
status: complete
created: 2026-07-30T00:00:00Z
---

# 0.27.0 迭代复盘

## 交付

BL-046 Agent waiting_input 控制协议、BL-051 Web 二进制文件预览、BL-052 Run append prompt、BL-054 New Run declared args 契约。53 个非合并提交（v0.26.0..v0.27.0）。执行容器 0105（设计）→ 0106/0109/0111（基建）→ 0107/0112（开发）→ 0108（系统测试）→ RELEASE。

## 问题总结

1. **契约传导遗漏（设计缺陷）**：ADR-0046（2026-07-27 修订）移除 reconcile 宽限阻塞，但 AC-014-B-7、AC-029-B-1、Spec BR-052、Interface 0001 未同步，直到 0112-03 才暴露。根因：ADR 修订后无强制下游传导检查。
2. **契约漂移沉默（基建缺陷）**：recovery manifest 缺节点存在性检查，AC-029-B-1/AC-020-F-3 引用已改名测试函数未被 strict 拦截，契约被静默篡改。
3. **mr-gate 阶段假设（基建缺陷）**：`test_mr_gate_allows_planned_during_incremental_develop` 硬编码假设当前为 DEVELOP，阶段推进后 CI 失败。
4. **发布流程认知错误（流程）**：误把 ADR-0008 的 PyPI 决策当现行流程，实际历史发布均为本地型（release/* → main + tag）。ADR 与实际脱节未被发现。

## 改进点（已录 backlog）

- BL-056：ADR-0008 部署决策与实际发布流程不符，需修订为本地型或补齐真实 PyPI 流程。
- 既有债保留：BL-049（--write 无早退）、BL-042/043（候选需求）。

## 工期偏差

0.27.0 因 Web 契约基建（0109-0112）返工量大：86→89 场景对齐 + 71 个 planned 场景补齐，属 DESIGN 契约冻结不完整导致的下游返工。下次 DESIGN 应在冻结前完成 strict 语义审查，避免 DEVELOP 阶段才大规模补测。
