---
title: AC Manifest 增量 — AC-031/032 覆盖与 singleagent profile
description: 为 0.26.0 新增 AC 场景补 manifest 覆盖：recovery manifest 补 AC-031，新增 singleagent profile 覆盖 AC-032
type: plan
status: done
created: 2026-07-28T11:05:00Z
---

# Plan: AC Manifest 增量

## 背景

0.26.0 DESIGN 新增 AC-031（docs/ac/0011 追加，11 场景）与 AC-032（docs/ac/0014 新建，7 场景）。`check-ac-manifest.py` 的 recovery profile 要求 0011 中每个 AC id 有 TARGETS 映射，否则 mr-gate 红；0014 无任何 profile 覆盖。

## Constraints

- 只扩展测试基建，不写业务测试用例（planned:: 节点由 DEVELOP 回填）。
- 不修改已 accepted 的测试基建 ADR；本轮无新增基建 ADR（增量检查结论见容器 README）。
- mr-gate 的 4 处 profile 调用保持既有顺序，新 profile 追加在 agent 之后。

## 步骤

1. `tests/recovery_support/manifest.py`：`_targets()` 追加 AC-031 ×11 映射（process:cli-run / process:cli-respond / unit:intervention-timeout / unit:intervention-default-validation / unit:intervention-replay）。
2. 新建 `tests/single_agent_support/__init__.py`（空）与 `tests/single_agent_support/manifest.py`：镜像 agent profile 结构，profile="singleagent"，VALID_KINDS={cli_exit, process, unit}，TARGETS 覆盖 AC-032 ×7（process:cli-run / process:cli-recover）。
3. `scripts/check-ac-manifest.py`：PROFILES 注册 `"singleagent": (singleagent_manifest, "docs/ac/0014-single-agent-run.md", "tests/system/single_agent_cases.json")`。
4. `scripts/mr-gate.sh`：if/else 两支各追加 `python3 scripts/check-ac-manifest.py --profile singleagent [--allow-planned]`。
5. 重新生成：`--profile recovery --write`、`--profile singleagent --write`。
6. 验证：5 个 profile 全部 `--allow-planned` 通过。

## Checkpoint

- [ ] recovery profile `--allow-planned` 通过（含 AC-031 ×11 planned 节点）
- [ ] singleagent profile `--allow-planned` 通过（AC-032 ×7 planned 节点）
- [ ] web/scheduling/agent profile 不回归
- [ ] mr-gate 的 manifest 段在 test 分支上通过（manifest 部分）
