---
title: loopflow AC-0010 — 本地 WebUI 控制台
description: 验收 Runs 主从工作台、AgentGraph 与 Call 过程、Loops 文件预览、Backend 诊断、SSE 恢复和本地安全边界。
type: ac
status: active
created: 2026-07-18T21:00:00Z
---

# AC-014: Runs 主从工作台

> 2026-07-22：AC-014-N-3、N-5、N-6、F-1 的 Run 操作预期已由 [AC-020 至 AC-022](0011-recovery-intervention.md) 替代；其他场景继续有效。

验证 Runs 列表与 Run 工作台在同一视图中持续协作。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-014-N-1 | fixture 含 running、failed、done、stopped 各 1 个 Run | 打开 WebUI，进入 Runs | 左栏同时显示 4 个 Run；默认选中最新 Run；中间和右侧显示该 Run 内容 | 自动化 |
| AC-014-N-2 | 左栏有 failed Run A 和 failed Run B，另有 done Run C；筛选为 failed | 选择 Run B，再选择 Run A | 只有 A、B 可见；URL/selection 更新；筛选条件保持 failed；详情原地切换，不导航到独立列表页 | 自动化 |
| AC-014-N-3 | Run A 为 running，Run B 为 failed | 分别选择 A、B | A 只显示 Stop；B 只显示 Resume，不同时显示互斥操作 | 自动化 |
| AC-014-N-4 | Loop hello 存在且 mock backend 可执行 | 在 WebUI 以 args={} 启动 hello | API 返回 201、Location 和 status=running 的新 Run；左栏出现相同 run_id | 自动化 |
| AC-014-N-5 | running Run A 的 mock 子进程持续运行 | 对 A 执行 Stop | 子进程收到终止信号；run.json 原子更新为 stopped；finished_at 非空且 pid 已清除 | 自动化 |
| AC-014-N-6 | failed Run A 有 1 个已完成缓存和 1 个未完成调用 | 对 A 执行 Resume | API 返回 status=running；已完成调用不执行，未完成调用执行；最终沿用 A 的 run_id | 自动化 |
| AC-014-N-7 | done Run A | 对 A 执行 Rerun | API 返回 201 和新 Run B；B.run_id != A.run_id，B.loop/args 与 A 相同，A 文件不变 | 自动化 |
| AC-014-N-8 | fixture 含 Loop 名和 run_id 可区分的 Runs | 分别应用 Loop 筛选和文本搜索 | 每次结果只包含匹配项；清除筛选后恢复完整列表 | 自动化 |
| AC-014-N-9 | WebUI New Run 对话框 | 用 Arguments 键值编辑器添加 `name=review`、`count=2`、`debug=true` 并启动 | POST body args 为 `{"name":"review","count":2,"debug":true}`（值智能类型解析：数字/布尔不包字符串） | 自动化 |
| AC-014-N-10 | Loop 的 loop.md 顶层声明 args（review 默认 main，count 无默认） | 打开 New Run 对话框并选择该 Loop | 键值编辑器预填 review=main 与空 count 行；直接启动时 POST args 只含 review=main | 自动化 |
| AC-014-N-11 | server 运行中 | `GET /api/v1/system/meta` 并观察 WebUI rail | 端点返回 200 `{"version": "..."}`（与 `loopflow.__version__` 一致）；rail 显示该版本而非硬编码值 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-014-B-1 | fixture 有 1000 个 Run | 连续滚动列表并选择第 1000 个 Run | 列表可到达目标项；选择后显示正确 run_id；主工作区宽度不因条目内容变化 | 自动化 |
| AC-014-B-2 | Runs 目录为空 | 打开 Runs | 左栏显示空状态；工作区不渲染伪造 Run；New Run 仍可用 | 自动化 |
| AC-014-B-3 | Arguments 键值编辑器含空 key 行 | 启动 Run | 空 key 行被忽略；args 仅含有效条目；无任何条目时 args 为 `{}` | 自动化 |
| AC-014-B-4 | Arguments 切换到 JSON 高级模式 | 输入非法 JSON 并启动 | 显示 JSON 校验错误，不发送请求 | 自动化 |
| AC-014-B-5 | loop.md 存在但无 args，workflow.py legacy meta.args 有值 | 打开 New Run 对话框 | loop.md 权威：编辑器为空白，不读取 workflow.py 声明 | 自动化 |
| AC-014-B-6 | Run 的 working_directory 为 `/home/user/bio-reproducer` | 查看 Runs 左栏该 run item | 次要标识行显示 `bio-reproducer`（working_directory 的 basename），不显示 run_id UUID；hover 显示完整路径 | 自动化 |
| AC-014-B-7 | Run 已记录 stale_since 且仍在 24h 宽限期，进程仍不存在 | 请求 reconcile | 返回 409 run_in_grace；run.json 除允许的首次 stale_since 记录外不改为 failed | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-014-E-1 | 一个 run.json 是非法 JSON，另一个合法 | 查询 Runs | 合法 Run 正常返回；非法条目作为 status=unreadable 的摘要返回并包含 parse_error；请求不返回 500 | 自动化 |
| AC-014-E-2 | Run status=running、进程不存在且 stale_since 缺失 | 首次选择该 Run，再刷新详情 | 首次读取原子记录 stale_since 并显示 stale；后续读取不重复改写；Stop 禁用且显示 Reconcile | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-014-F-1 | Run 为 done | 请求 stop 或 resume | API 返回 409；run.json 字节内容不变 | 自动化 |
| AC-014-F-2 | Run 为 stale，stale_since 已超过 24h，reconcile 二次校验仍 stale | 请求 reconcile | 返回 status=failed；run.json 原子替换且 pid/process_started_at/stale_since 已清除 | 自动化 |

