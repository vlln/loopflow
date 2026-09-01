---
title: 0115 — rerun_loop 校验驱动的重试编排（BL-062）
description: 框架层实现通用跨阶段回退编排原语 rerun_loop（ADR-0058），含单元测试 + 与 bio-reproducer 无关的端到端 demo loop 验证
type: plan
status: active
created: 2026-08-31T00:00:00Z
---

# Context

BL-062 / ADR-0058：bio-reproducer 的跨阶段回退机制（routing.jsonl + workflow.py 手写
循环）是通用需求，应上移框架层为 validation-driven rerun 原语。ADR-0052 已删 phase
抽象，故新原语为 `rerun_loop`（阶段序列 + 校验回调 + 路由映射 + 预算），路由事件经
State 持久化，不引入事件文件、不检查格式。

# Request

1. 实现 `src/loopflow/domain/rerun_loop.py`：`Stage` dataclass + `rerun_loop()`，
   与 `run_goal_loop` 同风格。
2. `loopflow.runtime` 暴露 `rerun_loop()` 入口（可选；若纯 domain 可先用 domain 层）。
3. State 增加 `route_log` 支持（路由事件持久化）。
4. 单元测试 `tests/unit/test_rerun_loop.py`：顺序执行 / 回退 / 预算耗尽 /
   validate 异常传播 / Stage 参数透传。
5. 端到端 demo loop（mock backend，**与 bio-reproducer 无关**）：
   `tests/agent_support/rerun_demo_loop/`——阶段 A 故意失败 → validate 返回 route_key
   → 回退 → 阶段 A 修复后通过。黑盒 e2e 测试 `tests/e2e/test_rerun_demo_loop.py`。
6. 验证 bio-reproducer 单个 entry 在现有代码上不受影响（本容器只验证不迁移，
   迁移归 bio-reproducer 侧后续）。

# Constraints

- 不引入 phase 概念（ADR-0052）；不新增事件文件（路由事件走 State）。
- 不内置领域路由表；route_map 由调用方注入。
- 框架层无破坏性变更（纯增量）；不修改现有 goal_loop / agent 行为。
- 文档 commit 与代码 commit 分开（devloop 约定）。

# Checkpoint

- [ ] ADR-0058 accepted
- [ ] rerun_loop 实现 + unit 测试全过
- [ ] demo loop e2e 黑盒通过（mock backend，无付费）
- [ ] bio-reproducer 单 entry 验证不受影响
- [ ] 全量回归（tests/unit + tests/integration + mr-gate 相关）通过

# Steps

1. 实现 rerun_loop.py（domain 层，参照 goal_loop.py 风格）。
2. 写 unit 测试（mock call_fn，不依赖真实 backend）。
3. runtime 暴露入口（如需要）。
4. 建 rerun_demo_loop（mock bash），e2e 黑盒验证回退行为。
5. 跑全量回归 + 检查 AC manifest。
6. 验证 bio-reproducer 单 entry（远端归档 run 或本地轻量 run）。
7. Report 落盘：HEAD、测试结果、e2e 证据、兼容验证结论。
