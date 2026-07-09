---
title: ADR-0009 — PhaseGraph 执行图与终端渲染
description: 运行时 phase 转移图的数据结构（PhaseGraph）与终端渲染（TerminalGraphRenderer），Rich 自绘，无第三方图库依赖，图与渲染解耦
type: adr
status: accepted
created: 2026-07-08T10:00:00Z
---

# 背景

v0.1.0 中 `phase()` 仅打印一行 stderr 文本，不记录 phase 间转移关系，不绘制执行图。v0.2.0 需要将 phase 执行过程可视化：线性路径画直线，回边（循环）画虚线/曲线并标注迭代次数，条件分支画分叉。UI 是被动观察者，不参与控制流。

# 方案

## 一、架构

```
runtime.py (phase event emitter)
       │
       │  events.jsonl     ← 每行一个 {"type":"phase","title":"A","ts":1.23}
       ▼
PhaseGraph (graph.py)       ← 纯数据结构：邻接表、边计数、环检测、快照
       │
       │  graph model
       ▼
TerminalGraphRenderer       ← Rich Live 增量渲染
(display/graph_renderer.py)
```

**模块边界：**

| 模块 | 职责 | 依赖 |
|------|------|------|
| `graph.py` | PhaseGraph 数据结构：记录转移、边计数、环检测、导出序列化 | 无（纯 Python） |
| `display/graph_renderer.py` | 终端渲染：解析 graph model → Rich renderable | graph.py, rich |

## 二、PhaseGraph 数据结构

```python
@dataclass
class Edge:
    from_phase: str
    to_phase: str
    count: int          # 该边被走过的次数
    is_backedge: bool   # 是否为回边（产生环）

class PhaseGraph:
    def __init__(self): ...
    
    # 记录一次 phase 转移
    def record(self, from_phase: str, to_phase: str) -> None: ...
    
    # 查询
    def nodes(self) -> list[str]: ...
    def edges(self) -> list[Edge]: ...
    def current_phase(self) -> str | None: ...
    def iteration_count(self) -> int: ...   # 当前迭代轮次
    
    # 环检测
    def has_cycle(self) -> bool: ...
    def cycle_nodes(self) -> list[str]: ...  # 参与环的节点
    
    # 序列化（用于 CLI 查询）
    def to_dict(self) -> dict: ...
    @classmethod
    def from_events(cls, events: list[dict]) -> "PhaseGraph": ...
```

**环检测规则：** 当 `record(A, B)` 时，如果 B 在当前路径中已出现过（即 B 是 A 的祖先），则 (A, B) 被标记为回边。

## 三、Phase 事件

`phase()` 不再仅打印，同时写入结构化事件到 `events.jsonl`：

```json
{"type": "phase", "title": "采集", "ts": 1.23}
{"type": "phase", "title": "处理", "ts": 2.45}
{"type": "phase", "title": "判断", "ts": 3.67}
{"type": "phase", "title": "采集", "ts": 4.89}  // 回边：判断→采集
```

与现有 `agent_*` 事件共存于 run 目录下。

## 四、终端渲染

```
线性执行:
  ● 采集 ──→ ● 处理 ──→ ● 判断 ──→ ● 归档 ✓

有环（判断 → 采集）:
         第2轮
  ● 采集 ──→ ● 处理 ──→ ● 判断
    ↑                    │
    └──── 第3轮 ─────────┘

条件分支:
               ┌─→ ● 审核 ──→ ● 发布
  ● 采集 ──→ ● ┤
               └─→ ● 跳过
```

**渲染规则：**
- 线性路径：`● A ──→ ● B`，直连
- 回边：用 `↑` `└` `┘` 等 box-drawing 字符画虚线路径，标注轮次
- 分支：用 `┌` `└` `┤` 画分叉
- 当前执行位置：高亮（rich Style）
- 已完成节点：`✓` 标记

**增量更新：** 使用 Rich Live，每次 `phase()` 调用时更新图，不清屏重绘。

## 五、为什么不引入第三方图库

| 候选 | 排除原因 |
|------|---------|
| graphviz | 太重，需要系统安装二进制，不纯 Python |
| networkx | 图算法过剩，只需邻接表 + 环检测 |
| asciigraph | 功能太弱，不满足自定义布局需求 |

Rich 的 `Text`/`Panel`/`Layout`/`Live` 组合即可实现，且 Rich 已是运行时依赖。

## 约束

| 编号 | 描述 |
|------|------|
| AR-001 | PhaseGraph 不依赖任何渲染库，纯数据结构 |
| AR-002 | 渲染器只依赖 PhaseGraph + Rich，不依赖 runtime |
| AR-003 | 环检测基于当前路径，O(n) 时间复杂度 |
| AR-004 | events.jsonl 追加写入，不原地修改 |
| AR-005 | phase 事件与 agent 事件共享同一个 events.jsonl（按时间序） |

## 替代方案

### A. 直接把图逻辑写在 display.py 里

耦合，不可测试，不可换渲染后端。拒绝。

### B. 用 networkx 的 DiGraph

功能过剩，增加依赖，且 networkx 的环检测语义（simple cycle）与需求（基于当前路径的回边）不完全匹配。拒绝。

### C. 声明式 DAG（phase 之间声明确切的跳转规则）

限制太多，失去了 Python 原生控制流的灵活性。v0.2.0 不做，未来可考虑作为可选层。

## 验证

- [ ] PhaseGraph 纯数据结构，不 import rich
- [ ] 线性路径渲染正确（3+ 节点直线）
- [ ] 回边渲染正确（环 + 轮次标签）
- [ ] 分支渲染正确（条件分叉）
- [ ] Rich Live 增量更新不闪屏
- [ ] events.jsonl 中 phase 事件正确记录