# Backlog

工程需求池。DESIGN 阶段的迭代候选只能从这里拉取；选定后状态改为 `planned` 并记录关联迭代。

状态值：`candidate`（待评估）→ `planned`（已排入迭代）→ `done`（已闭环）/ `dropped`（放弃，需注明原因）

| 编号 | 标题 | 描述 | 来源 | 状态 | 关联迭代 |
|------|------|------|------|------|---------|
| BL-001 | 失败分类驱动的重试/续接策略 | 将 agent 调用失败分类（auth/quota、poisoned、transient、task），按类别决定重试、会话续接（continue）或直接失败，替代统一退避重试 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-002 | 失败熔断 + 告警节流 | 连续失败达到阈值自动暂停；失败提示只在状态转变和周期性提醒时出现，防告警疲劳 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-003 | reconcile 失联宽限期 | 失联 ≠ 失败：run 失联后进入宽限期，宽限期内恢复可调和为成功，避免笔记本睡眠等场景误判 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-004 | 调度语义 deferred/supersede/misfire | 队列中等待的任务被取代标记 skipped、条件不满足挂起 deferred、错过触发补发，均不计为失败 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-005 | evolve run 自我进化 | 每 N 次 run 触发一次用 run 历史重写 loop 本身的 run（收紧 brief、折叠机械步骤）。业务层 vs 产品层未定 | loopany-platform 调研 2026-07-25 | candidate | — |
| BL-006 | loop 嵌套编排 | workflow 嵌套/组合的下一个大特性，方向未想好 | loopany-platform 调研 2026-07-25 | candidate | — |
| BL-007 | web profile manifest 漂移修复 | 以 test 容器补齐 web profile AC manifest | 0.20.0 发布评估 | candidate | — |
| BL-008 | loop args schema 服务端校验 | Web/API 侧对 loop args 做 schema 校验 | 0.20.0 发布评估 | candidate | — |
| BL-009 | 非 macOS 目录选择器 | Web UI 目录选择器在非 macOS 平台的适配（ADR-0053：GET /system/list-directory + Web 模态浏览器替代 osascript） | 0.20.0 发布评估 | done | 0096-web-directory-picker |
| BL-010 | AC-010-N-2/E-2 契约漂移裁决 | AC 文本期望 loop.md 缺失/坏 YAML 时回退 workflow.py meta，但 ADR-0031 后实现为强制 loop.md 缺失即跳过；需 DESIGN 裁决对齐文档或实现 | 0081 scheduling profile 落地时发现 | done | 0.21.0 |
| BL-011 | npm audit 既有失败修复 | brace-expansion 经 @vitest/coverage-v8 链 5 high，中断 mr-gate 链 | 0081 mr-gate 验证时发现 | planned | 0.25.0 |
| BL-012 | SSE file_changes OSError 未按 topic 隔离 | AC-016-F-3 实证发现：fc 读取 OSError 落入 server 通用 except，发无 topic 的 stream_error，与 AC-016-E-3 的 topic 隔离行为不一致；需裁决是缺陷还是可接受形态 | 0086 清理时发现 | candidate | — |
| BL-013 | 版本号单源化 | 版本号双写（pyproject.toml + src/loopflow/__init__.py）易不同步，0.21.0 release 冒烟时暴露 | 0.21.0 复盘 | planned | 0.25.0 |
| BL-014 | 采用官方 Python ACP SDK 替换手搓 ACP 管道 | acp.py/acp_backend.py 手搓 JSON-RPC 是未验证 stub（runtime 从不传 transport=acp，ACP 路径生产里是死的）；用官方 agent-client-protocol 替换协议管道，保留 loopflow 自己的 session/recovery/queue；CLI 保留为主传输，ACP 成为真正可用的可选路径 | 0.21.0 后架构调研（acpx 对比） | done | 0.22.0 |
| BL-015 | agent-client-protocol 划为可选 extra [acp] | 0.22.0 实现阶段放主依赖区，ADR-0049 §8 定位为可选 extra 未落地；默认安装不应含 pydantic | 0.22.0 复盘 | candidate | — |
| BL-016 | grok ACP `_meta` system prompt 在 SDK 路径的等价处理 | SDK session/new 不接受 _meta，0089 改走 prompt 文本拼接，需验证 grok 行为不回归 | 0.22.0 复盘 | candidate | — |
| BL-017 | render_template 模板变量转 str | `_replace` 返回 `str(value)`，防 integer/None 模板变量致 `re.sub` TypeError（如 `{{ breadth }}` 传 int） | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-018 | parse_agent 剥离 frontmatter | body 只含 markdown 正文（不含 frontmatter），避免 system prompt 含元数据，且 CLI backend（pi）把 prompt 作 argv 时 `---` 被当 unknown option | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-019 | pi backend 用 text_end 消息级 event | `_parse_line` 取 `text_end` 的完整 content，弃 `text_delta`（token 级），修 `_extract_text` `"\n".join` 在流式 delta 间插 `\n` 破坏 JSON 字符串值 | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-020 | CLI `--work-dir` 统一工作目录 | `loop run --work-dir [path|""|缺省]`，框架 chdir 到 workdir；loop 不处理工作目录，agent 用相对路径（当前目录）。统一 backend cwd 与产出目录，消除 run_dir/work 冗余 | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-021 | webUI call/occurrence 显示简化 | call-list 主显 call_id（逻辑编号），session 降 tooltip；节点 "×N"、详情 "第 N 次执行"、EventTimeline "N 个事件"——消除 call_id 重复（session 含 call_id 又单独显示）+ occurrence/events 措辞区分 | devloop DESIGN 2026-07-26 | done | 0.23.0 |
| BL-022 | phase 残留清理 | runtime.py 仍保留 `def phase()`、`_emit_phase` import、`from_phase`/`only_phase` 逻辑——ADR-0052 声称删除但实际未删；14 个测试基于 phase 红灯 | 0.24.0 发布后排查 | done | 0.24.1 |
| BL-023 | agent_graph fan-in 投影修复 | `project_events()` back-to-back parallel 的 join 边不生成、`pending_join` 跨组合并、fork source 解析错误；join-edge 无 CSS 区分 | 0.24.0 发布后排查 | done | 0.24.1 |
| BL-024 | agent 节点详情面板 | 点击节点仅过滤事件/文件，无合并详情面板（events + files + call info 一起展示） | 0.24.0 发布后排查 | done | 0.24.1 |
| BL-025 | Playwright fixture phase_id 清理 | `webui.spec.ts` mock fixture 仍含 `phase_id` 字段 | 0.24.0 发布后排查 | done | 0.24.1 |
| BL-026 | WebUI/API 默认工作目录隔离 | `BackgroundRunExecutor.start()` 在 `working_directory` 未提供时 fallback 到 `Path.cwd()`（server cwd，通常为项目根），导致 file observer 误捕获外部进程的文件变更。CLI 已有 `--work-dir ""` 隔离模式（BL-020），WebUI/API 路径缺少等价机制。修复：未提供时默认创建 `run_dir/work` 隔离目录，与 CLI `--work-dir ""` 对齐 | deep-research run bf862b1d 实测 2026-07-27 | done | 0097 |
| BL-027 | SSE stream 结束后 detail 不刷新 | run 结束（done/failed）后 SSE `stream_end` 只设 `streamState`，不重新拉取 `detail`，导致 UI 卡在 running 状态、error_banner 不显示 error_summary。秒败的 run 尤为明显 | deep-research run 实测 2026-07-27 | done | 0099 |
| BL-028 | agent graph live-run join 边缺失 | `project_events()` back-to-back join 边只在 fork_end 生成，live run 期间 verifier 节点出现但无边连接 researcher，独立平铺在画布中 | deep-research run 实测 2026-07-27 | done | 0098 |
| BL-029 | Loops 页面切换延迟 | `read_summary()` 中 `project_events()` 死代码导致每次切 loop 全量解析所有 run 的 events.jsonl；`detail()` 重复读 frontmatter；`rglob` 无隐藏目录过滤 | 用户报告 2026-07-27 | done | 0096 |
| BL-030 | reconcile 宽限期阻止逻辑移除 | 宽限期阻止已确认死亡的进程被清理，无安全收益；频繁重启 server 导致 stale run 永远无法清理（ADR-0046 修订） | 用户报告 2026-07-27 | done | 0096 |
| BL-031 | agent 失败重试缺乏详细错误原因 | run/agent 失败时 `error_summary` 仅记录顶层错误类别（如 `validation_failed`），不包含具体原因（如 schema 校验失败时应显示哪个字段不匹配、期望类型 vs 实际值）。应在 `error_summary`/`error_traceback` 中补充上下文信息，降低排查成本 | 用户报告 2026-07-27 | done | 0.25.0 |
| BL-032 | WebUI failed run 错误信息占用过多空间 | error_banner 在 run failed 时展开占据大量空白，影响其他面板可见性。应收紧布局：可折叠、限制高度、截断长文本 | 用户报告 2026-07-27 | done | 0.25.0 |
| BL-033 | Runs 左栏显示 run_id 而非项目目录 | 左栏 run 列表只显示 UUID（如 `4e1603c7...`），用户无法辨别哪个 run 对应哪个项目。应显示 working_directory 的目录名（如 `bio-reproducer`、`claroai-paper01`） | 用户报告 2026-07-27 | done | 0.25.0 |
| BL-034 | 远程 run 文件预览失败 | 工作目录在服务器上不存在时（远程 run 路径不可达、临时目录已清理），`resolve_working_directory` 返回 None，文件预览失败。应兜底到 `run_dir/work` 隔离目录 | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-035 | Events 重复渲染 | `agent_start` 在 infra-retry 每次迭代都写入 events.jsonl（重试时多余）；`agent_session` 同一 session_id 被写入多次。需去重 | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-036 | Claude Code 后端显示为 unknown | auto-detect 后 `backend_name` 仍为 None 传给 AgentRunner，`agent_start` 事件 backend 字段为空，前端显示 "backend unknown" | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-037 | File changes 文件夹不可折叠 | `ChangeTreeDirView` 无展开/折叠功能，树始终全展开。需加 toggle state + chevron 图标 | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-038 | Loops 页面混入运行时状态 | Loops 定义页显示 paused/failure_streak 等 run 级状态，应只展示定义信息 | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-039 | 切换 Runs 时卡顿 | 切换 run 时旧 detail 未清空，React 用旧数据重渲染（含 AgentGraph key 变化导致重挂载） | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-040 | Backends API 对 missing 后端也调用 _make_backend | 9 个后端中 7 个 missing 也创建实例只为读 capabilities，浪费开销 | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-041 | 切换页面卡顿 + missing catch | tab 切换卸载/重挂载组件丢失 state 重新发 API；LoopsWorkspace api.loops() 缺 .catch() | 用户报告 2026-07-28 | done | 0.25.1 |
| BL-042 | 跨 agent 文件依赖声明与校验 | agent 定义可声明产物文件（output）与前置依赖文件（input 引用上游产物），框架在 agent 调用前校验依赖文件存在性，缺失时报错/重试。当前各 loop 只能在 workflow.py 手写 `Path.exists` 检查防 LLM 幻觉完成（返回 complete 但未写产物），属于通用需求 | bio-reproducer loop 迁移 0.25.1 讨论 2026-07-28 | candidate | — |
| BL-043 | phase 级重做入口（replay 缓存作废） | recover 仅支持失败点 retry/continue，缺少"从指定 call/label 起作废 replay 缓存并重新执行"的原生机制（如 validate 发现问题后需重做上游 run 阶段）。当前 loop 侧只能用 workflow 参数（resume_from）跳过已完成调用，是业务层补丁；引擎层应考虑 recover --from <call_id/label> 或按 label 的缓存作废 | bio-reproducer loop 迁移 0.25.1 讨论 2026-07-28 | candidate | — |
| BL-044 | CLI intervene 应答通道 | `loop run` 进入 `waiting_input` 后 CLI 无任何提示和应答命令，用户以为 run 卡死（只能另开 WebUI/API 应答）。框架层方案：CLI 前台 run 监听 waiting_input 并在终端内联提问（stdin 可用），或至少打印应答指引（web URL / API 路径） | bio-reproducer loop 迁移 0.25.1 讨论 2026-07-28 | done | 0.26.0 |
| BL-045 | waiting_input 的无人值守处理策略 | headless/沙箱环境（benchmark、CI）中 run 进入 `waiting_input` 无人应答，只能空等到外部墙钟超时，浪费整个执行窗口。框架应提供策略：intervene 支持声明 default answer + timeout（超时取默认值继续），和/或启动时声明 unattended（遇 waiting_input 立即失败并给出明确错误，而非挂起） | bio-reproducer benchmark 接入讨论 2026-07-28 | done | 0.26.0 |
| BL-046 | agent 侧 waiting_input 协议不可发现 | `runner.py` 支持 agent 输出 `{"__loopflow":{"status":"waiting_input",...}}` 触发等待，但该协议未写入任何 agent 可见提示（marshalling 的 goal 模式 hint 只注入 `__goal`），agent 无法发现；且 continue 恢复要求 backend 同时具备 `resume_session` + `durable_session_id`，不满足时抛 `continue_not_supported`。应在 schema hint 中告知协议并在能力不满足时明确降级，或移除该路径 | bio-reproducer loop 迁移 0.25.1 讨论 2026-07-28 | planned | 0.27.0 |
| BL-047 | 单 agent 运行入口（评测/调试） | ADR-0052 删除 `--only-phase`/`--from-phase` 后，无法从 CLI 单独运行 loop 中的某个 agent_def。评测（component case 单 phase 验证）和调试（只重跑某个 agent 看输出）场景需要官方入口，如 `loop run <loop> --agent <name>` 或 `loop agent <loop> <name>`；当前只能手写临时 workflow 绕行 | bio-reproducer evals 迁移 0.25.1 时发现 2026-07-28 | done | 0.26.0 |
| BL-048 | AC-001-F-2 pi argv `---` 进程测试缺失 | BL-018 追加的 AC-001-F-2（pi backend 把 prompt 作 argv 时 `---` 被当 unknown option 的回归测试）无对应测试节点；agent manifest 中为 planned::，SYSTEM_TEST 严格模式会拦截。需要 pi backend 环境或等价的 argv 级断言 | 0.26.0 TEST_INFRA 增量检查发现 2026-07-28 | done | 0103 |
| BL-049 | check-ac-manifest --write 后无早退 | `--write` 重新生成 manifest 后仍以严格模式（无 --allow-planned）校验，新生成的 planned:: 节点必然报错，误导为失败；应写后跳过校验或自动 allow-planned | 0.26.0 TEST_INFRA 增量时发现 2026-07-28 | candidate | — |
| BL-050 | web profile manifest 无 TEST_NODES 机制 | `tests/web_support/ac_manifest.py` 的 `generate_manifest` 对所有场景硬编码 `planned::` 节点（无 TEST_NODES 映射表），web profile 86 场景永远无法通过严格模式；mr-gate.sh 在 SYSTEM_TEST/RELEASE 阶段走严格分支必然在 web profile 失败（0.26.0 SYSTEM_TEST 实证 exit=1）。0.25.x 的 SYSTEM_TEST 实际只跑测试套件未跑严格 manifest。需为 web profile 补 TEST_NODES 机制（映射 vitest/Playwright 节点）或重新定义其严格语义 | 0.26.0 SYSTEM_TEST 发现 2026-07-28 | done | 0109 |
| BL-051 | WebUI 二进制文件预览（图片/PDF） | file changes 面板点击 PDF/PNG 等二进制文件时显示 `file_not_previewable`（`preview()` 拒绝含 `\x00` 的文件）。需新增 raw 文件端点流式返回二进制内容（带正确 Content-Type），preview API 对图片/PDF 返回 `encoding:"raw"` + `raw_url`，前端用 `<img>`/`<iframe>` 渲染。支持格式：png/jpg/gif/svg/webp/bmp/ico/pdf，上限 50 MiB | bio-reproducer 远端 run 文件预览失败 2026-07-29 | planned | 0.27.0 |
| BL-052 | loop run 默认追加 prompt 参数 | 所有 loop 运行应有一个 `--prompt`/`--append-prompt` 参数，允许用户输入任意字符串追加到每个 agent 调用的 prompt 末尾（或作为 system prompt 补充）。用于调试和临时干预，不必修改 agent 定义或 workflow | 用户 2026-07-29 | planned | 0.27.0 |
| BL-053 | New Run 目录选择器支持创建文件夹 | WebUI New Run 对话框的 Browse 目录选择器目前只能浏览和选择已有目录，不可创建新文件夹。应加"新建文件夹"按钮 | 用户 2026-07-29 | candidate | — |
| BL-054 | New Run 自动填写 loop 声明的 args keys | WebUI New Run 对话框的 Arguments 编辑器应自动预填 loop 的 `loop.md` 中 `args:` 声明的参数名（key），用户只需填值。当前完全空白，用户需手动输入参数名 | 用户 2026-07-29 | planned | 0.27.0 |
| BL-055 | ADR-0052 Web 契约传导与 strict 覆盖补齐 | active Spec/AC/Interface 仍要求已删除的 PhaseGraph、phase occurrence、declared_phases/from_phase；Web strict 语义审查另发现有效 AC 只有局部测试。先对齐为 AgentGraph/call_id/label，再补完整测试与必要产品行为 | 0109 TEST_INFRA 语义审查 2026-07-29 | planned | 0.27.0 |
