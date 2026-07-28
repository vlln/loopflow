---
title: BL-047 单 agent 运行入口 Report
description: loopflow run --agent 实现完成，AC-032 全 9 场景真实测试节点通过，严格 manifest 通过
type: report
status: complete
created: 2026-07-28T11:50:00Z
---

# Report: BL-047 单 agent 运行入口

## AC 验收结果

| AC | 结果 | 证据 |
|----|------|------|
| AC-032-N-1 | PASS | `tests/integration/test_cli.py::TestSingleAgentRun`；digest == `call_input_digest(loop_dir=None,…)` 且编辑 workflow.py 后不变 |
| AC-032-N-2 | PASS | 同上（--mock auto，stdout 合法 JSON） |
| AC-032-N-3 | PASS | 同上（failed → recover retry → done，同 run_id，epoch 2） |
| AC-032-B-1 | PASS | 同上（--param 渲染；缺必填 param 明确报错不创建 Run） |
| AC-032-B-2 | PASS | 同上（agent 控制结果 → waiting_input） |
| AC-032-E-1 | PASS | 同上（agent_def 不存在，不创建 Run） |
| AC-032-E-2 | PASS | 同上（--agent + --args 拒绝） |
| AC-032-E-3 | PASS | 同上（prompt 二选一用法错误） |
| AC-032-F-1 | PASS | 同上（注入失败 → run failed、exit 1、可 recover） |

测试：`uv run pytest tests/unit tests/integration -q` 443 passed（基线 434 + 9 新增，无回归）；`check-ac-manifest.py --profile singleagent` 严格模式 9 scenarios 通过。commit `b153954`（代码）、`f369844`（测试+manifest）。

## 与 Plan 的偏差（实现者记录，经确认合理）

1. 单 agent 路径不用 `load_loop`（会 import workflow.py，违反 Constraint），改用 `discovery._load_loop_meta` 只读 loop.md；新增 `_loop_dir_for()` 供 recover 子进程按名解析。
2. 单 agent 路径执行选项冻结集合加入 `transport`（否则 `--transport` 被静默丢弃）——既有 execute_workflow 的遗漏顺带修正。
3. agent_def 参数机制实际是 frontmatter `input` JSON Schema（非 Plan 所写的 `requires.params`），按实际机制实现。
4. mock bash 非零退出不使 Run failed，F-1/N-3 改用 monkeypatch 注入真实失败（同 test_runtime intervention 组范式）。
5. N-1 的 digest 契约改为直接断言（done 的 Run 不可 recover，无法 e2e）；recover e2e 由 N-3 覆盖。