---

# AC-015: AgentGraph 与 Agent Call 运行过程

> 2026-07-29：ADR-0052 删除 Phase 抽象。本节保留既有场景编号以维持追踪关系，但 oracle 已统一为 call_id 唯一节点、AgentGraph 和 Call 关联；不恢复 phase occurrence 或 declared phases。

验证 Agent 实例图、Call 选择和结构化事件关联。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-N-1 | v2 事件包含顺序 call-1(planner) → call-2(fixer) → call-3(reviewer) | 打开 Run | AgentGraph 有 3 个 call_id 节点、2 条 sequential edge、current=call-3；dagre rankdir=LR，edge 从左侧节点指向右侧节点 | 自动化 + 截图 |
| AC-015-N-2 | call-1 与 call-3 各有消息、工具调用和文件变化 | 依次选择两个图节点 | Events 与文件变化分别只高亮对应 call_id；右侧 Call 过程同步切换 | 自动化 |
| AC-015-N-3 | 结构化事件表达 call-a 后 parallel(call-b, call-c) 再 call-d | 打开 Run 并选择 b、c | b/c 是不同节点且各自事件不串线；图含 a→b/a→c fork edge 和 b→d/c→d join edge | 自动化 |
| AC-015-N-4 | 两组连续 parallel 产生 back-to-back fork/join，当前 call 为最后一组子节点 | 打开 Run | 所有 fork/join edge 均可见；current 只标记当前 call_id，未完成图也不出现孤立子节点 | 自动化 + 截图 |
| AC-015-N-5 | state.json 为 `{"attempt":2}`，选中 call-2 | 打开 Run Inspector 和 Call 详情 | Inspector 显示 attempt=2；Call 详情只显示结构化事件，不伪造 Call state diff | 自动化 |
| AC-015-N-6 | 新 Run 尚未产生 agent_start，Loop legacy meta.phases 非空 | 查询 RunDetail 并打开页面 | 响应含 agent_graph={nodes:[],edges:[],current:null}，不含 graph/occurrences/declared_phases；UI 不预造节点 | 自动化 |
| AC-015-N-7 | Run 随后产生 call-1 的 agent_start(label=采集) | 保持页面打开或重新加载 | 图新增唯一 call-1 节点并标记 running/current，不存在声明占位节点 | 自动化 |
| AC-015-N-8 | 两次顺序 Agent Call 的 label 都是 review，call_id 分别为 call-1/call-2 | 打开 Run | 图显示两个独立节点和 call-1→call-2 edge；不按同 label 合并或显示 occurrence | 自动化 + 截图 |
| AC-015-N-9 | Run 有 3 个 Call（call-1/call-2/call-3），每个含 session_id | 打开 Run，查看 Calls 列表 | call-list 主显 call_id；session_id 仅在 tooltip 显示，不作为独立行重复显示 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-B-1 | Run 没有 Agent 事件 | 打开 Run | AgentGraph 显示空状态；其他原始 Events 仍可查看；页面不崩溃 | 自动化 |
| AC-015-B-2 | Run 有 100 个顺序 Call | 选择第 1、100 个节点 | 全部节点可到达且顺序稳定；详情分别只显示目标 call_id 的事件 | 自动化 |
| AC-015-B-3 | Loop legacy meta.phases 非空，但 workflow 未调用 Agent 后 done | 查询 Loop/Run 并打开 Run | Loop/Run 响应不含 declared_phases；AgentGraph 为空；原始日志仍可见 | 自动化 |
| AC-015-B-4 | workflow 只完成一个 Agent Call | 打开 Run | 图只有一个 done 节点、无 edge；页面无 Phase filter、is-in-phase 样式或 PhaseGraph 控件 | 自动化 |
| AC-015-B-5 | Call 有 call_id 但 session_id 缺失 | 查看 Calls 列表 | 列表显示 call_id；tooltip 不显示 session 或显示 no session；不渲染空白行或报错 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-E-1 | legacy 并行事件缺少 call_id，无法唯一关联 | 打开 Run | 原始时间线可见；歧义事件标记 unattributed；不归入任一虚构 Call | 自动化 |
| AC-015-E-2 | v2 Agent 事件缺少 required call_id，另有一个合法 call-1 事件 | 查询 RunDetail 并打开 Run | `malformed == [{"reason":"missing_call_id","raw":<原坏事件>}]` 且 `malformed_count == len(malformed) == 1`；该 raw 事件不在合法 events、Call、AgentGraph 或 unattributed 中；合法 call-1 仍进入 AgentGraph | 自动化 |
| AC-015-E-3 | agent_start 的 label 为空或缺失，但 call_id=call-1 | 打开 Run | 节点仍以 call-1 存在并使用 call_id 作为可见 fallback label；页面不崩溃 | 自动化 |
| AC-015-E-4 | AgentGraph 有 5 个节点，当前选择第 3 个；EventTimeline 含 12 个事件 | 查看图、Call 详情和 EventTimeline | 图节点数、选中 call_id 和事件数分别准确显示，不混用 occurrence 术语 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-F-1 | events.jsonl 不存在 | 打开 Run | API 返回 Run 摘要、空 AgentGraph 和空事件集合；UI 显示无执行记录，不返回 500 | 自动化 |
| AC-015-F-2 | events.jsonl 最后一行仅写入一半 | 运行期间读取事件 | 完整行全部返回；半行暂不返回且后续补全后只返回一次 | 自动化 |
| AC-015-F-3 | workflow.py 语法错误 | 在 WebUI 启动 Run | API 返回 500 internal_error；不创建 Run、不渲染 Agent 节点；Loop 查询与服务继续可用 | 自动化 |
| AC-015-F-4 | legacy 事件缺少 call_id，无法关联到 Call | 查看 Calls 列表和原始 EventTimeline | 事件不出现在任何 Call 详情；原始时间线标记 unattributed；不显示虚构 Call；页面不崩溃 | 自动化 |

