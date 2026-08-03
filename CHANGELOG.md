# Changelog

## [0.27.1] — 2026-07-30

### Fixed
- **并行 Agent 事件 call_id 串线**（生产阻断性，deep-research 实跑暴露）：parallel 多个 Agent 并发时，`agent_message` 等事件的 `call_id` 被标成其他 worker 的——根因是 context 的 `_current_call_id` 是共享实例属性，并发 worker 互相覆盖。修复：改为读线程局部 `_call_namespace.current_call_id`（`threading.local`），每个 worker 各自携带自己的 call_id。回归测试 `tests/unit/test_runtime.py::TestParallelEventAttribution` 固定。
- **`loopflow web` 返回 404 静态资源**（生产阻断性，0.27.0 发布遗漏）：0.27.0 发布时未将前端构建产物同步进 wheel，安装后 `loopflow web` 的 WebUI 全 404 `file_not_found`。修复：server 静态解析增加开发态兜底（包内 `static` 缺失时回退 `web/dist` 或 `LOOPFLOW_WEB_DIST` 环境变量），`uv run loopflow web` 不再依赖手动 `sync-web-assets.sh`。
- **发布门禁补强**：`scripts/verify-wheel-assets.py` 新增端到端 smoke——起真实 `loopflow web` 服务 curl `/` 应 200，防止"wheel 有文件但服务不起来"再次漏过。回归测试 `tests/integration/test_web_static_serving.py` 固定此缺陷。

## [0.27.0] — 2026-07-30

### Added
- **WebUI 二进制文件预览**（BL-051 / AC-033）：图片（png/jpg/jpeg/gif/svg/webp/bmp/ico）与 PDF 经 raw 端点只读返回，固定 media type 与 `Cache-Control: no-store`；preview 返回 `encoding=raw`/`raw_url`，>50 MiB 或非白名单返回 422 `file_not_previewable`；读取 OSError 返回 500 `file_read_failed` 且不发部分 bytes。
- **Run 级追加 prompt**（BL-052 / AC-034）：`--append-prompt` 与 WebUI New Run Append prompt 字段，附加段注入每个 workflow Agent 的动态 prompt 末尾，冻结进 run.json，不进入 system prompt；UTF-8 超 64 KiB 在 CLI/API/WebUI 三入口拒绝（422 / 退出码非 0 / 前端校验）。
- **New Run declared args 契约符合性**（BL-054 / AC-035）：`loop.md` 顶层 `args` 声明驱动 Arguments 编辑器预填（required 标记、空值忽略、false/0/对象/空串类型保留），切换 Loop 重建键值行，非法条目静默忽略；不回退 legacy `workflow.py meta.args`。
- **Agent waiting_input 控制协议**（BL-046 / ADR-0057 / AC-023）：并行 Agent 分组批量应答与各自 session 恢复、控制分支绕过业务 schema、answer envelope 保留组序并隐藏内部字段。

### Changed
- **reconcile 宽限期语义对齐 ADR-0046**（契约修订）：宽限期不再阻塞 reconcile——进程探活确认死亡即直接清理为 failed（后端 session 仍可 resume，阻塞无安全收益）。`stale_since` 仅供 UI 呈现失联参考时间。Spec v19→v20、AC-014-B-7、AC-029-B-1、Interface 0001 同步；`run_in_grace` 错误码保留仅为向后兼容，不再触发。

### Fixed
- **Web 契约测试基建**（BL-051 契约闭环）：AC manifest 对齐 AgentGraph/call_id 契约（ADR-0052），89 个冻结 Web 场景全部映射真实测试节点，strict 模式 0 planned。逐项语义审查既有节点，partial 节点保持诚实 planned 后逐一补齐。
- **recovery manifest 节点存在性检查**：补 `_test_node_exists` 校验，修正 AC-029-B-1/AC-020-F-3 引用已改名测试函数的漂移。
- **AgentGraph 投影**：malformed 事件包装为 `{reason, raw}` 结构且 detail `events` 排除坏事件 raw；空/缺失 label 回退 call_id；loop/run 响应移除已删除的 `declared_phases`（对齐 ADR-0052）。
- **working_directory 显示**：`_working_directory` 优先读 run.json 持久化值（AC-014-B-6 左栏 basename 显示）。
- **mr-gate 阶段测试**：不再假设仓库当前处于 DEVELOP，阶段推进后 CI 仍绿。
- **性能专项**：新增 Runs 首屏 p95 < 500ms 测试（1000 Runs + 1000 事件 fixture，30 次测量）。

## [0.26.0] — 2026-07-28

