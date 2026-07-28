---
title: Reliable Recovery, Cancellation, and Intervention AC
description: 验收可校验前序恢复、失败/取消 Agent retry/continue、attempt 取消和阻塞人工回答
type: ac
status: proposed
created: 2026-07-22T06:35:57Z
---

本 AC 替代 AC-002-N-1、AC-002-N-2、AC-002-B-1、AC-002-E-1、AC-002-F-1、AC-003-N-3、AC-003-E-1、AC-014-N-3、AC-014-N-5、AC-014-N-6 和 AC-014-F-1 中与 resume/stop 生命周期冲突的预期；其他既有场景继续有效。

> 2026-07-23：AC-023 定义 Agent structured intervention vNext。AC-022 中 schema/单 request/单 respond 语义在 vNext 实现后由 AC-023 替代；在实现迁移前继续作为当前产品行为证据。

# AC-020: 可校验恢复

验证成功 Call 重放、失败 Call 重跑以及恢复分歧检测。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-020-N-1 | failed Run A 有 Call 0001 的 succeeded 缓存和 Call 0002 的 failed 缓存；两者 input_digest 与当前调用一致 | 对 A 执行 recover mode=retry | 沿用 A.run_id；0001 返回缓存且不调用 backend；0002 创建新 session 执行；Run 最终 done | 自动化 |
| AC-020-N-2 | failed Run A 的目标 Call 已持久化 session_id，backend capabilities 含 resume_session=true、durable_session_id=true | 对 A 执行 recover mode=continue | 前序成功 Call 返回缓存；目标 Call 使用原 session_id 调用 resume_session；不创建新 session | 自动化 |
| AC-020-N-3 | 顺序 Call 成功完成 | 检查 `<call-id>.jsonl` | agent_start 含 call_id/input_digest；agent_done 含 call_id/status=succeeded/session_id/exit_code=0；输出仍由 message 事件提取 | 自动化 |
| AC-020-N-4 | failed Run A 的 backend 支持 durable session，failed Run B 不支持 | 在 WebUI 分别选择 A、B | A 显示 Retry 和 Continue；B 显示 Retry 且 Continue 禁用并说明原因；均不显示 Resume | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-020-B-1 | parallel 含三个 Call，执行完成顺序为分支 2、0、1 | 首次运行失败后 recover | 三个分支的 call_id 由输入位置稳定分配；恢复不因完成顺序变化而串用缓存 | 自动化 |
| AC-020-B-2 | 旧 Run 缓存没有 input_digest/status，但含 exit_code=0 | 执行 legacy retry | 允许按旧规则恢复并标记 unverified；continue 不可用；原缓存不迁移 | 自动化 |
| AC-020-B-3 | failed Run 使用旧 CLI `resume` 命令 | 执行 resume | 作为 deprecated recover --mode retry 执行并输出弃用提示；stopped Run 使用相同命令失败 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-020-E-1 | Call 0001 有 succeeded 缓存，但当前规范化输入 digest 不同 | 执行任一 recover mode | 返回 409 replay_diverged；不返回缓存、不调用 backend、不覆盖旧文件 | 自动化 |
| AC-020-E-2 | failed Call 有 session_id，但 backend 不声明 durable_session_id | 执行 recover mode=continue | 返回 409 continue_not_supported；不创建新 session；retry 仍可单独执行 | 自动化 |
| AC-020-E-3 | recover 重放时 `random`、时间或外部读取令同一 call_id 产生不同规范化输入 | 到达该 Call | 返回 replay_diverged；不返回旧缓存或执行新调用 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-020-F-1 | `<call-id>.jsonl` 最后一行损坏或没有 succeeded agent_done | 执行 recover mode=retry | 该 Call 视为未提交并创建新 session；前序合法缓存仍命中 | 自动化 |
| AC-020-F-2 | 同一 failed Run 已有恢复 worker 持有 Run 锁 | 再次提交 recover | 返回 409 invalid_run_transition；只存在一个有效 execution_epoch | 自动化 |
| AC-020-F-3 | recover 的目标是失败 Call 0003，但 workflow 重放在 0003 前提前返回 | 执行 recover | Run 变为 failed，错误为 replay_diverged；不得标记 done | 自动化 |

---

# AC-021: 可靠停止

