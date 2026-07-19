---
title: loopflow AC-0010 — 本地 WebUI 控制台
description: 验收 Runs 主从工作台、Phase occurrence、Loops 文件预览、Backend 诊断、SSE 恢复和本地安全边界。
type: ac
status: active
created: 2026-07-18T21:00:00Z
---

# AC-014: Runs 主从工作台

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

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-014-B-1 | fixture 有 1000 个 Run | 连续滚动列表并选择第 1000 个 Run | 列表可到达目标项；选择后显示正确 run_id；主工作区宽度不因条目内容变化 | 自动化 |
| AC-014-B-2 | Runs 目录为空 | 打开 Runs | 左栏显示空状态；工作区不渲染伪造 Run；New Run 仍可用 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-014-E-1 | 一个 run.json 是非法 JSON，另一个合法 | 查询 Runs | 合法 Run 正常返回；非法条目作为 status=unreadable 的摘要返回并包含 parse_error；请求不返回 500 | 自动化 |
| AC-014-E-2 | Run status=running，但进程不存在 | 选择该 Run | UI 显示 stale；Stop 禁用；显示 Reconcile；读取操作不修改 run.json | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-014-F-1 | Run 为 done | 请求 stop 或 resume | API 返回 409；run.json 字节内容不变 | 自动化 |
| AC-014-F-2 | Run 为 stale，reconcile 二次校验仍为 stale | 请求 reconcile | API 返回更新后 status=failed 的 Run；run.json 原子替换且 pid/process_started_at 已清除 | 自动化 |

---

# AC-015: Phase 与 Agent 运行过程

验证聚合 Phase 图、Phase occurrence 和 Agent Call 关联。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-N-1 | v2 事件包含 `Review(p1) → Fix(p2) → Review(p3)` | 打开 Run | 图有 Review、Fix 两个聚合节点和 Fix→Review 回边；Review 显示 2 个 occurrence | 自动化 |
| AC-015-N-2 | p1 关联 call-1，p3 关联 call-3 | 依次选择 p1、p3 | Calls/Events 分别只显示 call-1、call-3；右侧过程同步切换 | 自动化 |
| AC-015-N-3 | 一个 Phase 内两个并行 Call 的事件均有 call_id | 选择该 occurrence | 两个 Call 分开显示；各自消息、工具调用、重试和 done 不串线 | 自动化 |
| AC-015-N-4 | 事件形成 `Plan→Implement` 和 `Plan→Review` 两个分支，当前 phase_id 属于 Review | 打开 Run | 聚合图同时显示两条分支；Review 路径标记 current，另一条路径降低权重但仍可选择 | 自动化 + 截图 |
| AC-015-N-5 | state.json 为 `{"attempt":2}`，选中 Review occurrence | 打开 Run Inspector 和 Phase 详情 | Run Inspector 显示 attempt=2；Phase 详情只有 Calls/Events，不出现 Phase State 或伪造 state diff | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-B-1 | Run 没有 phase 事件 | 打开 Run | Phase 区显示空状态；原始 Events 仍可查看；页面不崩溃 | 自动化 |
| AC-015-B-2 | Phase 有 100 次 occurrence | 选择聚合节点并切换第 1、100 次 | occurrence 可选择且顺序稳定；右侧关联结果正确 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-E-1 | legacy 并行事件缺少 call_id，无法唯一关联 | 打开 Run | 原始时间线可见；歧义事件标记 unattributed；不归入任一虚构 Call | 自动化 |
| AC-015-E-2 | v2 Agent 事件缺少 required phase_id | 打开 Run | 该事件进入 malformed 集合且不进入 unattributed；其余合法事件继续构图 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-015-F-1 | events.jsonl 不存在 | 打开 Run | API 返回 Run 摘要和空事件集合；UI 显示无执行记录，不返回 500 | 自动化 |
| AC-015-F-2 | events.jsonl 最后一行仅写入一半 | 运行期间读取事件 | 完整行全部返回；半行暂不返回且后续补全后只返回一次 | 自动化 |

---

# AC-016: Run 事件流

