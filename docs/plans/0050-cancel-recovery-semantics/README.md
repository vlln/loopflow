# 0050 取消恢复语义设计修订

对应阶段：`DESIGN`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [取消恢复语义](01-plan-cancel-recovery-semantics.md) | [Report](01-report-cancel-recovery-semantics.md) | done |

## 背景

RELEASE 前审查发现当前 AC-021/022 把 `cancelled` 定义为只能 `rerun` 的不可恢复终态，这过度建模了用户“放弃整个 Run”的意图。新设计应把 `cancelled` 收敛为当前 execution attempt 被取消的事实，并由恢复边界和 session 能力决定后续是否可 recover/continue/respond。

## 范围

- 修订 ADR 0036 的 stop/cancel/recover/respond/rerun 语义
- 修订 Spec v13 的 Run 状态、allowed actions 和恢复 metadata
- 修订 Interface 0001 的 recover/respond 行为
- 修订 AC 0011 中 AC-021/022 的取消恢复预期
- 输出后续 TEST_INFRA/DEVELOP 执行建议

## 非范围

- 不直接修改产品代码
- 不重新发布 0.18.0
- 不引入“abandoned”或“不可恢复”状态，除非设计审查推翻本 Plan 的前提
