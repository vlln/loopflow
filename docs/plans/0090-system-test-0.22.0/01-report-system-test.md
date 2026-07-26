---
title: 0.22.0 系统测试报告
description: 0.22.0 迭代（BL-014 采用官方 Python ACP SDK）SYSTEM_TEST 全量验证
type: report
status: complete
created: 2026-07-25T05:35:00Z
---

# 0.22.0 系统测试报告

范围：BL-014 采用官方 Python ACP SDK 替换手搓 ACP 管道，CLI 保留为主传输，ACP 成为可选可用路径。容器 0088（mock ACP server 测试基建）→ 0089（ACP SDK 真实实现 + AC-030）。执行分支 develop（0089 合并后）。

## 测试摘要

| 测试层 | 通过/总数 | 失败用例 | 耗时 |
|--------|----------|----------|------|
| Python 全量（含覆盖率） | 527/527（1 skipped） | — | 33s |
| AC manifest strict（4 profile） | 80 + 69 + 32 + 21 = 202 scenarios | — | — |
| 浏览器/视觉（playwright） | 13/13（2 skipped） | — | 6.5s |
| 前端组件（vitest coverage） | 41/41（Stmts 98.19%） | — | — |
| 打包冒烟（wheel-smoke） | ok | — | — |
| ACP 端到端（AC-030，mock ACP server） | 6/6 | — | — |

结论: [PASS] 全部通过

## 专项测试

| 项 | 结论 | 说明 |
|----|------|------|
| 性能 | 跳过（有据） | 本轮为后端传输层替换，不涉及 Runs 首屏/SSE 推送路径；既有 p95 基准未受影响 |
| 安全 | 已知欠账 | npm audit brace-expansion 链 5 high 既有（BL-011），本轮 web 依赖零改动；新增运行时依赖 agent-client-protocol + pydantic（可选路径） |
| 兼容性 | 通过 | macOS 本机全量；CLI 默认路径行为不变（向后兼容），ACP 为新增可选路径 |

## 失败原因分类

无失败用例。无阻塞级缺陷。

## 遗留（不阻塞发布）

- ADR-0049 §8 的 extra `[acp]` 划分未做（0088/0089 实现阶段放主依赖区）；AC-030-B-2 的"未装 extra 报错"用 mock 验证常量存在，真实触发需 RELEASE 后做 extra 划分。记入 backlog。
- grok ACP 的 `_meta` system prompt 映射在 SDK 路径不生效（SDK session/new 不接受 _meta），system prompt 改走 prompt 文本拼接；不影响 AC-030。
- spike 分支 spike/0049-acp-sdk-spike 保留作参考（不合并）。
