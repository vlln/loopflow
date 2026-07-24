---
title: Intervention Frontend Contract Report
description: 记录用户回答问题介入链路的前后端契约对齐结果
type: report
status: complete
created: 2026-07-23T14:30:00Z
---

# Summary

0055 已完成 Intervention 前后端契约对齐。后端 Web contract 现在覆盖 InterventionSummary，WebUI 按 schema 类型提交结构化 response，waiting_input 与 cancelled pending request 的回答路径继续可用。

# Changes

- Web support contract 增加 `intervention` schema 和 example。
- Web API integration test 对 pending 与 answered InterventionSummary 执行 contract validation。
- WebUI InterventionPanel 增加 string text input、number input、JSON textarea fallback，并保留 boolean approve/reject。
- WebUI 在 `resume_mode=continue` 的 request 上显示 session continuation 标记。
- Web unit tests 覆盖 boolean、string、number、object JSON、null schema、cancelled pending request 和 API error toast。

# Verification

| 检查 | 结果 |
|------|------|
| Web support/API | `pytest tests/infrastructure/test_web_test_support.py tests/integration/test_web_api.py`：15 passed |
| Web typecheck | `npm run typecheck` in `web/`：passed |
| Web unit | `npm test` in `web/`：13 passed |
| AC manifest recovery | `python3 scripts/check-ac-manifest.py --profile recovery`：37 scenarios |
| AC manifest global | `python3 scripts/check-ac-manifest.py`：60 scenarios |
| Diff check | `git diff --check`：passed |

# Next

保持当前系统阶段为 DESIGN，下一步可讨论是否为 Intervention schema 支持更完整的 JSON Schema form renderer。
