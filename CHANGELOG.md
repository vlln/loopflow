# Changelog

## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

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