验证 SSE 初次订阅、增量推送、断线续传和去重。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-N-1 | Run 已有 event_id 1..10 | 不带游标订阅 SSE | 按 1..10 重放，之后连接保持并推送新事件 11 | 自动化 |
| AC-016-N-2 | 客户端已收到 event_id=7 后断线 | 以 last_event_id=7 重连 | 只返回 8 及之后事件；客户端集合无重复 event_id | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-B-1 | Run 已结束，最后 event_id=10 | 以 last_event_id=10 订阅 | 不重放旧事件；服务发送 `event: stream_end`（data 含 last_event_id=10）后关闭连接 | 自动化 |
| AC-016-B-2 | 100 条 1KB 事件连续落盘，单客户端订阅 | 记录落盘到 SSE 可读延迟 | p95 < 500ms，event_id 顺序严格递增 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-E-1 | 服务端最大 event_id=10，客户端以 last_event_id=11 订阅 | 订阅 SSE | 返回 410 JSON；body.error.code=`cursor_out_of_range`、body.error.details.max_event_id=10 | 自动化 |
| AC-016-E-2 | 客户端重复收到同一 event_id | 应用前端事件 reducer | 状态只应用一次，不重复增加 Call 消息或边计数 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-016-F-1 | run_id 不存在 | 订阅 SSE | 返回 404，连接不进入重试循环 | 自动化 |
| AC-016-F-2 | 注入 event reader，使订阅已发送 event_id=5 后下一次读取抛 `OSError("fixture-read-failed")` | 保持 SSE 连接并触发下一次读取 | 服务发送 `event: stream_error`，data.code=`event_read_failed`、data.last_event_id=5，随后关闭；不发送 event_id>5 | 自动化 |

---

# AC-017: Loops 工作区与文件预览

验证 Loop 主从浏览和文件系统安全边界。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-017-N-1 | 有两个合法 Loop | 打开 Loops 并选择第二项 | 左栏保留两个 Loop；右侧原地显示第二个 Loop 的 Overview | 自动化 |
| AC-017-N-2 | Loop 含 loop.md、workflow.py、agents/reviewer.md | 依次打开 Overview、Workflow、Agents | Markdown 被渲染；Python 只读展示；Agent 列表和定义可查看 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-017-B-1 | agents 目录为空 | 打开 Agents | 显示 0 Agents 空状态，不显示错误 |
| AC-017-B-2 | 文件为二进制或超过预览上限 | 请求预览 | 返回 422 和不可预览原因，不把内容作为文本返回 | 自动化 |

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
| AC-018-B-1 | 未发现任何 Backend | 打开 Backends | 显示空状态和诊断入口，不显示健康百分比 |
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
| AC-019-N-1 | 1440x900 视口，Runs fixture 已加载 | 截图并检查布局 | Runs 列表、Phase 工作区和 Inspector 同时可见；无元素重叠或水平页面滚动 | 自动化 + 截图 |
| AC-019-N-2 | Runs 工作区打开，焦点置于左栏第一个 failed Run A；A 含 Phase p1 和 Call c1；fixture DOM 的区域顺序为 Runs→Phase→Calls→Run actions | 按 Enter 选择 A；按 Tab 1 次进入 Phase 并按 ArrowRight 选择 p1；按 Tab 1 次进入 Calls 并按 ArrowDown 选择 c1；按 Tab 1 次聚焦 accessible name=`Resume run` 的按钮并按 Enter | 每步有可见 focus；详情依次显示 A、p1、c1；最后只发出一次 A 的 resume 请求 | 自动化 |
| AC-019-N-3 | 启动 Web 服务时未传 host | 检查监听 socket | 仅监听 `127.0.0.1`，不监听 `0.0.0.0` 或外部接口 | 自动化 |
| AC-019-N-4 | 本机测试接口地址为 `0.0.0.0` | 以 host=`0.0.0.0` 且 allow-remote=true 启动服务 | 服务启动成功并监听 `0.0.0.0`；stderr 输出远程暴露警告 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-019-B-1 | 1024x768 视口 | 打开 Run | 主列表和 Phase 工作区可用；Inspector 收入可打开/关闭的抽屉；文本不重叠 | 自动化 + 截图 |
| AC-019-B-2 | 390x844 视口 | 在 Runs、Phase、Process 间切换 | 一次只显示一个主区域；Stop/Resume 可到达；无水平页面滚动 | 自动化 + 截图 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-019-E-1 | Agent 输出含 500 字符无空格字符串 | 显示 Output | Output 使用 `overflow-wrap:anywhere` 在面板内换行；页面无水平滚动且不遮挡相邻面板 | 自动化 + 截图 |
| AC-019-E-2 | SSE 连接断开 | 观察顶栏和现有内容 | 显示连接中断状态；最后数据保留；重连不导致面板闪烁或尺寸变化 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-019-F-1 | 图标按钮无可见文字 | 扫描可访问性树 | 每个按钮都有 accessible name；陌生图标有 tooltip | 自动化 |
| AC-019-F-2 | 状态颜色样式被禁用 | 查看 Runs、Phase 和 Backend 状态 | 每个状态仍可由文字或图标区分 | 自动化 |
| AC-019-F-3 | 启动 Web 服务时传 host=`0.0.0.0`，但未传显式 allow-remote 配置 | 启动服务 | 启动失败并返回非零状态；stderr 包含 `remote binding requires explicit opt-in` | 自动化 |