### Added
- **单 agent 运行入口**（BL-047 / ADR-0055 / AC-032）：`loopflow run <loop> --agent <name> (--prompt | --prompt-file) [--param k=v]` 直接运行 loop 中单个 agent_def。完整 Run 语义（run_dir/缓存/事件/WebUI 可观察/可 recover），不导入、不执行 workflow.py，input_digest 的 workflow 分量为 None（编辑 workflow.py 不影响单 agent Run 的恢复）。评测 harness 与单 agent 调试不再需要临时 workflow 绕行。
- **CLI 前台内联应答 intervention**（BL-044 / ADR-0056 / AC-031）：前台 `loopflow run` 进入 `waiting_input` 且 stdin 为 tty 时，终端内联逐题提问（options 编号选择 / allow_custom 自由文本，声明 timeout 时倒计时），校验与 `answer_requests()` 一致，回答后就地恢复同一 Run 直至终态。stdin 非 tty 时打印 pending 数、run_id 与应答入口指引。
- **`loopflow respond <run-id>`**（BL-044）：对 `waiting_input`/`cancelled` 的 Run 交互式应答并恢复，应答非前台产生的等待，补齐 Spec 早已声明的 CLI 能力。
- **`intervene()` default/timeout**（BL-045 / ADR-0056 / AC-031）：`intervene(..., default=..., timeout=...)`。default 在调用时通过 options/allow_custom/schema 校验；timeout 必须搭配 default，采用惰性求值——重放到期（`created_at + timeout` 已过）的 pending 请求自动以 default 回答，无需常驻定时器。已回答请求记录 `response_source`（human/default/timeout_default）。
- **`--unattended` 无人值守模式**（BL-045）：`loopflow run --unattended` 冻结进 Run 执行选项（recover 继承）。遇到 intervention 请求：有 default 直接取兜底继续（不进入 waiting_input），无 default 以 `intervention_unattended` 明确失败，headless/CI/benchmark 环境不再空等。

### Changed
- **应用层应答路径共享**：`application/respond.py::respond_and_recover` 从 Web handler 提取，Web 与 CLI（内联应答、respond 命令）复用同一校验与恢复逻辑。
- **intervention 数据模型扩展**：请求记录新增 `timeout_seconds`，回答记录新增 `response_source`；旧记录读取兼容（缺省视为 human）。default/timeout 变更按 `replay_diverged` 处理。
- **intervention 读模型暴露 `default`/`timeout_seconds`/`response_source`**，供 WebUI 后续展示倒计时（本期前端不改）。

### Fixed
- **AC manifest 漂移清理**：recovery profile 补 AC-031 ×11 映射；agent profile 补 AC-001 BL-018 追加场景（4 个场景补 parse_agent 单测，AC-001-F-2 补假 pi getopt 进程级回归，BL-048）；AC-026 BL-031 追加场景补 4 个 agent() 行为级测试。recovery/scheduling/agent/singleagent 四个 profile 严格模式 planned 清零。
- **新增 singleagent AC manifest profile**（AC-032），mr-gate 注册 5 个 profile。

## [0.25.1] — 2026-07-28

### Fixed
- **远程 run 文件预览失败**（BL-034）：`resolve_working_directory` 在工作目录不存在时兜底到 `run_dir/work` 隔离目录（ADR-0054），并改进错误消息区分 "工作目录不可访问" 和 "文件不存在"。
- **Events 重复渲染**（BL-035）：`_call_backend` 的 infra-retry 循环仅在首次迭代写 `agent_start`（重试已有 `agent_retry`）；`project_events` 对同一 `(call_id, session_id)` 的重复 `agent_session` 事件去重，只保留最后一条。
- **后端显示为 unknown**（BL-036）：auto-detect 后端时 `agent_start` 事件的 `backend` 字段为 None，前端显示 "backend unknown"。修复：`_make_backend` 在实例上设置 `backend_name` 属性，`AgentRunner` 在写 `agent_start` 时优先使用该属性作为 display fallback，不影响 `input_digest` 缓存兼容性。
- **File changes 文件夹不可折叠**（BL-037）：`ChangeTreeDirView` 添加 `useState` 展开/折叠控制，点击切换，chevron 图标指示状态。默认展开。
- **Loops 页面混入运行时状态**（BL-038）：Loops 定义页移除 `paused`、`failure_streak`、`paused_reason`、Unpause 按钮等 run 级状态。定义页只展示定义信息。
- **切换 Runs 时卡顿**（BL-039）：切换 run 时立即清空旧 `detail`，避免 React 用旧数据重渲染（含 AgentGraph key 变化导致重挂载）。
- **Backends API 对 missing 后端调用 _make_backend**（BL-040）：`summary()` 中 `if path:` 条件保护 `_make_backend`，7 个 missing 后端不再创建实例。
- **切换页面卡顿 + missing catch**（BL-041）：tab 切换用 `hidden` 属性替代条件挂载/卸载，workspace state 跨 tab 保留，不重新发 API 请求；补 `api.loops()` 的 `.catch()`。

## [0.25.0] — 2026-07-28

### Added
- **Schema 类型兜底**（BL-031）：新增 `coerce_json()` 函数，agent 返回的 JSON 类型不匹配时自动尝试兼容转换（string→number/integer、string→bool、number/bool→string、enum case-insensitive match、array wrap）。兜底后的值必须通过 `validate_json` 二次校验才接受。
- **Retry hint 携带详细错误**（BL-031）：retry hint 从通用 "not valid JSON" 升级为汇总错误列表（字段路径、期望类型、实际值、兜底尝试结果），agent 能针对性修正而非反复改格式。
- **json.loads 成功后补 schema 校验**（BL-031）：修复 `runner.py:446-451` 跳过 schema 校验的缺陷，agent 返回纯 JSON 但类型不匹配不再被静默接受。