验证 stop 取消当前 execution attempt，并且并发退出不能覆盖取消状态。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-021-N-1 | running Run A 的 workflow 和 backend 子进程均存活 | 对 A 执行 stop | 先持久化 cancelling；进程组收到 SIGTERM；最终 status=cancelled、finished_at 非空、pid 被清除 | 自动化 |
| AC-021-N-2 | Run A 为 waiting_input 且没有存活 worker，request R 为 pending | 对 A 执行 stop | 不要求 PID；A 原子变为 cancelled；R 仍为 pending；allowed_actions 包含 respond，不把用户未回答解释为放弃 Run | 自动化 |
| AC-021-N-3 | cancelled Run A 有前序 succeeded 缓存和取消点 Call 0002；两者 input_digest 与当前调用一致 | 对 A 执行 recover mode=retry | 沿用 A.run_id；前序缓存命中；0002 创建新 session 重新执行；Run 进入 running 并递增 execution_epoch | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-021-B-1 | backend 忽略 SIGTERM | 对 Run 执行 stop 并等待 grace period | grace period 后向进程组发送 SIGKILL；Run 最终 cancelled | 自动化 |
| AC-021-B-2 | legacy Run status=stopped | 查询 Run 和 allowed_actions | Run 可读；不提供 recover；可提供 rerun | 自动化 |
| AC-021-B-3 | running Run A 的 active worker 声明 atomic/isolated，且已持久化 durable session_id | 对 A 执行 stop 后再 recover mode=continue | 返回 409 continue_not_supported；不恢复原 session；recover mode=retry 仍可单独执行 | 自动化 |
| AC-021-B-4 | running Run A 的 active worker 非 atomic，且 backend/session 均支持 durable continue | 对 A 执行 stop 后再 recover mode=continue | 目标 Call 使用原 session_id 调用 resume_session；不创建新 session | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-021-E-1 | stop 已将 A 写为 cancelling，旧 worker 随后尝试写 done | 完成竞态 | worker 因 execution_epoch/terminal guard 被拒绝；A 最终 cancelled | 自动化 |
| AC-021-E-2 | A 已 cancelled 且没有可重放边界或 pending request | 对 A 执行 recover 或 respond | 返回 409 invalid_run_transition 或具体恢复错误；run.json 不被错误标记为 done | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-021-F-1 | 持久化 cancelling 失败 | 执行 stop | 返回 500 atomic_write_failed；不向进程发送信号，避免产生未记录的终止 | 自动化 |
| AC-021-F-2 | 持久化取消成功后进程身份已变化 | 继续 stop | 不向复用 PID 的无关进程发信号；Run 最终 cancelled，并记录 process_gone 摘要 | 自动化 |

---

# AC-022: 阻塞人工介入

验证请求持久化、worker 释放、回答校验和回答后的确定性重放。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-022-N-1 | workflow 调用 `intervene(key="approve", prompt="Approve?", schema={"type":"boolean"})`，尚无 response | 运行 workflow | request 原子持久化；追加 intervention_requested；Run 变为 waiting_input；worker 退出且释放执行锁 | 自动化 |
| AC-022-N-2 | A 为 waiting_input，request R 未回答 | 对 R 提交 boolean `true` | response 持久化；追加 intervention_responded；A 自动恢复；重放到相同 key 时返回 true；A.run_id 不变 | 自动化 |
| AC-022-N-3 | Agent 结构化请求人工输入且缓存含 durable session_id | 回答 request | 前序 Call 返回缓存；目标 Call 使用回答恢复原 backend session；自然语言文本不用于推断请求 | 自动化 |
| AC-022-N-4 | Run A 为 waiting_input，request schema 为 boolean | 在 WebUI 选择 A | 展示 request prompt 和布尔输入控件；不展示自由文本 Resume；提交后按钮禁用直到响应完成 | 自动化 |
| AC-022-N-5 | A 原为 waiting_input，随后被 stop 为 cancelled，request R 仍 pending | 对 R 提交 boolean `true` | response 持久化；A 自动恢复同一 run_id；重放到相同 key 时返回 true | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-022-B-1 | Web 服务在 Run waiting_input 期间重启 | 重启后查询 request 并回答 | request 仍可读取；回答后同一 Run 恢复，不依赖旧进程内存 | 自动化 |
| AC-022-B-2 | request schema 为 null | 提交任意 JSON 值 | 值作为 immutable response 接受并在重放时原样返回 | 自动化 |
| AC-022-B-3 | A 为 cancelled 且含 pending request R；用户不提交 response | 查询 Run 和 request | A 保持 cancelled；R 保持 pending；框架不自动关闭 request，也不把该状态建模为 abandon | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-022-E-1 | request schema 要求 boolean | 提交字符串 `"yes"` | 返回 422 validation_failed；request 保持未回答；不启动恢复 worker | 自动化 |
| AC-022-E-2 | response 已提交 | 再次提交相同或不同值 | 返回 409 intervention_already_answered；原 response 不变；不重复启动恢复 | 自动化 |
| AC-022-E-3 | Agent 返回结构化 intervention，但没有 durable session_id | 处理 Agent 结果 | Call/Run 以 continue_not_supported 失败；不创建无法继续的 pending request | 自动化 |
| AC-022-E-4 | Run A 存在但 request R 不存在 | 对 R 提交 response | 返回 404 intervention_not_found；Run/request 集合不变；不启动恢复 worker | 自动化 |
| AC-022-E-5 | Run A 当前不是 waiting_input/cancelled，但存在 pending request R | 对 R 提交 response | 返回 409 invalid_run_transition；R 保持 pending 且 response 不落盘；不启动恢复 worker | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-022-F-1 | workflow 重放时相同位置产生不同 intervention key 或 prompt digest | 回答后自动恢复 | Run 变为 failed，错误为 replay_diverged；不把旧 response 注入新请求 | 自动化 |
| AC-022-F-2 | Agent 仅在自然语言输出中提出问题，没有结构化请求 | Agent 正常返回 | loopflow 不创建 intervention；结果按普通 Agent 输出处理 | 自动化 |

