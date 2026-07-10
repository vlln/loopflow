# Changelog

## [Unreleased]

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