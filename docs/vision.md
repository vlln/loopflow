---
title: Vision — 项目顶层愿景
description: 全局顶层愿景，一句话说明项目的核心目标和约束。
type: vision
# status: 见 SKILL.md status 有效值表
status: proposed
created: 2026-07-07T12:00:00Z
---

<!-- 全局唯一，项目启动一次性定稿。仅重大业务转型才修订。 -->

---

## 一、业务目标

loopflow 是一个独立的 AI Agent 循环编排工具。以 Agent（完整 ReAct 实体）为基本单元构建循环工作流——Agent 之间可以形成 while 循环、条件分支、迭代收敛，而非仅 DAG 拓扑。解决的核心问题：现有工作流工具（Dify、LangChain、subagent-skills）以函数/LLM 调用为原语，无法以 Agent 为单元做循环编排。

- 让开发者用 Python 代码定义 Agent 循环（workflow.py），自由控制循环条件、退出逻辑、状态累积
- 每个 Agent 有明确的能力边界（通过 Markdown 定义文件声明），可被循环引用
- 崩溃恢复对 workflow 作者完全透明——agent 调用按序号缓存，resume 时自动跳过已完成调用
- 一次定义，多次运行，每次运行产生独立实例（runs/），可查看状态、回放日志
- 复用 subagent-skills 的多后端适配层，支持 kimi/claude/codex/pi/opencode/qwen/kiro/gemini 

---

## 二、用户范围

- 需要编排多个 AI Agent 协作的开发者
- 需要迭代式 Agent 工作流（如代码审查 → 修复 → 再审查，直到通过）的团队
- 已有 subagent-skills 使用经验的用户（API 兼容，迁移成本低）
- 运行环境：macOS / Linux，Python 3.10+，终端 CLI 

---

## 三、长期理想形态

- loop 定义是文件夹，包含 workflow.py + agents/，可版本控制、可分享、可复用
- 任意 CLI Agent 后端可插拔使用，后端细节对 loop 作者透明
- 运行实例管理完善：loop run / loop resume / loop status / loop list
- 社区贡献的 loop 模板库，覆盖常见场景（代码审查、文档生成、测试修复、重构等）
- 与 subagent-skills 共享底层后端代码，但上层各自独立演进

---

## 四、不定义

<!-- 明确本文件不定义什么，避免 Agent 越界 -->

本文件不定义实现细节、技术选型、接口定义、非功能指标、编码规范。这些分别属于 Spec、ADR、CONTRIBUTING.md。