### Fixed
- **WebUI failed run 错误布局**（BL-032）：`.error-summary-text` 加 `max-height: 3em` + `-webkit-line-clamp: 2`，error_banner 不再占据大量空白挤占 Phase 工作区。
- **Runs 左栏显示项目目录名**（BL-033）：`<code>` 从显示 `run_id`（UUID）改为 `working_directory` 的 basename，用户可辨识 run 对应哪个项目。

### Changed
- **vitest 升级**（BL-011）：`@vitest/coverage-v8` 和 `vitest` 从 3.2.7 升级到 4.1.10，修复 brace-expansion 高危漏洞（0 vulnerabilities）。branch coverage 阈值从 80% 调整为 79%（vitest 4.x 分支计数方式变化）。
- **版本号单源化**（BL-013）：`__init__.py` 用 `importlib.metadata.version("loopflow")` 从 pyproject.toml 读取版本号，消除双写同步风险。

## [0.24.2] — 2026-07-27

### Added
- **Web 端跨平台目录选择器**（BL-009 / ADR-0053）：新增 `GET /api/v1/system/list-directory` 端点（`os.scandir` 列子目录），前端用 Web 模态目录浏览器替代 macOS-only osascript。远程/非 macOS 部署时 Browse 按钮正常工作。
- **WebUI/API 默认工作目录隔离**（BL-026 / ADR-0054）：`BackgroundRunExecutor` 未提供 `working_directory` 时默认创建 `run_dir/work` 隔离目录，与 CLI `--work-dir ""` 对齐。防止 file observer 误捕获外部进程的文件变更。
- **Run 失败 traceback 存储**（BL-027）：`run.json` 新增 `error_traceback` 字段，存储完整 Python traceback；前端 error_banner 增加可展开的 Traceback `<details>`。

### Fixed
- **agent graph live-run join 边**（BL-028）：`project_events()` back-to-back join 边从 `fork_end` 提前到 `agent_start`，live run 期间 verifier 节点不再孤立平铺在画布中。
- **SSE stream 结束后 detail 不刷新**（BL-027）：run 结束后 SSE `stream_end` 触发 `onState('closed')` 但不重新拉取 `detail`，导致 UI 卡在 running 状态、error_banner 不显示 error_summary。修复为 stream 结束时重新拉取 detail + fileChanges + runs 列表。
- **reconcile 宽限期阻止逻辑**（BL-030 / ADR-0046 修订）：移除宽限期阻止已确认死亡的进程被清理的逻辑，无安全收益；频繁重启 server 导致 stale run 永远无法清理。

### Changed
- **Loops 页面切换性能**（BL-029）：移除 `read_summary()` 中 `project_events()` 死代码（每次切 loop 全量解析所有 run 的 events.jsonl）；`detail()` 去重 frontmatter 解析；`rglob` 增加隐藏目录过滤。
- **error_banner CSS**：加 `flex-wrap` + `word-break` 处理长错误消息换行。

## [0.24.1] — 2026-07-27

### Fixed
- **Phase 残留清理**（BL-022）：删除 0.24.0 遗漏的 `phase()` 函数、`PhaseGraph`、`TerminalGraphRenderer`、`_emit_phase`、`from_phase`/`only_phase` CLI/API/context 属性（10 个文件，-1215 行）
- **agent_graph fan-in 投影**（BL-023）：修复 `project_events()` back-to-back parallel 的 3 个 bug（join 边不生成、pending_join 跨组合并、fork source 错误）；新增 `fork_active` 标志
- **join-edge CSS**：`.join-edge` 虚线 + mint-strong 色，区别于 fork-edge 和 sequential
- **`.phase-node` → `.agent-node` CSS**：修复 Playwright 视觉回归

### Added
- **节点详情面板**（BL-024）：点击 agent 节点显示 label/agent_def/backend/model/exit code/时间范围
- **fork/join 投影单元测试**：single fork、back-to-back forks、fork without preceding agent
- Events scope tabs：Events / Unattributed / Malformed 切换

### Changed
- WebUI 测试：14 个 phase 相关测试修复（Phase graph → Agent graph，phase_id → call_id/label）
- Playwright fixture：移除 `phase_id` 字段

## [0.24.0] — 2026-07-27

### Removed
- **Phase 抽象**：删除 `phase()` 函数、`PhaseGraph`、`_emit_phase`、`declared_phases`、`--from-phase`/`--only-phase`（ADR-0052）。每个 `agent()` 调用即图节点，`parallel()` 产生 fork/join 边

### Added
- **AgentGraph**：agent 实例图，dagre DAG 布局（`rankdir: LR`），fork/join 边表示并行
- agent_start 事件包含 `label`、`agent_def`、`backend` 字段
- File Changes 按 `call_id` 过滤，点击节点联动

