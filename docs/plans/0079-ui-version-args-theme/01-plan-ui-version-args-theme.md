---
title: UI 版本同步 / Args 声明预填 / 日夜主题 Plan
description: system/meta 版本端点 + loop meta.args 声明预填 + light/dark 主题切换
type: plan
status: pending
created: 2026-07-24T07:00:00Z
---

# Goal

修复/实现 RELEASE 人工验收的三条意见：UI 版本号与包版本同步（消除硬编码 v0.17）、Arguments 按 loop 声明预填、日夜主题切换。

# Constraints

- 版本号单一事实源为 `loopflow.__version__`；运行时 API 下发（`GET /api/v1/system/meta` → `{"version": "..."}`)，前端 rail 拉取显示，失败时静默保留占位
- args 声明走 `meta.args`（与 0071 `meta.phases` → `declared_phases` 同模式）：`[{name, default, description, required}]`；Loop summary + detail 均返回 `declared_args`；非法声明静默忽略（不阻断 loop 加载）
- 对话框预填：选择 loop 后按声明生成键值行（default 填入 value，无 default 留空）；required 仅作提示，不做强制校验
- 主题：CSS 变量 light 调色板（`[data-theme="light"]`）；rail 底部切换按钮；localStorage 持久化；默认跟随 `prefers-color-scheme`；硬编码 hex 需审计保证 light 下可读
- 后端零外部依赖

# Steps

1. 契约：interface（`GET /system/meta` + Loop `declared_args` 字段）、spec（US-028/029、BR-047/048）、AC（AC-014-N-10/N-11、B-5；AC-019-N-5、B-4）
2. 后端：`/system/meta` 端点；`meta.args` 解析（复用 declared_phases 提取模式）+ Loop API 字段
3. 前端：rail 版本拉取；NewRunDialog 按 selected loop 的 declared_args 预填；主题切换（样式 + 开关 + 持久化）
4. 测试：后端端点与解析测试；前端（预填、版本显示、主题切换持久化）；既有测试不回归
5. 全量验证：pytest、vitest/typecheck/build/e2e、静态资源同步

# Acceptance

- AC-014-N-10（预填）、AC-014-N-11（版本同步）、AC-014-B-5（无声明空白起始）
- AC-019-N-5（主题切换 + 持久化 + 系统偏好默认）、AC-019-B-3（light 下区分度）
- 既有 Python 405 + 前端 30 测试全部回归通过

# Checkpoint

- 后端 declared_args 可用后前端再联调预填
- 合入前全量测试通过

# Exit

全部 Acceptance 通过，写 Report，合并 develop，重新拉 release/0.20.0。
