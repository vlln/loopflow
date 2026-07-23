---
title: Intervention Control Plan
description: 实现 workflow/Agent 阻塞人工介入、请求持久化、回答校验和回答后的确定性恢复
type: plan
status: complete
created: 2026-07-22T19:10:00Z
---

# Goal

依据 ADR 0036、Spec v13、Interface 0001 和 AC-022，实现人工介入：workflow 或 Agent 以结构化方式创建 pending request，Run 进入 `waiting_input` 并释放 worker；用户提交一次 immutable response 后，服务自动恢复同一 `run_id`，重放到相同请求时注入 response。

# Acceptance

本 Plan 完整负责以下场景，Report 必须逐项记录真实测试节点、`[PASS]` 和提交：

`AC-022-N-1` `AC-022-N-2` `AC-022-N-3` `AC-022-N-4`

`AC-022-B-1` `AC-022-B-2`

`AC-022-E-1` `AC-022-E-2` `AC-022-E-3`

`AC-022-F-1` `AC-022-F-2`

# Constraints

1. Intervention request 必须是显式结构化输入；不得从自然语言问题文本推断。
2. workflow `intervene(key, prompt, schema=None)` 创建 `resume_mode=replay` request；回答后通过确定性重放返回 response。
3. Agent 结构化控制输出创建 `resume_mode=continue` request；只有目标 Call 已持久化 durable `session_id` 时允许进入 `waiting_input`，否则以 `continue_not_supported` 失败且不创建 pending request。
4. request identity 必须稳定：`key`、`prompt_digest`、`schema_digest`、`call_id/session_id` 和 `resume_mode` 持久化；回答后重放遇到不同 key/prompt/schema 必须 `replay_diverged`。
5. response 只接受一次；重复提交返回 `intervention_already_answered`，不得覆盖 response 或启动第二个 worker。
6. schema 首版只实现 AC 覆盖所需的 JSON Schema 子集：`{"type":"boolean"}`、`{"type":"string"}`、`{"type":"number"}`、`{"type":"object"}`、`{"type":"array"}` 和 `null`。不支持的 schema 返回 `validation_failed`。
7. 回答成功后自动恢复同一 Run：`resume_mode=replay` 走 replay recover；`resume_mode=continue` 走 continue recover；恢复错误按 Interface 映射。
8. `waiting_input` 允许 `respond` 和 `stop`；`cancelled`、`done`、`failed`、legacy `stopped` 不允许 respond。
9. 产品代码不得依赖 `tests/recovery_support`；AC-020/021 的真实 manifest 节点不得回退。

# Steps

1. 建立 AC-022 失败测试：runtime workflow intervention、Agent control output、application/API response、WebUI 控件、manifest 映射。
2. 增加 intervention storage primitive：request/response JSON 原子写、list/read、schema 校验、digest 校验和事件追加。
3. 扩展 `RunContext` 和 runtime API：向 workflow 注入 `intervene()`；首次 pending 写 request 并抛出受控异常让 worker 以 `waiting_input` 退出；恢复时命中 answered request 并返回 response。
4. 扩展 AgentRunner 结果处理：识别 `{"__loopflow":{"status":"waiting_input", ...}}` 控制对象；durable session 不足时失败为 `continue_not_supported`；自然语言文本保持普通输出。
5. 扩展执行器终态：`InterventionPending` 写 `waiting_input`、释放 lock；回答恢复沿用 execution options 和 epoch。
6. 实现 application/Web API：`GET /runs/{run_id}/interventions`、`POST /runs/{run_id}/interventions/{request_id}/response`，成功后启动同一 Run 恢复。
7. 更新 WebUI：waiting_input 展示 request prompt；boolean schema 显示布尔控件；提交后禁用直到 API 返回；不显示自由文本 Resume。
8. 替换 AC-022 的 11 个 manifest planned 节点；运行 recovery strict checker。
9. 运行 targeted tests、Python/前端/浏览器、MR gate、wheel smoke 和 scoped submission gate，回填 Report。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Request storage | pending/answered/closed 状态、digest、resume_mode 和事件完整 | Report: PASS |
| Workflow replay | answered response 只在相同 key/prompt/schema 处注入；漂移失败 | Report: PASS |
| Agent continue | durable session 才创建 request；回答后继续原 session | Report: PASS |
| API/UI | Interface 0001 endpoints、错误码、allowed_actions 和 Web 控件一致 | Report: PASS |
| Idempotency | 重复回答不覆盖、不重复启动 worker | Report: PASS |
| AC coverage | AC-022 11 个场景均有真实节点；recovery strict manifest 通过 | Report: PASS |
| Regression | AC-020/021、Python、frontend、browser、wheel 无回归 | Report: PASS |

# Review Points

1. 是否接受首版 schema 校验只覆盖 AC 所需 JSON Schema 子集。
2. 是否接受 request 文件位于 `run_dir/interventions/<request_id>.json`，其中 `request_id` 由 key 与 prompt/schema digest 稳定派生。
3. 是否接受 Agent intervention 首版只识别最终结构化输出，不解析流式文本或普通自然语言问题。

# Exit

全部 AC-022 场景有机器证据且不再使用 planned node、Report complete、MR gate 与 scoped submission gate 通过后，才能 squash 合并到 `develop`。AC-020/021/022 全部完成后，recovery strict manifest 必须通过。