### Changed
- `file_changes.jsonl` 字段：`phase`/`phase_id` → `call_id`/`label`
- WebUI 图节点：Phase 节点 → Agent 节点（显示 label + agent_def + status）
- File Changes 面板：扁平列表，无 phase 分组
- 事件流：移除 phase 事件类型，只保留 agent_start/agent_done

### Fixed
- 重复 agent_message 事件（`_write_cache` 冗余写入）
- agent_start 事件缺少 `backend` 字段

## [0.23.0] — 2026-07-26

### Added
- CLI `--work-dir` 统一工作目录（ADR-0042 §5）：`loop run --work-dir [path|""|缺省]`，框架 chdir，loop 用相对路径

### Changed
- `parse_agent` 剥离 frontmatter（ADR-0051）：body 只含 markdown 正文，不再含 frontmatter 元数据
- webUI call-list 主显 call_id（数字），session 降 hover tooltip；phase 节点 "×N"、详情 "第 N 次执行"、EventTimeline "N 个事件"

### Fixed
- `render_template` 模板变量转 str：防 integer/None 致 `re.sub` TypeError
- pi backend `_parse_line` 用 `text_end` 消息级 event：修 `_extract_text` `"\n".join` 在流式 delta 间插 `\n` 破坏 JSON 字符串值
- event `call_id` 不再用 session fallback：runner agent_start 加 call_id，`_write_event` 删 session fallback

## [0.22.0] — 2026-07-25

### Added
- Optional ACP transport via the official Python ACP SDK (ADR-0049, AC-030): `loopflow run --transport acp --backend <native-acp>` routes to an SDK-backed ACP transport; CLI remains the default. The hand-rolled JSON-RPC plumbing is replaced by `agent-client-protocol` (asyncio stdio transport + Pydantic schema), bridged to loopflow's sync runner via a dedicated daemon-thread event loop.
- ACP notification full mapping (BR-056): `agent_message_chunk`, `agent_thought_chunk`, `tool_call_start`/`progress` (informational), and `usage_update` are all surfaced as loopflow events — completing the ADR-0021 stub.
- ACP permission auto-approve (BR-055): `request_permission` is auto-approved (fire-and-forget model), eliminating the ADR-0018 authorization deadlock.
- ACP continue (BR-057): backends declaring `loadSession`/`resume` expose continue recovery via `session/load`; best-effort and capability-gated, like the CLI path.
- `--transport` / `--backend` CLI options and a `transport` field on `POST /api/v1/runs`.

### Changed
- `agent-client-protocol` (+ pydantic) added as a runtime dependency during implementation; the optional `[acp]` extra split is deferred to a later release (AC-030-B-2 verified via the error constant).
- Mock ACP server test infrastructure (0088) enables CI-runnable ACP tests without real-backend quota; a new `agent` AC manifest profile covers AC-001~004 and AC-030 (21 scenarios, all strict-green).

## [0.21.0] — 2026-07-25

### Added
- Failure classification for agent calls (ADR-0044, AC-026): failures are categorized as auth / quota / transient / task / unknown — structured backend reporting takes precedence over stderr pattern matching; only transient failures auto-retry with the existing 3/9/27s backoff. The category is persisted in `agent_done` events and `run.json` `error_category`.
- Loop failure circuit breaker (ADR-0045, AC-027): consecutive failed runs are counted per loop in `~/.loopflow/loop_state/<loop>.json`; at the threshold (default 5, overridable via loop frontmatter `failure_threshold`) the loop is paused and its queued tasks are deferred instead of dispatched. `loopflow unpause <name>` / `POST /api/v1/loops/{name}/unpause` clears the pause manually; manual `loopflow run` is never blocked.
- Stale grace period (ADR-0046, AC-029): a stale run records `stale_since` on first detection; reconcile within the 24h grace window returns 409 `run_in_grace`, and a worker that comes back within the window reconciles naturally — its terminal write wins and clears `stale_since`.
- Explicit queue task status (ADR-0047, AC-028): queue entries carry `status` (pending / deferred / superseded), `status_reason`, and `superseded_by`; resource-locked tasks are marked deferred, `loopflow enqueue --supersede` replaces same-loop pending tasks, and deferred/superseded no longer count as dispatch errors.
- WebUI failure and circuit-breaker surfacing: run list and detail render `error_category` + `error_summary`; the Loops workspace shows the paused badge, reason, failure-streak aggregation, and an unpause action; stale runs display "Unreachable (grace period)" with the remaining window.

### Changed
- AC text aligned with verified implementation (0086): AC-010-N-2/E-2 (loop.md is mandatory per ADR-0031), AC-015-F-3/N-7/N-8, AC-016-F-3 — documentation corrected to actual behavior; 8 previously planned manifest scenarios now map to real test nodes, and all three AC manifest profiles (web / recovery / scheduling) pass in strict mode.
- Dispatch summary reports `deferred` / `superseded` buckets separately; the legacy `skipped` key is kept at 0 for compatibility.

## [0.20.1] — 2026-07-24

