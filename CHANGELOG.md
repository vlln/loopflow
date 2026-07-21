# Changelog

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
- **CLI 命令**：`loop enqueue`（入队）、`loop dispatch`（调度执行）
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
- `meta.requires.environment`：workflow 声明环境文件路径（如 `environment.yml`），`loop run`/`loop resume` 启动时校验文件存在
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
- `loop run` 和 `loop resume` 结束自动渲染执行图
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
- `loop status --graph` 显示执行图，`--no-graph` 关闭
- 21 个 graph 单元测试 + 4 个集成测试

### Changed
- `phase()` 和 `log()` 除 stderr 输出外，同时写入结构化事件到 events.jsonl
- `loop status` 不再统计 events.jsonl 为 agent 调用

---

## [0.1.0] — 2026-07-08

### Added
- Loop 定义：以文件夹形式组织（workflow.py + agents/），支持 `~/.loopflow/loops/` 目录
- Workflow Runtime：agent/parallel/pipeline/phase/log/args/workflow API，与 Claude Code Workflow 签名一致
- 崩溃恢复：序号计数器重放，已完成 agent 调用自动跳过，对 workflow 作者透明
- CLI 命令：loop run / resume / status / list / stop
- 多后端支持：从 subagent-skills 复用 8 种后端适配器（kimi/claude/codex/pi/opencode/qwen/kiro/gemini）
- 测试框架：pytest + coverage.py，50 个测试（41 unit + 9 integration），59% 覆盖率
- CI/CD：GitHub Actions workflow，Python 3.10 + 3.14 矩阵测试
- 文档体系：vision.md, Spec, 8 ACs, 8 ADRs, 5 Plans

### Changed
- 从 subagent-skills 复制 backends/transports/agent/registry/lock，精简移除 goal/swarm/send/cancel 等不需要的功能

### Fixed
- Runtime 捕获真实后端输出（text_handler），修复了 mock 文本硬编码的问题