---

# AC-016: Run 事件流

验证 SSE 初次订阅、增量推送、断线续传和去重。

> 2026-07-23 追加：SSE 从单 topic（run_event）重构为多 topic transport（ADR-0041），新增 `file_changes` topic。AC-016-N-3/N-4、AC-016-B-3、AC-016-E-3 验证多 topic 场景。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-N-1 | Run 已有 event_id 1..10 | 不带游标订阅 SSE | 按 1..10 重放 `event: run_event`，之后连接保持并推送新事件 11 | 自动化 |
| AC-016-N-2 | 客户端已收到 event_id=7 后断线 | 以 last_event_id=7 重连 | 只返回 8 及之后 `event: run_event`；客户端集合无重复 event_id | 自动化 |
| AC-016-N-3 | events.jsonl 有 event_id 1..5，file_changes.jsonl 有 seq 1..3 | 不带游标订阅 SSE | 同一连接收到 `event: run_event`（id 1..5）和 `event: file_changes`（id 1..3），各自 `id:` 独立递增 | 自动化 |
| AC-016-N-4 | 客户端已收到 run_event id=5、file_changes id=2 后断线 | 以 last_event_id=5&last_file_changes_id=2 重连 | run_event 只推 id>5，file_changes 只推 id>2；两个 topic 独立游标 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-B-1 | Run 已结束，最后 event_id=10 | 以 last_event_id=10 订阅 | 不重放旧事件；服务发送 `event: stream_end`（data 含 last_event_id=10）后关闭连接 | 自动化 |
| AC-016-B-2 | 100 条 1KB 事件连续落盘，单客户端订阅 | 记录落盘到 SSE 可读延迟 | p95 < 500ms，event_id 顺序严格递增 | 自动化 |
| AC-016-B-3 | Run 已结束（run_event terminal），file_changes.jsonl 仍有未推送数据 | 订阅 SSE | `stream_end` 不发送，直到 file_changes topic 也 terminal；file_changes 数据继续推送 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-E-1 | 服务端最大 event_id=10，客户端以 last_event_id=11 订阅 | 订阅 SSE | 返回 410 JSON；body.error.code=`cursor_out_of_range`、body.error.details.max_event_id=10 | 自动化 |
| AC-016-E-2 | 客户端重复收到同一 event_id | 应用前端事件 reducer | 状态只应用一次，不重复增加 Call 消息或边计数 | 自动化 |
| AC-016-E-3 | file_changes.jsonl 最大 seq=2，客户端以 last_file_changes_id=99 订阅 | 订阅 SSE | file_changes topic 返回 `event: stream_error`（data 含 topic=file_changes, code=cursor_out_of_range）；run_event topic 不受影响，正常推送 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-F-1 | run_id 不存在 | 订阅 SSE | 返回 404，连接不进入重试循环 | 自动化 |
| AC-016-F-2 | 注入 event reader，使订阅已发送 event_id=5 后下一次读取抛 `OSError("fixture-read-failed")` | 保持 SSE 连接并触发下一次读取 | 服务发送 `event: stream_error`，data.code=`event_read_failed`、data.last_event_id=5，随后关闭；不发送 event_id>5 | 自动化 |
| AC-016-F-3 | file_changes.jsonl 读取抛 `OSError("fixture-read-failed")`，events.jsonl 正常 | 保持 SSE 连接 | 服务发送 `event: stream_error`（data.code=`event_read_failed`、data.last_event_id=当前 run_event 游标，无 topic 字段），随后关闭连接；失败前已推送的 run_event/file_changes 数据不重复 | 自动化 |

