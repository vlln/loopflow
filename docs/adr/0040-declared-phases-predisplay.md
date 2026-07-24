---
title: ADR 0040 — Declared Phases 预显示与合并语义
description: 利用 meta.phases 声明在 Run 启动时预显示占位 phase 节点，运行时按 events 合并为实际执行图；无声明时退化为运行时涌现
type: adr
status: proposed
created: 2026-07-23T12:00:00Z
---

# ADR 0040: Declared Phases 预显示与合并语义

## Context

ADR-0009 定义了 PhaseGraph 从 `events.jsonl` 运行时涌现的执行图——phase 拓扑在 `phase()` 调用时逐步构建。这导致 Run 启动时 WebUI 和终端的 phase 图为空白，用户无法预知 workflow 将经过哪些阶段。

Spec 0001（第 161-163 行）和 ADR-0031 已经定义了 `meta.phases` 声明：

> `phases` 声明预期阶段，运行时 `phase()` 调用锚定到声明上。`meta` 必须是纯字面量（无变量、函数调用、表达式），用于静态发现和进度显示。

但实现存在缺口：`src/loopflow/infrastructure/discovery.py` 的 `load_loop()` 只读 `loop.md` frontmatter，未提取 `workflow.py` 模块的 `meta.phases`；WebUI 的 phase graph 只从 runtime events 构建，未使用 declared phases 做预显示。

需要冻结 declared phases 与 runtime events 的合并语义，使 Run 启动时即可展示预期 phase 占位节点，运行时逐步替换为实际执行状态。

## Decision

### 1. Declared phases 提取

`discovery.py` 的 `load_loop()` 在加载 `workflow.py` 模块后，提取 `mod.meta.get("phases")` 并并入返回的 meta 字典。提取规则：

- `meta.phases` 是 object[]，每个 object 含 `title`（required）和 `detail`（optional）
- `meta` 必须是纯字面量（BR-007 已约束），无需 AST 解析或动态执行
- `loop.md` frontmatter 不含 `phases`（ADR-0031 已明确：loop.md 是调度层元数据权威源，workflow.py 的 meta 只保留 phases）
- 若 `workflow.py` 无 `meta` 或 `meta` 无 `phases` 键，declared phases 为空列表

### 2. 预显示合并语义

Phase graph 的构建分为两层：

**Layer 1: Declared phases（静态层）**

Run 创建时（`loopflow run` 或 WebUI 启动 Run），从 Loop 的 declared phases 生成占位节点：

- 每个 declared phase 成为一个占位节点，状态为 `pending`
- 占位节点有 title 和 detail，无 phase_id、无 occurrence、无边
- 占位节点按声明顺序排列
- 占位节点不参与环检测、不计入 iteration_count

**Layer 2: Runtime events（动态层）**

运行时 `phase()` 调用产生 phase 事件后，按 ADR-0009 的 PhaseGraph 逻辑构建实际执行图。合并规则：

| 情况 | 合并行为 |
|------|---------|
| runtime phase title 匹配 declared phase | 占位节点替换为实际节点，继承 declared 的 detail；状态从 pending → active/done |
| runtime phase title 不在 declared 中 | 新增实际节点（undeclared phase），标记为 `undeclared`，无 detail |
| declared phase 无对应 runtime event | 保持占位状态（pending），Run 结束后仍显示为未执行 |

**关键约束：**

- 合并基于 **title 匹配**，不基于位置或顺序。declared phases 的顺序只影响占位节点的初始排列，runtime events 的顺序决定实际边的绘制。
- 同名 phase 的多次 occurrence（循环）按 ADR-0034 的 `phase_id` 区分，聚合到同一节点。占位节点被第一次 occurrence 替换后，后续 occurrence 增加计数。
- undeclared phases 出现在 declared phases 之后（视觉上），不插入到声明顺序中间。

### 3. 降级：无 declared phases

当 `meta.phases` 为空或不存在时，PhaseGraph 完全退化为 ADR-0009 的运行时涌现模式——从空白开始，按 events 逐步构建。这是现有行为，不改变。

### 4. Run 读模型

application service 的 Run 读模型新增 `declared_phases` 字段：

```json
{
  "declared_phases": [
    {"title": "采集", "detail": "从数据源拉取原始数据"},
    {"title": "处理", "detail": "清洗和转换数据"},
    {"title": "判断", "detail": "评估处理结果是否达标"}
  ]
}
```

WebUI 和终端渲染器消费此字段生成占位节点，再与 runtime PhaseGraph 合并。

### 5. 终端渲染

