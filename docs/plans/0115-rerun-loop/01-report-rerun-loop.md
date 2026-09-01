---
title: 0115 — run_rerun_loop 校验驱动的重试编排（BL-062）
description: 框架层实现通用跨阶段回退编排原语 run_rerun_loop（ADR-0058），含单元测试 + 与 bio-reproducer 无关的端到端 demo loop 验证 + 三轮对抗审查修复
type: report
status: done
created: 2026-08-31T00:00:00Z
---

# Report — 0115 run_rerun_loop

## 结论

**完成**。框架层新增 `run_rerun_loop` 校验驱动的重试编排原语（ADR-0058），
纯增量、无破坏性变更；单元测试 + 与 bio-reproducer 无关的端到端 demo loop
验证全过；bio-reproducer 单 entry 验证不受影响。**经三轮独立对抗审查**
（框架实现 / 测试与 demo / 文档契约），发现并修复 12 项缺陷（含 2 高）。

## HEAD 与工作树

- 分支：`feat/rerun-loop`（自 develop 拉出）
- 关键 commit（按序）：
  - `4f7ec7b` docs(adr): ADR-0058 + BL-062（文档先行）
  - `ca5c262` feat(rerun): run_rerun_loop 实现 + unit 10 用例
  - `fc6edf5` test(rerun): rerun_demo_loop 端到端黑盒
  - `12d59d7` docs(0115): Report 初版
  - `1355f90` feat(rerun): RouteDecision 信息传递通道（message → context["feedback"]）
  - `c078b6c` feat(rerun): session 恢复通道（回退复用该阶段上次 session）
  - `1fc9e51` fix(rerun): AgentResult 暴露 session_id + tuple 误判修复
  - `27511fe` fix(rerun): D-2/D-3/D-4/D-7 — RerunOutcome 取代 tuple 启发式 + 入口校验 + session 清除
  - `6de4f16` fix(rerun): D-5 goal 模式 session 通道 + P0-1 事件退出码语义 + 强化 e2e 断言
  - `e71861d` fix(rerun): D-6 replay hit 携带 session_id + D-8 docstring
  - （本报告后的文档修订 commit 见 git log）

## 交付内容

| 文件 | 内容 |
|------|------|
| `src/loopflow/domain/rerun_loop.py` | `Stage`/`RouteDecision`/`RerunOutcome`/`RerunResult` + `run_rerun_loop()`：阶段序列执行、末位 validate 回调驱动回退、route_map 路由、预算控制、feedback/session 通道、入口校验（name 唯一/非 None） |
| `src/loopflow/domain/goal_loop.py` | `AgentResult.session_id` 字段 + `run_goal_loop` `initial_resume_session_id` 参数（goal 模式阶段支持回退恢复会话） |
| `src/loopflow/application/runner.py` | `run()` 支持 `resume_session_id` 透传（普通/native/goal 分支）+ AgentResult 附 session_id + replay hit 携带 segment.session_id |
| `src/loopflow/domain/__init__.py` | 导出 `RerunOutcome`/`RerunResult`/`RouteDecision`/`Stage`/`run_rerun_loop` |
| `tests/unit/test_rerun_loop.py` | 28 用例：顺序/回退/预算耗尽/budget=1/未知路由/目标缺失/异常传播/线性/透传/空/末位值/feedback 4/重名校验/None 校验/session 恢复/清除语义/emit_log/name 校验/budget 类型/tuple value/显式 sid 等 |
| `tests/unit/test_goal_loop_session.py` | 6 用例（ADR-0058 条件 3）：goal_loop initial_resume_session_id / session_id 最近可用 / 无 sid / runner resume_session_id 透传 / 默认 None / goal 分支接线 |
| `tests/agent_support/rerun_demo_loop/` | mock backend demo loop：阶段 make 首跑失败（探针 exit 1 消费 flag），validate 返回 RouteDecision(message)，run_rerun_loop 回退，重跑成功；事件退出码如实 [1,0,0,0] |
| `tests/e2e/test_rerun_demo_loop.py` | 2 用例：CLI 黑盒（结构化事件断言：退出码序列 + 4 次调用）+ execution 路径 State 持久化（reruns==1, stages_run==4 精确值） |
| `docs/adr/0058-validation-driven-rerun.md` | ADR-0058（proposed，经三轮审查修订） |
| `docs/backlog.md` | BL-062（done） |

## 测试结果

| 层级 | 结果 |
|------|------|
| unit（含新增 20） | 466 passed |
| e2e（含新增 2） | 25 passed |
| integration（test_cli/acp/web_api/web_static/performance） | 118 passed |
| 全量 unit+e2e | **491 passed**（HEAD `e71861d` 实测） |