---

# AC-023: Agent structured intervention vNext

验证 Agent 结构化多问题、预设选项、自定义回答、批量提交和 workflow routing gate 的职责边界。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-023-N-1 | Agent 返回 `__loopflow.status=waiting_input`，含两个 requests，backend 已持久化 durable session_id | 运行 workflow | 两个 request 原子持久化；`source=agent`、`resume_mode=continue`、response 类型为 string；Run 进入 waiting_input；worker 退出且释放执行锁 | 自动化 |
| AC-023-N-2 | A 为 waiting_input，两个 agent requests 均 pending，分别含 options/custom 约束 | 对 A 执行 batch respond，提交两个 string responses | responses all-or-nothing 持久化；只启动一次恢复 worker；同一 Agent session 收到回答继续执行；A.run_id 不变 | 自动化 |
| AC-023-N-3 | workflow 调用 `intervene(key, prompt, options=[...], allow_custom=False)` | 运行 workflow 并回答一个 option | request `source=workflow`、`resume_mode=replay`；重放到同一 key 后 answer 返回给 workflow；workflow 根据 answer 进入对应分支 | 自动化 |
| AC-023-N-4 | CLI `loopflow run` 与 Web `POST /runs` 执行同一含 `intervene()` 的 workflow | 分别运行 | 两条入口均注入 `intervene`，均进入 waiting_input，而不是把 `intervention_pending` 记录为 failed | 自动化 |
| AC-023-N-5 | Run A 有多个 pending requests | 在 WebUI 选择 A | 显示多问题表单；每个 request 展示 prompt、options 和可选手动输入；用户填写全部后一次提交 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-023-B-1 | 并行 Agent worker 同时产生 pending requests | 查询 Run interventions | 所有 pending requests 可读；request_id 稳定且不互相覆盖；Run allowed_actions 包含 respond | 自动化 |
| AC-023-B-2 | request `allow_custom=true` 且 options 非空 | batch respond 提交非 options 的非空 string | response 被接受并持久化 | 自动化 |
| AC-023-B-3 | request `allow_custom=false` 且 options 只有一个值 | batch respond 提交该 option | response 被接受并持久化 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-023-E-1 | request `allow_custom=false` 且 options 不包含 `"other"` | batch respond 提交 `"other"` | 返回 422 validation_failed；所有 responses 均不落盘；不启动恢复 worker | 自动化 |
| AC-023-E-2 | batch respond 中一个 request 已 answered | 提交 batch | 返回 409 intervention_already_answered；所有 responses 均不覆盖/不落盘；不启动恢复 worker | 自动化 |
| AC-023-E-3 | batch respond 中一个 request_id 不存在 | 提交 batch | 返回 404 intervention_not_found；所有 responses 均不落盘；不启动恢复 worker | 自动化 |
| AC-023-E-4 | Run 当前不是 waiting_input/cancelled | 提交 batch | 返回 409 invalid_run_transition；所有 requests 不变；不启动恢复 worker | 自动化 |
| AC-023-E-5 | Agent structured request 缺 key/prompt，或 options 含非 string | 处理 Agent 结果 | Call/Run failed，错误为 validation_failed；不创建 pending request | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-023-F-1 | Agent 返回自然语言问题但无结构化 requests | Agent 正常返回 | loopflow 不创建 intervention；结果按普通 Agent 输出处理 | 自动化 |
| AC-023-F-2 | Agent requests 需要 continue，但 durable session_id 未落盘 | 处理 Agent 结果 | Call/Run 以 continue_not_supported 失败；不创建无法继续的 pending request | 自动化 |
| AC-023-F-3 | batch respond 持久化成功后恢复 worker 失败 | 提交 batch | responses 保持 answered；后续失败按普通 Run execution failure 表达，不创建 intervention 特殊状态 | 自动化 |