---

# AC-017: Loops 工作区与文件预览

验证 Loop 主从浏览和文件系统安全边界。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-017-N-1 | 有两个合法 Loop | 打开 Loops 并选择第二项 | 左栏保留两个 Loop；右侧原地显示第二个 Loop 的 Overview | 自动化 |
| AC-017-N-2 | Loop 含 loop.md、workflow.py、agents/reviewer.md、chart.png、report.pdf | 打开文本和二进制文件 | Markdown 被渲染、Python 只读、Agent 定义可查看；图片用 img、PDF 用 iframe/raw viewer；raw bytes 不转码，chart.png 返回 `Content-Type: image/png`，report.pdf 返回 `Content-Type: application/pdf` | 自动化 |
| AC-017-N-3 | Run file changes 含 chart.png 和 report.pdf | 依次选择两文件 | preview 返回 encoding=raw/raw_url；图片和 PDF 在 Run 文件面板可见且不作为文本解码 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-017-B-1 | agents 目录为空 | 打开 Agents | 显示 0 Agents 空状态，不显示错误 | 自动化 |
| AC-017-B-2 | 文件是非白名单二进制，或文本超过 1 MiB，或白名单 raw 超过 50 MiB | 请求预览 | 返回 422 file_not_previewable，不返回 content 或部分 bytes | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-017-E-1 | 请求路径为 `../../etc/passwd` | 请求 Loop 文件 | 返回 403；响应不包含目标文件内容 | 自动化 |
| AC-017-E-2 | Loop 内符号链接指向根目录外 | 请求该链接 | resolve 后拒绝，返回 403 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-017-F-1 | Loop 在列表加载后被删除 | 请求详情 | 返回 404；左栏刷新后移除该项；其他 Loop 保持可用 | 自动化 |
| AC-017-F-2 | loop.md YAML 非法 | 查询 Loops | 该 Loop 标记 invalid 并提供解析错误摘要；服务不退出 | 自动化 |
| AC-017-F-3 | raw 文件通过路径/大小校验，但完整读取抛 OSError | 请求 Run 或 Loop raw URL | 返回 500 file_read_failed；不得先发送 200 headers 或部分 bytes；UI 显示可读失败态 | 自动化 |

---

# AC-018: Backends 工作区