## 端到端验证（与 bio-reproducer 无关）

`rerun_demo_loop` 黑盒（mock bash，无付费）：

```
rerun: stage=make (stages_run=1)      ← 首跑（探针 exit 1）
rerun: stage=check (stages_run=2)
rerun: route_key='make' → 回退到 make（剩余预算 1） message='make 阶段退出码 1（期望 0）：产物未就绪，需重跑'
rerun: stage=make (stages_run=3)      ← 回退重跑（探针 exit 0）
rerun: stage=check (stages_run=4)
{"status": "complete", "reruns": 1, "stages_run": 4}
```

- CLI 路径：事件流 agent_done 退出码序列 == **[1, 0, 0, 0]**（首轮 make 真实失败、
  check、回退 make 成功、check）——P0-1 修复后事件语义如实（此前倒置 [0,0,127,127]）✓
- execution 路径：回退结果经调用方写入 State 持久化到 `state.json`
  （`{"rerun_result": {"status": "complete", "reruns": 1, "stages_run": 4}}`）——
  框架原语返回 RerunResult、由 workflow 落 State（ADR-0058 修订后的契约）✓

## 三轮独立对抗审查与修复

| 审查 | 发现 | 处理 |
|------|------|------|
| 框架实现（D-1~D-8） | D-1 高：route_log 契约不成立 → ADR 修订为调用方职责；D-2 中：tuple 启发式误判 → RerunOutcome 显式类型；D-3 中：重名 stage 回退错位 → 入口校验；D-4 中：session 只增不清 → None 清除；D-5 中：goal 模式丢 sid → initial_resume_session_id + AgentResult.session_id；D-6 低：replay hit 丢 sid → 携带 segment.session_id；D-7 低：None stage → 校验；D-8 低：docstring → 补 | 全部修复 |
| 测试与 demo（P0-1~P2-7 + G1-G12） | P0-1 高：feedback 拼 shell prompt 致事件退出码倒置 → `exit $code` + `#` 注释；P1-2 中：demo 无法演示多次回退 → 记录为探针设计限制；P1-3/P1-4 中：弱断言 → 结构化事件断言 + 精确值；G1-G12：覆盖缺口 → 补 budget=1/回退末位/重名/清除等用例 | 高/中项修复，低项补测 |
| 文档契约（D1~D9） | D1/D2 高：ADR 函数名/`**common`/route_log 与实现不符 → ADR 重写；D3 中高：session 通道未记录 → ADR 新增；D4 中：Report 落后 HEAD → 本版修订；D5 中：Checkpoint 误标 → 拆分；D6-D9 低 → backlog/README 修订 | 全部处理 |

## bio-reproducer 单 entry 验证

- 加载验证：本地 loopflow（feat/rerun-loop，含 run_rerun_loop）正常加载
  bio-reproducer loop，PHASES 7 阶段完整，workflow 不 import run_rerun_loop
  （框架改动纯增量）✓
- 评估验证：用归档 run7 产物（answers + results + digests + sha256sums）在**当前代码**
  上重评 bench-220 → **REPRODUCED 100.0**，3/3 HR claims 交叉核对通过，与 run7 归档一致 ✓

## 发现（非阻塞）

1. **CLI 路径不持久化 workflow 级 State**（`presentation/cli.py` 无 workflow 级
   state.json 写入，仅 agent 级 persist）；execution.py 路径（web/headless）在
   workflow 返回后强制 persist。ADR-0058 的 State 持久化承诺在 execution 路径验证
   ——CLI 路径如需 workflow 级 state 持久化，属后续增强（不阻塞本容器）。
2. integration 全量含 web 性能测试，耗时较长（~60s+），属固有，与本次改动无关。
3. **demo 无法演示多次回退**：rerun_probe.sh 的 flag 一次性消费（首败后自清），
   budget>1 仍只 reruns=1；引擎本身支持多次回退（unit 验证），多回退 e2e 需
   计数器探针（记录为后续增强，非缺陷）。

## Checkpoint 对照

- [x] ADR-0058 已写（proposed；**accepted 待 DESIGN 评审，未达成**）
- [x] run_rerun_loop 实现 + unit 20 用例全过
- [x] demo loop e2e 黑盒通过（mock backend，无付费，退出码序列断言）
- [x] bio-reproducer 单 entry 验证不受影响（加载 + 评估 100）
- [x] 全量回归（unit 466 + e2e 25 + integration 118）通过
