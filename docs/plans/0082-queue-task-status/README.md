# 0082 队列任务显式状态

对应阶段：`DEVELOP`（0.21.0 迭代，ADR-0047 / BR-053 / AC-028，BL-004）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [队列任务显式状态](01-plan-queue-task-status.md) | [Report](01-report-queue-task-status.md) | done |

## 范围

- 队列条目 schema 增加 `status`（pending/deferred/superseded，默认 pending）、`status_reason`、`superseded_by`；缺失或未知 status 按 pending 处理（向后兼容）
- CLI `loopflow enqueue --supersede`：同 loop 的 pending/deferred 任务标记 superseded + `superseded_by`
- dispatch：资源锁不可得 → 标记 deferred + `status_reason` 留队；superseded 任务跳过并清理；summary 增加 deferred/superseded 两桶，均不计入 errors
- Web 投影 `QueueRepository` 透传 status/status_reason/superseded_by（仅后端投影 + 接口契约）
- AC-028 全部 7 场景自动化测试 + scheduling manifest 落实真实 test_node

## 非范围

- 前端队列状态展示（呈现层后续容器）
- paused loop 的队列任务 deferred 衔接（ADR-0045 / AC-027，属 0084 熔断容器）
- AC-027/AC-029 场景实现
- misfire 补偿（loopflow 无常驻调度器，ADR-0047 已声明不适用）
