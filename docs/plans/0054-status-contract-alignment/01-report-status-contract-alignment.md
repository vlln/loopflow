---
title: Status Contract Alignment Report
description: 记录后端状态相关设计与产品接口、文档和 contract fixture 的对齐结果
type: report
status: complete
created: 2026-07-23T14:00:00Z
---

# Summary

0054 已完成状态契约对齐。核心 Run 状态语义未变；本次只修正 InterventionSummary 字段漂移和活跃索引 wording。

# Changes

- `InterventionSummary` 产品返回补齐 `can_continue_session`。
- answered request 的 `InterventionSummary` 现在按 Interface 条件返回 `response`。
- Spec、Interface、前端类型和 recovery contract fixture 统一使用 `responded_at`。
- AC/ADR 活跃索引从“永久停止”改为“可靠取消”。
- ADR 0037 索引状态同步为 `accepted`。

# Verification

| 检查 | 结果 |
|------|------|
| Python targeted | `pytest tests/infrastructure/test_recovery_support.py tests/unit/test_web_application.py tests/integration/test_web_api.py`：42 passed |
| AC manifest recovery | `python3 scripts/check-ac-manifest.py --profile recovery`：37 scenarios |
| AC manifest global | `python3 scripts/check-ac-manifest.py`：60 scenarios |
| Web typecheck | `npm run typecheck` in `web/`：passed |
| Web unit | `npm test` in `web/`：11 passed |
| Diff check | `git diff --check`：passed |

# Next

保持当前系统阶段为 DESIGN，等待下一轮正式功能设计。
