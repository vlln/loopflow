---
title: 01-report-impl-gaps
description: 实现 A1-A4：meta.phases 声明、agent 事件 phase 归属、agent_def 接入、模板渲染 — 执行结果
type: report
status: complete
created: 2026-07-08T12:00:00Z
---

# 01-report-impl-gaps: 实现补全 A1-A4

## 执行摘要

| 项 | 值 |
|----|-----|
| 状态 | done |
| 测试 | 107/107 pass |
| 新增测试 | 22 (7 agent + 5 discovery + 3 runtime phase + 5 runtime agent_def + 2 existing) |

## 变更清单

| 文件 | 变更 |
|------|------|
| `src/loopflow/agent.py` | 新增 `render_template(body, **kwargs)` 函数 |
| `src/loopflow/runtime.py` | RunContext 加 `_current_phase`、`loop_dir`；agent() 加 `agent_def`、`**kwargs`；_emit_phase() 设 current_phase；agent 事件加 `phase` 字段 |
| `src/loopflow/discovery.py` | `load_loop()` 返回 3-tuple `(mod, meta, loop_dir)`；`_load_meta()` 验证 `phases` 字段 |
| `src/loopflow/cli.py` | `run`/`resume` 命令传递 `loop_dir` 到 RunContext |
| `tests/unit/test_agent.py` | 新增：7 个模板渲染测试 + 4 个 parse_agent 测试 |
| `tests/unit/test_discovery.py` | 新增：5 个 meta.phases 验证测试 |
| `tests/unit/test_runtime.py` | 新增：3 个 phase 归属测试 + 5 个 agent_def 测试 |

## AC 验收

### A1: meta.phases 声明

| 场景 | 测试 | 结果 |
|------|------|------|
| N-正常 | `test_meta_with_valid_phases` — 合法 phases 声明加载成功 | PASS |
| N-正常 | `test_meta_without_phases` — 无 phases 字段兼容 | PASS |
| N-正常 | `test_meta_phases_empty_list` — 空列表合法 | PASS |
| B-边界 | `test_meta_phases_not_list` — phases 非列表报错退出 | PASS |
| E-异常 | `test_meta_phases_missing_title` — 缺少 title 字段报错 | PASS |

### A2: Agent 事件 phase 归属

| 场景 | 测试 | 结果 |
|------|------|------|
| N-正常 | `test_agent_event_has_phase_field` — agent_start 携带 phase | PASS |
| N-正常 | `test_phase_change_updates_agent_events` — phase 切换正确 | PASS |
| B-边界 | `test_agent_event_without_phase` — 无 phase 时为 None | PASS |

### A3: agent_def 接入

| 场景 | 测试 | 结果 |
|------|------|------|
| N-正常 | `test_agent_def_merges_body_and_prompt` — body 与 prompt 合并 | PASS |
| N-正常 | `test_agent_def_default` — 默认加载 default.md | PASS |
| B-边界 | `test_agent_def_without_loop_dir` — 无 loop_dir 时降级为 plain prompt | PASS |
| E-异常 | `test_agent_def_nonexistent` — 不存在的 agent_def 降级 | PASS |
| F-失败 | `test_agent_def_missing_template_param` — 缺少模板参数抛 ValueError | PASS |

### A4: 模板渲染

| 场景 | 测试 | 结果 |
|------|------|------|
| N-正常 | `test_render_single_param` / `test_render_multiple_params` | PASS |
| N-正常 | `test_render_no_params` — 无占位符原样返回 | PASS |
| N-正常 | `test_render_duplicate_param` — 重复参数全部替换 | PASS |
| B-边界 | `test_render_empty_body` — 空 body 返回空字符串 | PASS |
| B-边界 | `test_render_extra_kwargs_ignored` — 多余参数忽略 | PASS |
| F-失败 | `test_render_missing_param_raises` — 缺少参数抛 ValueError | PASS |

## 关联 Commit

```
feat/0010-impl-gaps: A1-A4 implementation
```