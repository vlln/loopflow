---
title: 0.21.0 系统测试报告
description: 0.21.0 迭代（BL-001~004 可靠性主题）SYSTEM_TEST 阶段全量验证结果
type: report
status: complete
created: 2026-07-25T01:10:00Z
---

# 0.21.0 系统测试报告

范围：BL-001 失败分类（0083）、BL-002 失败熔断（0084）、BL-003 stale 宽限期（0085）、BL-004 队列状态（0082），及 0086 manifest 欠账清理。执行分支：develop（5d5f733 之后）。

## 测试摘要

| 测试层 | 通过/总数 | 失败用例 | 耗时 |
|--------|----------|----------|------|
| 单元 + 基建自证（tests/unit + tests/infrastructure） | 411/411（1 skipped） | — | 4.4s |
| 集成 + CLI e2e（tests/integration + tests/e2e） | 84/84 | — | 24.8s |
| Python 全量（含覆盖率） | 495/495（1 skipped） | — | ~28s |
| 浏览器/视觉（playwright webui.spec.ts） | 13/13（2 skipped，既有视口条件 skip） | — | 3.7s |
| 前端组件（vitest coverage） | 41/41 | — | — |
| AC manifest（web / recovery / scheduling，全 strict） | 80 / 69 / 32 scenarios | — | — |
| 打包冒烟（wheel-smoke） | ok（index.html + 2 hashed assets） | — | — |

结论: [PASS] 全部通过

## 专项测试

| 项 | 结论 | 说明 |
|----|------|------|
| 性能 | 跳过（有据） | 本轮变更为调度/恢复/分类逻辑，不涉及 Runs 首屏与 SSE 推送路径；既有 p95 基准（0070s 迭代建立）未受影响，未重复测量 |
| 安全 | 已知欠账 | npm audit brace-expansion 链 5 high 为既有问题（BL-011，@vitest/coverage-v8 依赖链，仅开发依赖），本轮 web 依赖零改动 |
| 兼容性 | 通过 | macOS 本机全量；Linux 路径无平台相关变更（loop_state/stale_since/queue 均为 POSIX 文件操作） |

## 失败原因分类

无失败用例，无需分类。无阻塞级缺陷。

## 遗留（不阻塞发布）

- BL-010 done（AC-010 文本已对齐 ADR-0031）；0086 顺带修正 web 4 条 AC 文本漂移（见 0086 Report）。
- BL-012 candidate：SSE file_changes OSError 未按 topic 隔离，待裁决。
- BL-011 candidate：npm audit 既有失败。
