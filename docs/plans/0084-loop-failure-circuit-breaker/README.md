# 0084 Loop 失败熔断与 loop_state

对应阶段：`DEVELOP`（0.21.0 迭代，ADR-0045 / BR-050 / BR-051 / AC-027，BL-002）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Loop 失败熔断与 loop_state](01-plan-loop-failure-circuit-breaker.md) | [Report](01-report-loop-failure-circuit-breaker.md) | done |

## 范围

- 新模块 `infrastructure/loop_state.py`：`~/.loopflow/loop_state/<loop>.json` 原子读写，损坏/缺失按初始状态处理
- run 终态计数：failed → `consecutive_failures`+1 并记 `last_run_id`；done → 归零；手动与 dispatch 触发都计入（execution.py 终态收尾）
- 熔断：达阈值（默认 5，loop.md frontmatter `failure_threshold` 可覆盖，非法值按默认）置 `paused=true` + `paused_reason=failure_streak:<n>` + `paused_at`
- paused 消费语义：dispatch 将其队列任务 mark deferred + status_reason 留队（计 deferred 不计 errors）；手动 `loopflow run` 不拦截
- 解除仅手动：CLI `loopflow unpause <name>`；Web `POST /api/v1/loops/{name}/unpause`（404 loop 不存在）；清除 paused 与 streak
- Web 呈现：Loops 工作区 paused 徽标 + 原因 + unpause 操作；Run 列表/详情渲染 `error_summary` 与 `error_category`；streak 计数聚合呈现
- Spec 补充：UI 约束新增「失败与熔断呈现」小节（DESIGN 遗漏补充，方向已经用户批准）
- AC-027 全部 9 场景自动化测试 + scheduling manifest 落实真实 test_node

## 非范围

- 自动解除熔断（ADR-0045 明确不提供）
- 外部告警通知渠道（节流形态为 UI 分级呈现）
- AC-010-N-2/E-2 两个遗留 planned 场景（BL-010，DESIGN 裁决遗留）
- recover 语义与队列状态机（AC-028，0082 已交付）调整
