---
title: 0.21.0 迭代复盘
description: 0.21.0 发布认证与迭代复盘：工期、问题、改进点
type: report
status: complete
created: 2026-07-25T01:20:00Z
---

# 0.21.0 迭代复盘

发布认证：v0.21.0 tag 在 main（release/0.21.0 → main + develop 已合并，分支已删）。系统测试 495 passed / 1 skipped，三 AC profile strict 全绿（80/69/32），浏览器视觉 13 passed，wheel 冒烟 ok。

## 交付

BL-001~004（可靠性主题，借鉴 loopany-platform 调研）：AC-026 失败分类、AC-027 失败熔断、AC-028 队列状态、AC-029 stale 宽限期。容器 0081（基建）→ 0082~0085（特性）→ 0086（欠账）→ 0087（系统测试），93 文件 +5101/-102。

## 工期

DESIGN → RELEASE 单日完成（2026-07-25），无工期偏差基线（首次全 devloop 流程单日迭代）。

## 问题与改进

| 问题 | 根因 | 改进 |
|------|------|------|
| release 冒烟时 test_smoke 失败 | 版本号双写（pyproject.toml + `src/loopflow/__init__.py`）不同步 | BL-013：版本号单源化 |
| Spec 的 UI 约束小节在 DESIGN 时漏写，0084 开发中补 | 设计时只覆盖了数据模型/业务规则/ API，漏了 UI 约束维度 | DESIGN 自查清单加「UI 约束是否同步」一项 |
| 6 处 AC 文本与实现漂移（0086 才发现） | 历史迭代缺少对应 manifest profile，strict 门禁未覆盖 | scheduling profile 已建立；三 profile strict 已常态化，漂移将在当轮暴露 |

## 改进点录入 backlog

- BL-013 版本号单源化（candidate）
