---
title: Workflow State Persistence
description: meta.state 声明式工作流状态变量，自动持久化到 state.json，resume 恢复
type: adr
status: accepted
created: 2026-07-09T12:00:00Z
---

# ADR 0012: Workflow State Persistence

## Context

bio-reproducer 的 `attempt` 计数器在 resume 后归零——workflow 脚本的 Python 变量不持久。workflow 作者被迫手动写文件：

```python
attempt_file = f"{out}/.retry_count"
attempt = int(Path(attempt_file).read_text()) if Path(attempt_file).exists() else 0
```

Claude Code workflow 有 `STATE.md`（agent 维护的 Markdown 记忆），但 loopflow 需要的是 **workflow 脚本的变量持久化**——程序化的、run 级别的、resume 自动恢复的。

## Decision

### 声明式 state，自动持久化

```python
# meta 中声明
meta = {
    "name": "bio-reproducer",
    "state": {
        "attempt": 0,        # 默认值，类型推断
    },
}

# run() 中读写
def run(agent, ..., state):
    while state.attempt < phase_retries:
        ...
        state.attempt += 1   # 每次 agent() 调用后自动持久化
```

### 行为规则

| 规则 | 说明 |
|------|------|
| 声明 | `meta.state` 声明所有持久化变量及其默认值 |
| 读写 | `state.key` 属性访问，直接赋值 |
| 持久化时机 | 每次 `agent()` 成功返回后自动写入 `runs/<id>/state.json` |
| 格式 | `state.json` 是 JSON 对象，key 和 `meta.state` 一致 |
| 类型 | 仅支持 JSON 可序列化的值（str, int, float, bool, list, dict, None） |
| Resume | 加载 `state.json`，缺失的 key 用 `meta.state` 默认值填充 |
| 初始化 | 首次运行时，`state` 以 `meta.state` 默认值初始化 |

### 与 resume 的协作

```
首次运行:
  meta.state → state.json（初始值）
  agent() 成功 → state.json 更新
  agent() 成功 → state.json 更新
  ↓ 崩溃

resume:
  state.json 加载（保留已更新的值）
  agent() 缓存命中 → 跳过，state 不变
  agent() 未完成 → 重新执行，state 继续更新
```

### 边界

- **不做** 自动类型校验——默认值类型即约定类型，运行时赋值不检查
- **不做** 嵌套属性的深层合并——`state.dict_key["nested"]` 的修改需要整体赋值
- **不做** 跨 run 共享——state 是 run 级别的，不同 run 实例独立
- **不做** agent 内访问——state 是 workflow 层的概念，agent 不可见

## Consequences

### 正面

- Workflow 作者不需要手动写文件——声明即持久化
- Resume 语义完整——状态变量和 agent 缓存一起恢复
- 与 `meta.phases` 同模式——声明式，开发者体验一致

### 代价

- `state` 成为 `run()` 的第 8 个参数
- 每次 `agent()` 调用后多一次文件写入（通常可忽略）
- 并行 agent 调用同时写 state 时，last-write-wins（workflow 作者应避免并行修改同一 key）