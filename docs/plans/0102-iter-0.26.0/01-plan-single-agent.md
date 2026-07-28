---
title: BL-047 单 agent 运行入口实现
description: loopflow run --agent 直接运行单个 agent_def，完整 Run 语义，不执行 workflow.py，digest 不含 workflow
type: plan
status: pending
created: 2026-07-28T11:35:00Z
---

# Plan: BL-047 单 agent 运行入口

## 契约

ADR-0055（accepted）、AC-032（active，9 场景）、Spec v17 BR-058/US-035。

## Constraints

- 不导入、不执行 workflow.py；单 agent Run 的 input_digest 中 workflow 分量必须为 None（编辑 workflow.py 不得导致单 agent Run recover 时 replay_diverged）。
- 复用现有 Run 基础设施（run_dir/run.json/events/缓存/recover），不造并行实现。
- presentation 层不得绕过 RunContext 直接构造 AgentRunner。
- 文档与代码分开 commit。

## 实现要点（已核实的代码锚点）

1. **RunContext 增加 digest 开关**：`src/loopflow/infrastructure/context.py` 的 `RunContext` 增加 `digest_workflow: bool = True`。`src/loopflow/application/runner.py:332` 处 `call_input_digest(loop_dir=self.ctx.loop_dir, ...)` 改为 `loop_dir=self.ctx.loop_dir if self.ctx.digest_workflow else None`（`workflow_digest(None)` 返回 None，见 `infrastructure/recovery.py:72`）。
2. **run.json 持久化单 agent 配置**：新增 `single_agent` 字段 `{"agent_def": str, "prompt": str, "params": dict}`（prompt 在创建时从 `--prompt`/`--prompt-file` 解析为最终文本）。`--args` 在 `--agent` 模式下拒绝（用法错误，exit≠0，不创建 Run）。
3. **共享执行函数**：`src/loopflow/application/execution.py` 新增 `execute_single_agent(loop_dir, single_agent, options, run_id, run_dir, working_directory)`，镜像 `execute_workflow()`（execution.py:20-184）的 run.json 生命周期：status running → done/failed/waiting_input、execution_epoch、InterventionPending 捕获、error_summary/error_category、冻结执行选项。内部构造 `RunContext(digest_workflow=False)` + `set_context`，调 `runtime.agent(prompt, agent_def=..., **params)`（runtime.py:44；agent_def 加载 runtime.py:72-79，`output` schema 自动应用）。
4. **CLI**：`src/loopflow/presentation/cli.py` `run()`（cli.py:120-269）增加 `--agent/--prompt/--prompt-file/--param`（click，param 可重复、解析 `key=value`）。校验顺序：agent_def 文件存在（loop_dir/agents/<name>.md，不存在则明确错误不创建 Run）→ prompt 二选一必填 → --args 拒绝。前台路径调 `execute_single_agent`；结果打印 stdout（dict 则 `json.dumps`），退出码 done=0/failed=1。
5. **recover 接通**：`_execute_workflow_process`（execution.py，BackgroundRunExecutor.start 的 spawn target，execution.py:274）在 options 含 `single_agent` 或 recover 且 run.json 含 `single_agent` 字段时走 `execute_single_agent` 分支；recover 时 agent/prompt/params 从 run.json 读（冻结，不接受覆盖，同 ADR-0036 执行选项冻结）。CLI `recover`/`resume` 与 Web recover 因此都可用。
6. **显示**：沿用现有 `_emit_log`/`text_handler` stderr 输出，不新增展示层。

## 测试（回填 singleagent manifest TEST_NODES）

新增 `tests/integration/test_cli.py::TestSingleAgentRun`（沿用该文件现有 CliRunner + LOOPFLOW_LOOPS_DIR/RUNS_DIR env 隔离 + `--mock bash/auto` 模式）：

| AC | 测试要点 |
|----|---------|
| AC-032-N-1 | `--agent reader --prompt` + `--mock bash`：run.json done、events.jsonl、0001.jsonl 存在；digest 中 workflow 为 None（改 workflow.py 后 recover 不 diverge）；stdout 含结果 |
| AC-032-N-2 | agent_def 带 `output` schema + `--mock auto`：stdout 为合法 JSON |
| AC-032-N-3 | mock 失败后 recover mode=retry：同 run_id，Call 0001 重跑 done |
| AC-032-B-1 | body 含 `{{topic}}`：`--param topic=x` 渲染成功；缺 param 明确报错不创建 Run |
| AC-032-B-2 | agent 返回 waiting_input 控制结果（mock backend 可控输出，参考 tests/unit/test_runtime.py intervention 组的做法）：run waiting_input |
| AC-032-E-1 | `--agent ghost`：明确错误，run_dir 不创建 |
| AC-032-E-2 | `--agent` + `--args` 同传：拒绝 |
| AC-032-E-3 | `--prompt` 与 `--prompt-file` 同传/皆缺：用法错误 |
| AC-032-F-1 | backend 失败（mock bash 非零退出）：run failed、exit 1、可 recover |

回填 `tests/single_agent_support/manifest.py` TEST_NODES ×9 并 `--profile singleagent --write` 重新生成 cases.json；严格模式（无 --allow-planned）必须通过。

## Checkpoint

- [ ] AC-032 全 9 场景有真实测试节点并通过
- [ ] `python3 scripts/check-ac-manifest.py --profile singleagent`（严格）通过
- [ ] `uv run pytest tests/unit tests/integration -q` 不回归
- [ ] 编辑 workflow.py 后 recover 单 agent Run 不 diverge（N-1 覆盖）