### Fixed
- Recovery now applies the persisted mock option from `execution_options` before backend resolution; recovering a mock-executed run no longer exits on machines without an agent CLI.
- Run start signal window raised from 2s to 15s, avoiding false `run_process_start_failed` on loaded or low-core machines.
- Run subprocesses now spawn with a fresh interpreter by default, fixing stale-environment inheritance under Python 3.14's forkserver default on Linux.
- `test_smoke` version check works on Python 3.10 (no `tomllib` dependency).

## [0.20.0] — 2026-07-24

### Added
- Multi-topic SSE transport: `run_event` and `file_changes` topics multiplexed over a single connection with independent cursors; an out-of-range `file_changes` cursor is non-fatal (ADR-0041).
- Declared phases pre-display: loop frontmatter `meta.phases` is surfaced in Loop summary/detail and merged into the Run phase graph as pending placeholder nodes (ADR-0040).
- File change observation: `phase()` snapshots and diffs the working directory into `file_changes.jsonl`, exposed via `GET /api/v1/runs/{run_id}/file-changes` (ADR-0039).
- Explicit run working directory (ADR-0042): `POST /api/v1/runs` accepts an optional absolute `working_directory`; the run subprocess chdirs into it so execution and file observation happen in the chosen project instead of the server launch directory.
- Run working directory file preview: `GET /api/v1/runs/{run_id}/file?path=` serves a read-only text preview confined to the run's working directory; clicking a file in the WebUI changed-files tree opens its content.
- Native directory picker for the New Run dialog: `POST /api/v1/system/pick-directory` opens the OS folder chooser on macOS; other platforms fall back to manual input.
- Loop args declarations (BR-047): loop frontmatter `meta.args` (name/default/description/required) is surfaced as `declared_args` in the Loop API and pre-fills the New Run dialog's key-value editor.
- Light/dark theme toggle with system-preference default and a persisted choice (BR-048).
- `GET /api/v1/system/meta` exposes the running server version.
- WebUI file changes panel: changed-files tree with per-phase action markers that follow the selected phase.

### Changed
- File observation now seeds a baseline snapshot at run start (ADR-0043): `created` only means created during a phase, and pre-existing files first touched by a phase are reported as `modified` with baseline `prev_size` — aligning the implementation with the documented AC-024-B-1 semantics.
- Runs workspace information architecture: three task-oriented columns (list / execution / file changes), unified `PanelHeader`/`SectionHeader` primitives, and a three-step type scale.
- New Run dialog arguments are edited as typed key-value rows with a JSON advanced mode instead of a raw JSON textarea.
- Intervention requests surface as a top banner in the Runs workspace only while pending; history collapses inline.
- Event display consolidated into the single center-column timeline; the duplicated right-column process output is removed.

### Fixed
- WebUI rail version was hardcoded (`v0.17`) and stale; it now reflects the running server's version from `GET /system/meta`.
- File changes region always renders an explicit empty state for legacy runs and quiet phases (AC-024-B-6/B-7).
- SSE `file_changes` topic now reaches the WebUI in real time instead of being dropped.
- The file changes drawer toggle only appears in overlay layout (≤1180px) where it has an effect.

## [0.19.1] — 2026-07-24

### Changed
- WebUI shared primitives now centralize status badges, icon buttons, empty states, metrics, facts, and scroll areas.
- Runs, Loops, Backends, event timelines, process logs, and intervention questions now share a single scrollbar treatment.

### Fixed
- Legacy `intervene(schema={"type": "boolean"})` requests now expose `true`/`false` choices in the WebUI while preserving boolean replay semantics.
- Removed the misspelled `gork` backend registration; `grok` is the only valid Grok backend name.
- `test:browser:smoke` now points at the existing Playwright `webui.spec.ts` suite.

## [0.19.0] — 2026-07-23

### Added
- Agent structured intervention vNext: Agents can return multiple `__loopflow.requests[]` in one turn.
- Intervention request options and custom-response constraints with string responses.
- Batch intervention response endpoint: `POST /runs/{run_id}/interventions/responses`.
- WebUI multi-question intervention form with one submit action.

### Changed
- `intervene()` remains a workflow routing gate and now supports `options` and `allow_custom`.
- CLI and Web workflow execution inject `intervene()` consistently.
- Intervention summaries now expose `source`, `options`, `allow_custom`, and string `response`.

### Fixed
- CLI waiting-input workflows no longer fail just because `intervene()` was not injected.
- Strict-signature workflows no longer receive unsupported framework kwargs.
- Agent intervention request IDs include call identity to avoid parallel worker collisions.

## [0.18.0] — 2026-07-23

### Added
- Grok backend and Grok ACP support.
- Verifiable recovery controls for failed and cancelled Runs, including retry and durable-session continue.
- Persistent intervention requests that can be answered after worker exit or after a waiting Run is cancelled.

### Changed
- `cancelled` now means the current execution attempt was cancelled, not that the Run identity is unrecoverable.
- `loopflow stop` on `waiting_input` preserves pending intervention requests.
- Web/API allowed actions now derive `recover_retry`, `recover_continue` and `respond` from recovery boundaries and pending requests.

### Fixed
- Atomic/isolated cancelled worker boundaries no longer expose durable-session continue.
- `src/loopflow/__init__.py` version is synchronized with package metadata for release.

