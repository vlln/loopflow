# Changelog

## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

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