终端 PhaseGraph 渲染器（`display/graph_renderer.py`）在 Run 启动时若收到 declared phases，先渲染占位节点序列：

```
○ 采集 → ○ 处理 → ○ 判断
```

`○` 表示 pending（占位），`●` 表示 active/done。运行时按 events 逐步将 `○` 替换为 `●`，并画边、标注循环轮次。

### 6. WebUI 渲染

WebUI 的 phase graph（`@xyflow/react`）在 Run 创建后立即用 declared phases 渲染占位节点。SSE 事件到达后，按合并语义更新节点状态和边。

占位节点和实际节点的视觉区分：

| 节点状态 | 视觉 |
|---------|------|
| pending（declared，未执行） | 低对比度、虚线边框 |
| active（当前执行中） | 高亮 |
| done（已完成） | 正常对比度、✓ 标记 |
| undeclared（运行时新增） | 标记 badge "undeclared" |

## Alternatives

### 方案 A：AST 静态扫描 phase() 调用（拒绝）

- 优点：不需要 workflow 作者声明，自动发现。
- 缺点：动态 title（f-string、变量）无法捕获；无法获得 detail；拓扑（谁连谁）仍不可知。`meta.phases` 声明已提供更好的静态信息，无需 AST 解析。

### 方案 B：声明式 phase 拓扑，启动即完整图（拒绝）

- 优点：启动即显示完整拓扑，包括边和循环。
- 缺点：推翻 ADR-0009 的核心决策——命令式 Python 的灵活性来自运行时决定控制流。声明式拓扑与 Python 原生控制流冲突，限制 workflow 表达力。

### 方案 C：不预显示，保持运行时涌现（拒绝）

- 优点：实现最简单，不改变现有行为。
- 缺点：Spec 0001 和 ADR-0031 已定义 `meta.phases` 用于"静态发现和进度显示"，但实现未跟进。用户体验差——启动时空白，无法预知 workflow 结构。

## Consequences

### 正面

- Run 启动时即可看到预期 phase 结构，改善用户体验。
- 利用已有 `meta.phases` 契约，不改变 workflow 作者的声明方式。
- 降级机制保证无声明 workflow 不受影响。
- 合并语义清晰，title 匹配规则简单可测。

### 负面

- declared phases 与 runtime events 不匹配时（声明了但没执行、执行了但没声明）需要明确的视觉表达，增加 UI 复杂度。
- discovery.py 需要额外提取 `mod.meta.phases`，增加加载步骤。
- 占位节点和实际节点的状态管理增加 PhaseGraph 渲染器复杂度。

### 不做的

- 不从 AST 推断 phase 拓扑。
- 不要求 workflow 必须声明 phases（保持 optional）。
- 不用声明式拓扑替代命令式 Python 控制流。
- 不在 declared phases 中表达边或循环结构（只声明节点集合，不声明拓扑）。

## Architecture Boundary

本 ADR 约束 discovery.py 的 meta.phases 提取、application service 的 Run 读模型、以及终端/WebUI 渲染器的占位节点与合并逻辑。

- discovery.py 提取 `mod.meta.phases` 并并入返回 meta；
- application service 在 Run 读模型中暴露 `declared_phases`；
- 终端渲染器和 WebUI 消费 declared phases 生成占位节点，按 title 匹配合并 runtime events；
- 渲染器不自行推断 phase 拓扑，不从 AST 或文本扫描提取 phase。

## Verification

不需要外部技术选型 spike。在 TEST_INFRA/DEVELOP 阶段通过以下测试验证：

| 验证项 | 复现步骤 | 预期结论 |
|--------|---------|---------|
| meta.phases 提取 | workflow.py 含 meta.phases 声明 | discovery.load_loop() 返回的 meta 含 phases 列表 |
| 启动时占位节点 | WebUI 启动有 declared phases 的 Run | phase graph 立即显示占位节点，不等 events |
| title 匹配合并 | declared ["采集","处理","判断"], runtime events 采集→处理 | 采集、处理替换为实际节点，判断保持 pending |
| undeclared phase | declared ["采集","处理"], runtime 出现 "归档" | 归档作为 undeclared 节点出现，标记 badge |
| 无声明降级 | workflow.py 无 meta.phases | phase graph 从空白开始，按 events 涌现（现有行为不变） |
| 循环合并 | declared ["采集","处理","判断"], runtime 采集→处理→判断→采集 | 采集节点 occurrence=2，回边判断→采集 |
| 声明未执行 | declared ["采集","处理","归档"], runtime 只到处理就 done | 归档保持 pending，Run 结束后仍显示 |
