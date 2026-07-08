---
title: 01-plan-backend
description: 精简从 subagent-skills 复制的后端代码，移除 loopflow 不需要的接口
type: plan
status: pending
created: 2026-07-07T12:00:00Z
---

# 01-plan-backend: 后端层精简

## Context

subagent-skills 的 backends/transports/agent/registry/lock 已复制到 `src/loopflow/` 下。需要移除 loopflow 不需要的部分，对齐 ADR-0003 的约束。

## Request

1. 从 `BaseBackend` 移除 `list_sessions` 方法
2. 从 `registry.py` 移除 goal、swarm、send、cancel、queue 相关方法
3. 从 `agent.py` 移除不需要的字段（如 subagent-skills 特有的 extensions）
4. 确保所有 import 使用 `loopflow.` 包路径前缀

## Output Format

修改后的源文件，通过现有 smoke tests 和新增的单元测试。

## Constraints

- 不修改 backend 适配器的 create_session/resume_session/close 逻辑
- 不修改 transports 层
- 保留 diagnostics.py（后端检测和安装指引）
- 修改后 `uv run pytest tests/unit/ -v` 全部通过

## Checkpoint

1. `BaseBackend` 只有 create_session, resume_session, close 三个方法
2. `registry.py` 无 goal/swarm/send/cancel/queue 相关函数
3. 所有 smoke tests 通过
4. 新增 backend 精简的单元测试

## Steps

1. 精简 `base.py`：移除 list_sessions
2. 精简 `registry.py`：移除 goal/swarm/send/cancel/queue 相关约 200 行
3. 检查 `agent.py`：移除不需要的字段
4. 更新单元测试：覆盖精简后的接口
5. 运行 `uv run pytest tests/ -v` 确认通过