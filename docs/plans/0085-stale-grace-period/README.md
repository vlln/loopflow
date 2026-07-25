# 0085 stale 失联宽限期

对应阶段：`DEVELOP`（0.21.0 迭代，ADR-0046 / BR-052 / AC-029，BL-003）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [stale 失联宽限期](01-plan-stale-grace-period.md) | [Report](01-report-stale-grace-period.md) | done |

## 范围

- run.json 新增 `stale_since`：读模型首次判定 stale 时原子写入（复用 BR-031 机制），只写一次不刷新；legacy run 无该字段按首次判定处理
- 宽限期默认 24h（常量，不做可配置入口）：宽限期内显式 reconcile 返回 409 `run_in_grace` 且 run.json 不修改；期满后按 BR-032 既有流程转 failed 并清除 `stale_since`
- worker 恢复优先：execution.py / cli.py 终态写入路径清除 `stale_since`（epoch+status 乐观锁保证 worker 写入优先）
- 读模型投影透出 `stale_since` 与宽限剩余秒数；WebUI 宽限期内 stale 呈现「失联（宽限中）」与剩余时间（非警报化，前端从简）
- AC-029 全部 7 场景自动化测试 + recovery manifest 落实真实 test_node

## 非范围

- 宽限期可配置入口（ADR-0046 决策常量化，保持简单）
- 心跳机制（ADR-0046 Alternatives 已否决）
- AC-010-N-2/E-2 两个遗留 planned 场景（BL-010，scheduling profile）
- reconcile 后 recover 边界调整（既有行为不变）
