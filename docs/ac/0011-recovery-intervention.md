---
title: Reliable Recovery, Cancellation, and Intervention AC
description: 验收可校验前序恢复、失败/取消 Agent retry/continue、attempt 取消和阻塞人工回答
type: ac
status: active
created: 2026-07-22T06:35:57Z
---

本 AC 替代 AC-002-N-1、AC-002-N-2、AC-002-B-1、AC-002-E-1、AC-002-F-1、AC-003-N-3、AC-003-E-1、AC-014-N-3、AC-014-N-5、AC-014-N-6 和 AC-014-F-1 中与 resume/stop 生命周期冲突的预期；其他既有场景继续有效。

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