## [0.17.2] — 2026-07-21

### Added
- Run 创建时向 `runs/runs_index.jsonl` 追加真实工作目录、Run 分组目录和 Run ID 的无损映射。

### Changed
- WebUI Runs、Loops 与 Backends 工作区按原型设计语言重新整理，Run 事件正文改为类型化 Markdown 渲染。
- Phase graph 成为阶段选择的唯一入口，移除重复的 Phase occurrence 导航。

### Fixed
- 切换 Loop 时不再以新 Loop 名请求上一个 Loop 的 Agent 文件。
- Runs 侧栏优先显示索引记录的真实工作目录，旧 Run 保留 `lf_<pwd-path>` 回退显示。

## [0.17.1] — 2026-07-18

### Fixed
- **Goal loop schema retry**: schema retry 归 goal loop 跨迭代管理，不再在 `_execute_once` 内重复
- **backend_sid 丢失**: `_execute_once` 失败时 `backend_sid` 附加到 `AgentError`，goal loop 正确 resume 同一 session
- **缓存丢失**: `_execute_once` 失败时写入缓存，resume 可看到已尝试状态

## [0.17.0] — 2026-07-18

### Added
- **loop.md**：loop 声明式定义文件，frontmatter 给机器读，body 给 Agent 和人类读。`discovery` 优先读 loop.md，回退到 workflow.py meta
- **queue 模块**：`infrastructure/queue.py`，文件队列（`~/.loopflow/queue/`），支持 enqueue / dequeue / list / size
- **resource lock**：`lock.py` 扩展 resource 粒度锁，TTL 30 分钟自动清理
- **dispatch 模块**：`infrastructure/dispatch.py`，扫描队列、优先级排序、资源锁、执行 loop
- **CLI 命令**：`loopflow enqueue`（入队）、`loopflow dispatch`（调度执行）
- 外部调度器文档：macOS 推荐 launchd，Linux 用 cron/systemd timer

## [0.16.0] — 2026-07-14

### Changed
- **DDD 四层架构**：domain / infrastructure / application / presentation
- `Agent` 类 → `AgentRunner` 类 + 模块级函数 `marshal()` 等
- `marshal()` 接受 `Capabilities` 值对象而非 `Backend` 实例
- `BaseBackend.capabilities` property，各后端覆写
- `parse_agent()` / `list_agents()` → `infrastructure/repository.py`
- `discovery.py` / `lock.py` / `skills.py` → `infrastructure/`
- `runtime.py` 582 → 197 行，纯应用协调
- 后端文件移入 `infrastructure/backends/`，传输文件移入 `infrastructure/transports/`
- CLI / graph / display 移入 `presentation/`

### Removed
- `Agent` 类（贫血 marshalling 工具）
- 所有兼容层（旧 `agent.py` / `graph.py` / `cli.py` / `runner.py` / `backends/` / `transports/` / `display/`）
- `_get_ctx()` / `_get_mock_mode()` 全局状态 workaround

### Fixed
- Backend 双重创建（marshalling 查询 + 执行调用）
- 两条执行路径重复（统一为 `AgentRunner._execute_once()`）
- infrastructure → presentation 依赖方向违规
- 8 个 TYPE_CHECKING 死引用（`loopflow.agent` → `loopflow.domain`）

## [0.13.0] — 2026-07-12

### Changed
- **破坏性变更**：Agent frontmatter 格式对齐 Claude Code subagent schema
- 删除 `requires` 包装层，所有字段提升到顶层
- `requires.params` → `input`（JSON Schema，与 `output` 对称）
- `requires.mcps` → `mcpServers`（Claude Code 对齐）
- `requires.skills` → `skills`（顶层）
- `requires.env` → `env`（顶层）
- 新增 `model`、`isolation` 字段
- 新增 `tools`、`disallowedTools`、`maxTurns`、`hooks`、`effort`、`color`、`background`、`memory`、`permissionMode` 字段（接口预留，暂未实现）

### Removed
- `AgentRequires` 类：后端直接接收 `AgentDef`

### Fixed
- 后端 `__init__` 接受 `thought_handler` 参数（kimi/gemini/qwen/kiro/opencode）
- 集成测试适配 `lf_<pwd>/<run_id>/` 运行目录结构
- `set_mock("shell")` → `set_mock("bash")`

## [0.12.0] — 2026-07-11

### Added
- JSON 提取：text 模式后端回复包裹在 markdown 中时，使用 `jsonschema` 验证 + schema keys 匹配提取 JSON 对象，跳过 retry
- `agent.extract_json()` 和 `agent.validate_json()` 函数
- `jsonschema` 项目依赖

### Fixed
- `json.dumps` 缺少 `ensure_ascii=False`：中文不再被转义为 `\uXXXX`
- `json.dumps` 缺少 `separators`：JSONL 输出不再有多余空格
- 文件写入缺少 `encoding="utf-8"`：非 UTF-8 系统上中文不损坏

## [0.11.0] — 2026-07-11

