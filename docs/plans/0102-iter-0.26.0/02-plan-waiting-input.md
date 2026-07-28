---
title: BL-044+045 waiting_input 生命周期实现
description: intervene default/timeout、--unattended、CLI 前台内联应答、loopflow respond 命令
type: plan
status: pending
created: 2026-07-28T11:35:00Z
---

# Plan: BL-044+045 waiting_input 生命周期

## 契约

ADR-0056（accepted）、AC-031（active，11 场景）、Spec v17 BR-059/060/061、US-036/037。扩展 ADR-0036 §5，不改变"请求落盘 + 进程退出 + 重放恢复"模型。

## Constraints

- CLI 应答必须复用应用层 `answer_requests()` + recover 路径，不在 presentation 层重写校验/写盘逻辑。
- timeout 惰性求值：只有两个求值点（重放到期 pending 请求时、CLI 前台提问倒计时），不引入常驻定时器。
- agent 侧结构化请求（resume_mode=continue）本期不加 default/timeout。
- 旧 intervention 记录（无 timeout_seconds/response_source）读取兼容。
- 文档与代码分开 commit。

## 实现要点（已核实的代码锚点）

### A. intervene default/timeout + unattended（runtime + infrastructure）

1. `src/loopflow/runtime.py:233-267` `intervene()` 增加 `default=None, timeout=None` 参数：
   - `timeout is not None and default is None` → `ValueError`（AC-031-E-2）；
   - `default` 用与 `answer_requests()` 相同的 options/allow_custom/schema 校验（`infrastructure/intervention.py:162-204`），不通过 → `ValueError`（AC-031-E-1）。
2. `src/loopflow/infrastructure/intervention.py`：
   - 请求记录增加 `timeout_seconds`（默认 None）；`request_id_for` 不变；一致性校验（intervention.py:124 附近）把 default/timeout 纳入比对，变更抛 `ReplayDiverged`（AC-031-F-1）；
   - `request_or_answer()`（intervention.py:104-155）两条新分支：
     - **创建前 unattended**：`ctx.execution_options.get("unattended")` 为真时——有 default → 直接写 answered 记录（`response_source="default"`）+ `intervention_responded` 事件并返回 default（AC-031-N-3）；无 default → 抛专用错误（如 `InterventionUnattended`），由执行层映射为 run failed `intervention_unattended`，**不创建 request**（AC-031-E-3）；
     - **惰性超时**：已存在 pending 且声明 timeout/default 且 `now > created_at + timeout` → 以 default 回答（`response_source="timeout_default"`）并返回（AC-031-B-1）；
   - `answer_requests()` 人工回答写 `response_source="human"`；旧记录无该字段读作 human。
3. `execute_workflow()`（application/execution.py:116 附近）与 CLI run 的异常映射：`InterventionUnattended` → status=failed、error_summary=`intervention_unattended`（区别于 InterventionPending → waiting_input）。
4. `--unattended` 标志：CLI `run` 注入 `execution_options["unattended"]=True`；冻结进 run.json 执行选项（BR-038 既有机制），recover 继承。

### B. CLI 前台内联应答 + `loopflow respond`

5. 交互实现位置：`src/loopflow/presentation/` 新增交互模块（如 `intervene_prompt.py`），职责：列出 pending 请求（读 run_dir/interventions/*.json）、逐题提问（options 编号选择 / allow_custom 自由文本）、`select.select` 实现 tty 倒计时（timeout 到期取 default，AC-031-B-2）、非法输入重问不落盘（AC-031-F-2）。提问与校验分离：校验仍由 `answer_requests()` 执行。
6. CLI `run()` 捕获 `InterventionPending`（cli.py:235-240）后：
   - stdin 是 tty → 内联问答 → 调应用层应答（见 7）→ 就地以 recover 语义重新执行（replay/continue 按请求 resume_mode，逻辑对齐 application/web.py:261-274），循环直到终态（AC-031-N-1）；Ctrl-C 保持 waiting_input 退出、回答不落盘；
   - stdin 非 tty → 打印 pending 数、run_id、`loopflow respond <run-id>`、WebUI 入口，waiting_input 退出（AC-031-E-4）。
7. 应用层应答复用：`application/web.py:228-285` `_respond_intervention_items()` 的核心（answer_requests + recover 启动）提取为可复用函数（如 `application/respond.py` 的 `respond_and_recover(runs_root, executor, run_id, responses)`），Web handler 与 CLI 都调它，HTTP 层只做参数解析。
8. 新命令 `loopflow respond <run-id>`（cli.py）：校验 run 状态 waiting_input/cancelled 且有 pending（否则明确错误）；stdin 非 tty 拒绝并提示 Web API；交互问答（复用 5）后调 7 的共享函数（recover 经 BackgroundRunExecutor 后台拉起，同 Web 行为）（AC-031-N-2）。

### C. Web 读模型小扩展

9. intervention 读模型暴露 `timeout_seconds`/`response_source`/`default`（如有）供 WebUI 后续展示倒计时；本期前端不改。

## 测试（回填 recovery manifest AC-031 TEST_NODES ×11）

| AC | 测试位置/要点 |
|----|--------------|
| AC-031-N-1 | tests/integration/test_cli.py：mock workflow 含 intervene(options)；CliRunner `input=` 喂选择序号；断言同 run_id done、response_source=human |
| AC-031-N-2 | 同上：先造 waiting_input run，再 `respond <run-id>` 交互应答，断言恢复（executor 可用 tests/unit/test_web_application.py 的 fake 模式或直接后台跑 mock bash） |
| AC-031-N-3 | tests/unit/test_runtime.py intervention 组：execution_options unattended + default → 返回 default、无 waiting_input、response_source=default |
| AC-031-B-1 | tests/unit/test_intervention 或同组：伪造 created_at 过期 → request_or_answer 惰性取 default（timeout_default） |
| AC-031-B-2 | 交互模块单测：patch select/时间，倒计时到期取 default |
| AC-031-E-1/E-2 | 单测：ValueError，不创建 request |
| AC-031-E-3 | 单测：unattended 无 default → run failed intervention_unattended，无 request 文件 |
| AC-031-E-4 | CLI 集成：stdin 非 tty（CliRunner 默认即非 tty）→ 指引文本 + waiting_input 退出 |
| AC-031-F-1 | 单测：改 default/timeout 后重放 → ReplayDiverged |
| AC-031-F-2 | 交互模块单测：非法输入重问、不落盘 |

回填 `tests/recovery_support/manifest.py` TEST_NODES ×11 并 `--profile recovery --write`；严格模式通过。

## Checkpoint

- [ ] AC-031 全 11 场景有真实测试节点并通过
- [ ] `python3 scripts/check-ac-manifest.py --profile recovery`（严格）通过
- [ ] `uv run pytest tests/unit tests/integration -q` 不回归
- [ ] Web handler 改为调用共享 respond 函数后 tests/unit/test_web_application.py（41 tests）不回归