验证后端列表、能力和诊断日志只来自真实诊断结果。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-018-N-1 | mock BackendManager 返回 2 个可用、1 个缺失 | 查询 Backends | 返回 3 项及真实 status、CLI path、version、capabilities、transport | 自动化 |
| AC-018-N-2 | backend 诊断 stderr 为 `token=lf-secret-123; connection failed`，exit_code=1 | 选择该 Backend | 详情显示诊断时间、exit_code 和 `token=[REDACTED]; connection failed`；API 和 DOM 均不含 `lf-secret-123` | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-018-B-1 | 未发现任何 Backend | 打开 Backends | 显示空状态和诊断入口，不显示健康百分比 | 自动化 |
| AC-018-B-2 | Backend 无法报告版本 | 查询 Backends | API version 为 null，UI 显示 `Unknown`；其他能力仍显示 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-018-E-1 | 诊断进程超过 fixture timeout=100ms | 执行诊断 | Backend 返回 status=unavailable、reason=timeout；日志包含 `diagnostic timed out after 100ms`；其他 Backend 继续诊断 | 自动化 |
| AC-018-E-2 | 诊断输出非法编码 | 查看日志 | 使用替换字符安全显示；API 不返回 500 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-018-F-1 | backend 名不存在 | 请求单项诊断 | 返回 404，不启动任意命令 | 自动化 |
| AC-018-F-2 | 诊断进程无法启动 | 执行诊断 | 返回 503 和错误摘要；不伪造 latency、VRAM 或健康分数 | 自动化 |

---

# AC-019: WebUI 布局与可访问性

验证规范视口下的结构稳定性和核心键盘路径。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-019-N-1 | 1440x900 视口，Runs fixture 已加载 | 截图并检查布局 | Runs、AgentGraph/Events、Inspector 同时可见；AgentGraph 节点按 LR 排列且 edge 不穿过无关节点；无重叠或水平页面滚动 | 自动化 + 截图 |
| AC-019-N-2 | Runs 工作区打开，焦点置于 failed Run A；A 含 call-1/call-2；DOM 区域顺序为 Runs→AgentGraph→Calls→Run actions | 用键盘选择 A、call-1，再聚焦 accessible name=`Retry failed call` 并按 Enter | 每步有可见 focus；详情依次显示 A 和 call-1；最后只发出一次 A 的 recover retry 请求 | 自动化 |
| AC-019-N-3 | 启动 Web 服务时未传 host | 检查监听 socket | 仅监听 `127.0.0.1`，不监听 `0.0.0.0` 或外部接口 | 自动化 |
| AC-019-N-4 | 本机测试接口地址为 `0.0.0.0` | 以 host=`0.0.0.0` 且 allow-remote=true 启动服务 | 服务启动成功并监听 `0.0.0.0`；stderr 输出远程暴露警告 | 自动化 |
| AC-019-N-5 | WebUI 已打开 | 点击 rail 主题切换按钮，然后刷新页面 | 日夜主题切换；选择持久化（刷新后保持）；未做过选择时默认跟随系统 `prefers-color-scheme` | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-019-B-1 | 1024x768 视口 | 打开 Run | 主列表和 AgentGraph 工作区可用；Inspector 收入可打开/关闭的抽屉；文本不重叠 | 自动化 + 截图 |
| AC-019-B-2 | 390x844 视口 | 在 Runs、AgentGraph、Call process 间切换 | 一次只显示一个主区域；当前 Run 的允许操作可到达；无水平页面滚动 | 自动化 + 截图 |
| AC-019-B-3 | light 主题 | 打开 Runs 工作区 | 面板背景与前景文字为不同色；status 徽章文字与图标可辨；无白底白字或黑底黑字区域 | 自动化 + 截图 |
| AC-019-B-4 | failed Run 的 error_summary 超过 2 行文本（如多行 schema 校验错误） | 查看该 Run 详情 | error_banner 的 error_summary 文本截断为 2 行（-webkit-line-clamp），不挤占 AgentGraph 工作区和 Inspector；Traceback 折叠条仍可展开查看完整信息 | 自动化 + 截图 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-019-E-1 | Agent 输出含 500 字符无空格字符串 | 显示 Output | Output 使用 `overflow-wrap:anywhere` 在面板内换行；页面无水平滚动且不遮挡相邻面板 | 自动化 + 截图 |
| AC-019-E-2 | SSE 连接断开 | 观察顶栏和现有内容 | 显示连接中断状态；最后数据保留；重连不导致面板闪烁或尺寸变化 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-019-F-1 | 图标按钮无可见文字 | 扫描可访问性树 | 每个按钮都有 accessible name；陌生图标有 tooltip | 自动化 |
| AC-019-F-2 | 状态颜色样式被禁用 | 查看 Runs、Agent Call 和 Backend 状态 | 每个状态仍可由文字或图标区分 | 自动化 |
| AC-019-F-3 | 启动 Web 服务时传 host=`0.0.0.0`，但未传显式 allow-remote 配置 | 启动服务 | 启动失败并返回非零状态；stderr 包含 `remote binding requires explicit opt-in` | 自动化 |
