---
title: Recovery Controls Test Infrastructure Report
description: 记录恢复控制测试 fixture、fake、故障注入、contract 和 AC manifest 的实现与自证结果
type: report
status: complete
created: 2026-07-22T08:00:00Z
---

# Summary

恢复、永久停止与人工介入的一次性测试基础设施已完成。后续 DEVELOP 可直接组合确定性 Call cache、Backend session、持久化/并发故障、Intervention、workflow 和 v13 contract fixture 编写 AC-020..022 产品测试；恢复 manifest 已纳入 MR gate。

# Results

| 检查点 | 结果 | 证据 |
|--------|------|------|
| Cache | PASS | 六类 fixture、稳定层级 Call ID、单段 reader 通过；digest 漂移、未提交段和失败段串入均被拒绝 |
| Backend | PASS | durable/non-durable、early/complete/never session ID、create/resume、非零退出、异常和可控阻塞可注入 |
| Fault injection | PASS | atomic writer、Run lock、execution epoch、TERM/KILL、PID identity 和 clock 正反例通过 |
| Process safety | PASS | POSIX smoke 创建独立测试进程组，只终止并清理自身父子进程 |
| Contract | PASS | Run/Call/Intervention/Backend v13 schema 正例通过；旧 action 与缺失 capability 被拒绝 |
| Manifest | PASS | recovery profile 覆盖 AC-020..022 全部 32 场景；缺失、重复、旧 `/resume`、错误状态码和 strict planned node 被拒绝 |
| Regression | PASS | 恢复专项 15 passed；infrastructure 33 passed, 1 skipped；Python MR 门禁 290 passed, 1 skipped，coverage 83.01%（阈值 59%）；既有 Web manifest 60 scenarios |
| Scope | PASS | `src/`、Web 产品组件和业务 endpoint 无变更；仅 tests、manifest checker、MR gate 与文档变更 |

# Changes

- `dd85f55`：Call cache、Backend/fault/process/workflow/Intervention fixture、v13 schema、recovery manifest 与正反向自证。
- `caaf2ad`：将 recovery manifest planned/strict profile 接入现有 MR gate。
- `tests/system/recovery_cases.json`：AC-020..022 共 32 个 planned test nodes，等待 DEVELOP 替换为真实节点。

# Residual Risks

- 32 个恢复场景当前仍为 `planned::`；DEVELOP 必须逐项替换为真实 pytest/HTTP/UI/process node，strict checker 会阻止遗漏。
- process-group smoke 验证本机 POSIX 行为；Windows 不在当前支持范围，真实 PID 复用竞态仍需产品集成测试覆盖。
- Session Backend 使用确定性 fake，不证明任一真实供应商的 session durability；真实 backend 兼容性留给 SYSTEM_TEST 的显式环境验证。
- 本阶段未实现 recover、stop、intervene、Web endpoint 或前端业务交互。
