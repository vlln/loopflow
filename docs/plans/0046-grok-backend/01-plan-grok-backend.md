---
title: Grok Backend Plan
description: 接入 Grok Build CLI headless 模式作为 loopflow Agent backend，并保持后端诊断和恢复能力声明一致
type: plan
status: done
created: 2026-07-22T00:00:00Z
---

# Goal

将 Grok Build CLI 接入 loopflow 后端管理体系，使 `agent(..., backend="grok")` 可以通过 `grok -p` headless 模式执行 Agent 调用，并解析 Grok `streaming-json` 输出中的文本、思考和 session id。

# Acceptance

本 Plan 覆盖 AC-008 后端管理的扩展场景：

`AC-008-N-2`：显式指定 `backend="grok"` 时使用 Grok backend，不影响已有后端。

`AC-008-B-2`：未注册后端仍报 unknown；`grok` 和兼容别名 `gork` 不应触发 unknown backend。

`AC-008-E-1`：Grok 二进制存在但认证或运行失败时仍通过现有 CLI transport 返回 exit code，由调用层按既有错误路径处理。

# Constraints

1. 继续复用现有 `CliBackend`，不引入网络依赖或 API transport。
2. 使用 Grok 官方 headless 单轮入口：`grok -p <prompt> --output-format streaming-json`。
3. `resume_session` 使用 Grok `--resume <session_id>`，并从 `end.sessionId` 解析 durable session id。
4. system prompt 处理遵循 Grok CLI 能力：`system_mode=overwrite` 使用 `--system-prompt-override`，默认追加语义使用 `--rules`。
5. 解析器只消费已文档化事件：`text`、`thought`、`end`、`error`；未知事件忽略但保留其中的 `sessionId`。
6. Web/API 后端列表继续以 `BACKEND_META` 为权威来源。
7. `gork` 只作为用户拼写兼容别名，官方文档列表使用 `grok`。

# Steps

1. 调用 `grok --help` 和 `grok agent --help`，确认 headless、resume、model、system prompt 与 output format 参数。
2. 查阅 `~/GithubProjects/grok-build` 文档，确认 `streaming-json` 事件格式和 `sessionId` 字段。
3. 新增 `GrokBackend(CliBackend)`，实现 create/resume 命令构造和 streaming-json 解析。
4. 在后端 manager 和 diagnostics 注册 `grok` 与 `gork`，补安装/认证提示。
5. 更新 README 后端列表。
6. 增加单元测试覆盖后端注册、capabilities 和 Grok streaming-json 解析。
7. 运行 targeted pytest 与 py_compile，回填 Report。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| CLI contract | `grok --help` 显示 `-p`、`--output-format streaming-json`、`--resume`、`--model`、`--system-prompt-override` | Report |
| Backend registration | `_make_backend("grok")` 和 `_make_backend("gork")` 均创建 GrokBackend | Unit test |
| Stream parsing | `text` 进入 text handler，`thought` 进入 thought handler，`end.sessionId` 进入 session handler | Unit test |
| Diagnostics | Web/API backend list 能展示 Grok CLI 状态 | Existing BackendRepository test path |
| Regression | 后端相关单测和语法检查通过 | Report |

# Exit

Plan 状态为 done、Report complete、targeted tests 通过后，本执行容器完成。后续如需验证真实 Grok 认证和完整 agent 调用，应在 system test 或手工验收中用有效 `grok login` / `XAI_API_KEY` 环境执行。