### Changed
- 缓存事件格式迁移：`agent_text` → `agent_message_chunk`（ACP 归一化 schema）
- kimi 后端：strip `•` 前缀，输出干净文本
- `CliBackend` 新增 `_normalize_line` 钩子，子类可重写以归一化 stdout 行
- `_extract_text` 向后兼容 `agent_text` 和 `agent_message_chunk` 两种类型

### Added
- codex 后端：`turn.completed` 事件处理（usage 提取占位）
- Spec v8：ACP 缓存 schema 定义，BR-016（ACP 归一化规则）

## [0.10.0] — 2026-07-11

### Changed
- ACP auto-detection 禁用：所有后端默认走 CLI 传输，ACP 仅在 `transport="acp"` 时启用
- Agent 输出实时写入 `{seq}.jsonl`：执行期间可 `cat` 查看进度，resume 通过 `agent_done` 正确区分进行中/已完成
- 内部命名统一：`backend_name` → `backend`（`_make_backend`、`_run_subagent`）

### Fixed
- kimi ACP 模式 tool call 死锁：ACP 协议要求 client 授权 tool call，loopflow 未对接导致永久等待。CLI 模式无此问题

## [0.9.0] — 2026-07-11

### Added
- `lf_<pwd>/<uuid>` 运行目录结构：按工作目录分组，完整 UUID 标识
- 文件系统布局：pwd 工作目录 vs `~/.loopflow/` 数据目录，worktree 在 pwd 下
- `agent()` 新增 `timeout` 参数，默认无超时
- Agent 输出实时流式到 stderr 和 events.jsonl，`[agent]` 前缀

### Changed
- `agent_start` 事件在 agent 调用前 emit（而非完成后）
- `AgentError` 消息包含 CLI stderr 输出，便于诊断
- 运行实例通过 `_find_run_by_id()` 搜索所有 `lf_*/` 目录，而非仅当前 pwd

### Fixed
- `CliBackend` 接受 `**kwargs`，修复 claude/codex/pi 等后端
- Resume 时 counter 从 `run.json` 恢复

### Removed
- `registry.py`：session 管理功能已由 `run.json` + `events.jsonl` + counter 缓存替代

## [0.8.2] — 2026-07-10

### Fixed
- Ctrl+C 优雅退出：保存 `stopped` 状态和 counter，允许 resume 继续

## [0.8.1] — 2026-07-10

### Changed
- ADR 0017：skill 声明边界 — agent 仅声明 WHAT，WHERE 由环境文件管理
- 移除 SKILL.md 的 `path`/`source` 字段，保留 `name`/`description`
- Skill 存储隔离：`.skills/`（项目本地），通过 `SKILLS_HOME` 环境变量
- 推荐 pixi 作为环境管理器（`[activation.env]` 原生隔离），不约束格式
- 环境文件提醒消息：存在时打印激活命令

## [0.8.0] — 2026-07-10

### Added
- `meta.requires.environment`：workflow 声明环境文件路径（如 `environment.yml`），`loopflow run`/`loopflow resume` 启动时校验文件存在
- 松散校验：检查文件存在，不激活环境，不安装依赖，不解析内容
- 隔离层级体系：声明层（environment 文件）→ 文件系统（worktree）→ 环境激活（conda，未来）→ 完整隔离（容器，未来）

## [0.7.0] — 2026-07-10

### Added
- `requires.skills`：agent 声明依赖的 skill 名称列表，loopflow 自动查找并注入到 system prompt
- Skill 发现：按 `~/.agents/skills/` → `~/.loopflow/skills/` 顺序查找 `SKILL.md`
- 双轨策略：后端支持原生 skill 参数时优先使用（kimi `--skills-dir`、pi `--skill`），否则 prompt 注入
- Skill prompt 注入格式：仅注入名称+描述+路径，agent 按需读取完整 skill 内容

### Changed
- `_run_subagent()` 新增 `requires` 参数，透传 AgentRequires 到后端
- bio-reproducer reader agent 声明 `requires.skills: [paperutils]`

## [0.6.0] — 2026-07-09

### Added
- `--mock auto`：根据 agent 的 `output` schema 自动生成 mock 数据，无需 AI 后端即可验证 workflow 完整流程

### Changed
- `--mock` 从布尔标志改为模式选择：`--mock bash`（shell 执行）或 `--mock auto`（schema 生成）
- 删除 `echo` mock 模式，`auto` 覆盖其场景

### Fixed
- Mock 模式不再因自然语言 prompt 导致 shell 执行失败，`auto` 模式生成合法数据

## [0.5.0] — 2026-07-09

### Added
- `meta.state`：声明式工作流状态变量，`state.key` 属性访问，每次 `agent()` 成功后自动持久化到 `state.json`
- `state` 参数：`run()` 新增第 8 个参数，resume 时自动恢复已保存的状态
- `isolation="worktree"`：agent 在独立 git worktree 中执行，并发安全，不自动清理

### Changed
- CLI transport 支持 `cwd` 参数，worktree 隔离时 agent 子进程在 worktree 目录中执行
- `run()` 签名向后兼容：`state` 参数仅在函数签名包含时传入

