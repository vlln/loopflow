---
title: Transport Strategy + Observability
description: 禁用 ACP auto-detection，{seq}.jsonl 实时写入，backend_name → backend 统一命名
type: plan
status: done
created: 2026-07-11T13:00:00Z
---

# Plan 0018: Transport Strategy + Observability

## 关联文档

- ADR: [0018-transport-strategy](../adr/0018-transport-strategy.md)
- Spec: [0001-loopflow](../spec/0001-loopflow.md) v6 → v7

## 步骤

### 01 — 禁用 ACP auto-detection

**文件：** `src/loopflow/backends/{kimi,opencode,qwen,gemini,kiro}.py`

每个后端修改 1 行：

```python
# 之前
use_acp = transport == "acp" or (transport is None and check_acp(...))

# 之后
use_acp = transport == "acp"
```

移除未使用的 `from loopflow.backends.utils import check_acp` 导入。

**验证：** 现有测试全部通过（kimi 后端测试应走 CLI 路径）。

### 02 — `{seq}.jsonl` 实时写入

**文件：** `src/loopflow/runtime.py`

当前 `text_handler` 只写 `events.jsonl` + stderr。改为同步 append 到 `{seq}.jsonl`：

```python
def text_handler(text: str) -> None:
    if text:
        output_parts.append(text)
        event = {"type": "agent_text", "session": session, "content": text}
        _write_event(event)                          # events.jsonl
        _append_cache(cache_path, event)             # {seq}.jsonl ← 新增
        print(f"[agent] {text}", file=sys.stderr, flush=True)
```

`_write_cache` 改为只追加 `agent_done`（不再重复写 `agent_text`）。

Resume 逻辑无需修改——`try_resume` 检查 `agent_done` + `exit_code=0`，仅含 `agent_text` 的文件不会被误判。

**验证：** 单元测试验证 `{seq}.jsonl` 在 agent 执行期间存在且包含 `agent_text`，完成后包含 `agent_done`。

### 03 — `backend_name` → `backend` 统一命名

**文件：** `src/loopflow/runtime.py`

- `_make_backend(backend_name=...)` → `_make_backend(backend=...)`
- `_run_subagent(backend_name=...)` → `_run_subagent(backend=...)`
- 所有内部引用同步更新

**验证：** 现有测试通过，无功能性变更。

## 约束

- 不删除 ACP 代码（`AcpBackend`、`AcpTransport`、`check_acp` 保留）
- 不修改 `tests/` 目录下的测试（除非测试因新行为而失败）
- 不修改 `events.jsonl` 的格式

## 检查点

- [ ] 5 个后端 ACP auto-detection 已禁用
- [ ] `{seq}.jsonl` 实时写入，执行中可见
- [ ] Resume 不误判进行中的 agent 调用
- [ ] `backend_name` → `backend` 全部重命名
- [ ] 全部测试通过