---

# AC-026: Agent 失败分类处理

验证失败分类驱动的重试/续接策略的正确性。对应 Spec v15 BR-049、ADR-0044。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-026-N-1 | mock 后端第 1 次调用返回 transient 失败（stderr 含 "rate_limit"），第 2 次成功 | 执行含该 agent() 的 workflow | 自动退避重试后成功返回；events.jsonl 含 agent_retry 事件（attempt/reason/delay）；agent_done 的 error_category 缺省或 transient | 自动化 |
| AC-026-N-2 | 后端结构化上报 error_category=quota，同时 stderr 含 "timeout" 字样 | 执行含该 agent() 的 workflow | 按 quota 处理：不自动重试（无 agent_retry 事件），结构化上报优先于 stderr 模式匹配 | 自动化 |
| AC-026-N-3 | agent 调用失败（任意类别） | run 失败后检查 run.json 与 agent_done 事件 | run.json 的 error_category 与 agent_done payload 的分类一致，值为 auth/quota/transient/task/unknown 之一 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-026-B-1 | 后端上报 auth 失败（如凭证过期） | 执行含该 agent() 的 workflow | 不自动重试，run 直接 failed，error_category=auth | 自动化 |
| AC-026-B-2 | 失败信息无法匹配任何已知类别 | 执行含该 agent() 的 workflow | error_category=unknown，按 task 处理：不自动重试 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-026-E-1 | transient 失败连续 3 次重试均失败 | 执行含该 agent() 的 workflow | 抛 AgentError（含 category=transient），run failed；agent_retry 事件共 3 条，退避间隔 3/9/27s | 自动化 |
| AC-026-E-2 | agent 返回合法 JSON 但 schema 校验失败（如 `decisions` 应为对象数组但返回字符串数组），兜底也无法转换，连续 max_retries 次均如此 | 执行含该 agent() 的 workflow | 抛 AgentError，消息中包含最后一次的 schema 校验错误 + 兜底失败原因（字段路径 + 期望类型 + 兜底尝试）；run.json 的 error_summary 包含该错误列表 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-026-F-1 | 后端上报 quota 失败 | run 失败后尝试 recover --mode continue | 按既有 continue 规则处理（durable session 满足则可续接），分类不改变恢复边界 | 自动化 |

> 2026-07-27 追加（BL-031）：retry hint 携带具体 schema 校验错误 + 框架类型兜底。E-2 插入既有异常表，N-5 新增正常场景，B-3/E-3 新增场景如下。

### 正常场景（追加）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-026-N-5 | agent 返回 `{"score": "95"}`，schema 要求 `score` 为 number 且无值约束 | 检查 agent() 返回值 | 框架兜底 + 二次校验成功，返回 `{"score": 95.0}`（number），不触发 retry | 自动化 |

### 边界场景（追加）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-026-B-3 | agent 返回 `{"score": "95"}`，schema 要求 `score` 为 number 且 `maximum: 10` | 检查 agent() 行为 | 兜底类型转换成功（"95"→95），但二次校验值约束失败（95 > 10），触发 retry；hint 包含类型转换成功 + 值约束失败两个错误 | 自动化 |

### 异常场景（追加）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-026-E-3 | agent 返回合法 JSON 但 schema 校验失败（字段 `verdict` 应为 enum `[REPRODUCED, PARTIAL, FAILED, BLOCKED]` 但返回 `"pass"`），兜底也失败 | 检查 retry hint | hint 包含具体字段路径（`verdict`）、期望类型、实际值、兜底尝试结果；hint 不包含 "not valid JSON" 措辞 | 自动化 |

---

# AC-029: stale 失联宽限期