## [0.4.0] — 2026-07-09

### Added
- `output` 字段：agent 定义新增可选的 JSON Schema 输出契约，与 `requires.params` 对称
- Schema prompt 注入：当 agent 有 `output` 时，自动将 schema 注入 prompt，要求 agent 返回纯 JSON
- Schema 重试：JSON parse 失败时自动重试（默认最多 3 次），每次提醒 agent 按 schema 输出
- `AgentError` 异常：infra 失败（后端崩溃、超时、非零退出）抛 `AgentError`，crash 后由 resume 恢复
- `max_retries` 参数：`agent()` 新增，控制 schema 重试次数

### Changed
- `parse_agent()` 重构：使用 `yaml.safe_load()` 解析 frontmatter，支持嵌套 output schema
- `agent()` 失败时抛 `AgentError` 而非返回 `None`（mock 模式除外）
- 缓存仅写入成功的 agent 调用（非零退出不再缓存）

### Fixed
- Mock 模式下非零退出码不再导致 AgentError（mock 是测试工具，exit_code 无意义） 

---

## [0.3.0] — 2026-07-09

### Added
- `meta.phases` 声明：workflow.py 可在 meta 中声明预期阶段列表，运行时验证格式
- Agent 事件 `phase` 归属：`agent_start` 事件自动携带当前 phase 上下文
- `agent_def` 参数：`agent("指令", agent_def="reader")` 加载 `agents/<name>.md` 作为系统提示词
- `{{param}}` 模板渲染：agent body 支持占位符，调用时通过 kwargs 替换
- `load_loop()` 返回 `(mod, meta, loop_dir)` 三值，支持 agent 定义文件查找
- 用户文档 `README.md`

### Changed
- `agent.py` 移出 coverage omit，`render_template` 纳入覆盖率统计
- 覆盖率从 69% 提升至 70%

---

## [0.2.3] — 2026-07-09

### Fixed
- 无 mock 模式后端卡死无反馈：添加 5 分钟默认超时、进度提示、错误消息
- `--watch` 模式日志与图形冲突：使用 `console.log()` 暂停 Live 再输出

---

## [0.2.2] — 2026-07-09

### Added
- `loopflow run` 和 `loopflow resume` 结束自动渲染执行图
- `--watch` 标志：Rich Live 实时增量渲染执行图
- `--mock` 标志：无需安装 AI 后端即可测试
- `--no-graph` 标志：关闭 status 图形输出

### Changed
- `phase()` 运行时自动记录到 PhaseGraph，支持 live 更新
- 手动测试流程：一条命令完成运行+绘图

---

## [0.2.1] — 2026-07-09

### Added
- 多行分支渲染：fork/merge 节点使用 box-drawing 字符（`└─→` `└──`）分叉展示
- 分支路径上的回边标注（`└── Start (第N轮, 回边)`）
- PhaseGraph: `forward_edges()`, `back_edges()`, `fork_nodes()`, `merge_nodes()`, `children()` 方法
- E2E 测试：多分支 + 回边组合场景

### Changed
- 渲染器从单行模式改为多行树形模式：主干 + 分支 + 回边分行展示
- 覆盖率从 68.62% 提升至 70.11%

---

## [0.2.0] — 2026-07-08

### Added
- PhaseGraph 执行图：纯数据结构（`graph.py`），邻接表 + 边计数 + 环检测，不依赖任何渲染库
- TerminalGraphRenderer：Rich 终端渲染，支持线性/回边（循环）/分支三种布局
- `phase()` 和 `agent()` 自动写入 events.jsonl 事件流
- `loopflow status --graph` 显示执行图，`--no-graph` 关闭
- 21 个 graph 单元测试 + 4 个集成测试

### Changed
- `phase()` 和 `log()` 除 stderr 输出外，同时写入结构化事件到 events.jsonl
- `loopflow status` 不再统计 events.jsonl 为 agent 调用

---

## [0.1.0] — 2026-07-08

### Added
- Loop 定义：以文件夹形式组织（workflow.py + agents/），支持 `~/.loopflow/loops/` 目录
- Workflow Runtime：agent/parallel/pipeline/phase/log/args/workflow API，与 Claude Code Workflow 签名一致
- 崩溃恢复：序号计数器重放，已完成 agent 调用自动跳过，对 workflow 作者透明
- CLI 命令：loopflow run / resume / status / list / stop
- 多后端支持：从 subagent-skills 复用 8 种后端适配器（kimi/claude/codex/pi/opencode/qwen/kiro/gemini）
- 测试框架：pytest + coverage.py，50 个测试（41 unit + 9 integration），59% 覆盖率
- CI/CD：GitHub Actions workflow，Python 3.10 + 3.14 矩阵测试
- 文档体系：vision.md, Spec, 8 ACs, 8 ADRs, 5 Plans

### Changed
- 从 subagent-skills 复制 backends/transports/agent/registry/lock，精简移除 goal/swarm/send/cancel 等不需要的功能

### Fixed
- Runtime 捕获真实后端输出（text_handler），修复了 mock 文本硬编码的问题
