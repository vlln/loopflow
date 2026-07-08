---
title: 02-plan-runtime
description: 实现 Workflow Runtime：agent/parallel/pipeline/phase/log/args/workflow API
type: plan
status: pending
created: 2026-07-07T12:00:00Z
---

# 02-plan-runtime: Workflow Runtime

## Context

Runtime 是 loopflow 的核心——加载 workflow.py，提供 agent/parallel/pipeline/phase/log/args/workflow 运行时 API。签名与 Claude Code Workflow 和 subagent-skills 完全一致。

## Request

实现 `src/loopflow/runtime.py`，提供以下 API：

```python
def run(agent, parallel, pipeline, phase, log, args, workflow):
    ...
```

每个 API 的实现：

1. **agent(prompt, *, schema=None, label=None, backend=None, model=None)**
   - 分配递增序号，生成 session 名 `wf_<run_id>_<seq>`
   - Resume 时检查 `<seq>.jsonl` 缓存，命中则返回缓存
   - 未命中则调用 backend 真正执行，结果写入缓存
   - 失败返回 None

2. **parallel(thunks)**
   - 并发执行，屏障等待全部完成
   - 失败 thunk 返回 None，不抛异常

3. **pipeline(items, *stages)**
   - 每个 item 独立流经所有 stage，无屏障
   - stage 回调签名：`(prev_result, item, index)`
   - 失败/None 跳过后续 stage

4. **phase(title)** — 进度分组
5. **log(message)** — 进度消息
6. **args** — CLI 传入的 JSON 参数
7. **workflow(script_path, args)** — 嵌套子 workflow（一层深）

## Output Format

`src/loopflow/runtime.py`，约 200-300 行。配套单元测试 `tests/unit/test_runtime.py`。

## Constraints

- 签名与 subagent-skills 完全一致
- 使用 `contextvars` 或模块级变量管理运行上下文，不注入 ctx
- 缓存文件写入 `~/.loopflow/runs/<run-id>/<seq>.jsonl`
- Mock 模式支持（`SHELL` — 用 shell 命令替代真实 agent）

## Checkpoint

1. `agent()` 正确分配序号，缓存命中/未命中逻辑正确
2. `parallel()` 并发正确，失败不崩溃
3. `pipeline()` 无屏障，item 独立流动
4. Resume 机制：已完成的 agent 调用跳过，损坏缓存重新执行
5. 单元测试覆盖 N/B/E/F 四场景

## Steps

1. 设计 RunContext（run_id, counter, resume flag, run_dir）
2. 实现 agent()：序号分配、缓存检查、backend 调用、缓存写入
3. 实现 parallel()：threading 并发 + 屏障
4. 实现 pipeline()：threading 无屏障
5. 实现 phase() / log() / workflow()
6. 编写单元测试：正常、边界、异常、失败四场景
7. 编写集成测试：mock backend 验证完整流程