验证 stale 宽限期与调和语义的正确性。对应 Spec v15 BR-052、ADR-0046。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-029-N-1 | run 状态 running，其 pid/process_started_at 探活失败（首次判定 stale） | 通过 API 读取该 run | 读模型返回 stale；run.json 原子写入 stale_since（首次判定时间） | 自动化 |
| AC-029-N-2 | AC-029-N-1 之后，宽限期内 worker 进程恢复并写入终态（done/failed） | 读取 run.json | 以 worker 写入的终态为准，stale_since 已清除 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-029-B-1 | run 处于 stale 且 stale_since 距今不足 24h（宽限期内） | `POST /api/v1/runs/{id}/reconcile` | 返回 409，错误码 run_in_grace；run.json 未被修改 | 自动化 |
| AC-029-B-2 | run 处于 stale 且 stale_since 距今超过 24h | `POST /api/v1/runs/{id}/reconcile` | 按既有 reconcile 流程：status=failed、写 error_summary、清除 pid 字段与 stale_since | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-029-E-1 | run.json 已含 stale_since，再次读取仍为 stale | 连续两次读取该 run | stale_since 保持首次值不被刷新 | 自动化 |
| AC-029-E-2 | legacy run（无 stale_since 字段）判定 stale | 读取该 run | 按首次判定处理：写入 stale_since，行为与 AC-029-N-1 一致 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-029-F-1 | run 状态非 stale（进程存活） | `POST /api/v1/runs/{id}/reconcile` | 返回 409 run_not_stale（既有行为不变） | 自动化 |

---

> 2026-07-28 追加（BL-044/045，ADR-0056）：waiting_input 生命周期扩展——CLI 应答通道与无人值守策略。

# AC-031: waiting_input CLI 应答与无人值守

验证 CLI 前台内联应答、`loop respond` 命令、intervene default/timeout 与 `--unattended` 模式。对应 Spec v17 BR-059/060/061、ADR-0056。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-031-N-1 | workflow 调用 `intervene(key="approve", prompt="继续？", options=["继续","停止"], allow_custom=False)`；CLI 前台 tty 运行 | 执行 `loopflow run`，在终端提问中选择"继续" | 终端内联展示 prompt 与编号选项；回答经应用层校验落盘（response_source=human）；同一 run_id 恢复重放，intervene 返回"继续"；Run 最终 done | 自动化 |
| AC-031-N-2 | Run A 为 waiting_input，request R 为 pending（后台或非前台产生） | 执行 `loopflow respond <A.run_id>` 并交互回答 | response 持久化；A 自动恢复同一 run_id；重放到相同 key 时返回回答 | 自动化 |
| AC-031-N-3 | workflow 调用 `intervene(..., default="继续")`；以 `--unattended` 运行 | 执行 `loopflow run --unattended` | Run 不进入 waiting_input；请求以 default 回答（response_source=default）；workflow 拿到 default 继续至终态 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-031-B-1 | request R pending，`created_at + timeout` 已过，声明了 default | 对 Run 执行 recover | R 自动以 default 回答（response_source=timeout_default），重放返回 default；无需任何常驻进程触发 | 自动化 |
| AC-031-B-2 | CLI 前台内联提问且声明了 timeout/default | 不输入，等待倒计时结束 | 超时后自动取 default 继续；回答落盘 response_source=timeout_default | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-031-E-1 | `intervene(options=["a","b"], allow_custom=False, default="c")` | 运行 workflow | 调用即抛 ValueError（default 未通过 options 校验）；Run failed；不创建 request | 自动化 |
| AC-031-E-2 | `intervene(timeout=60)` 未声明 default | 运行 workflow | 调用即抛 ValueError（timeout 依赖 default）；不创建 request | 自动化 |
| AC-031-E-3 | workflow 调用无 default 的 `intervene()`；以 `--unattended` 运行 | 执行 `loopflow run --unattended` | Run 以 `intervention_unattended` 失败；不进入 waiting_input；不创建 request（unattended 冻结后 recover 亦无人应答，pending 无意义） | 自动化 |
| AC-031-E-4 | CLI 前台运行但 stdin 非 tty，未声明 `--unattended` | 执行 `loopflow run`（stdin 重定向） | 打印 pending 请求数、run_id、`loop respond <run-id>` 与 WebUI 应答入口后以 waiting_input 退出；不隐式失败、不隐式取 default | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-031-F-1 | request R 已 pending，workflow 修改 default 或 timeout 后 recover | 执行 recover | Run failed，错误 replay_diverged；不把旧请求与新参数混用 | 自动化 |
| AC-031-F-2 | CLI 内联提问 `allow_custom=false`，用户输入 options 之外的值 | 交互应答 | 提示校验失败并重新提问；非法回答不落盘、不触发恢复 | 自动化 |
