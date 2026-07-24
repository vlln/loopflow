---
title: loopflow AC-0009 — Phase 执行图可视化
description: 终端渲染 phase 执行图：线性路径、回边（循环）、条件分支三种布局，Rich Live 增量更新，不闪屏
type: ac
status: active
created: 2026-07-08T10:00:00Z
---

# AC-009: Phase 执行图可视化

验证 phase 转移图的数据结构和终端渲染。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-N-1 | workflow.py 中线性调用 phase("A") → phase("B") → phase("C") → phase("D")，无循环无分支 | 执行 `loopflow run <name>` | 终端渲染为 `● A ──→ ● B ──→ ● C ──→ ● D ✓`，直线连接，已完成节点标记 ✓ | 自动化 |
| AC-009-N-2 | workflow.py 中 while 循环：phase("A") → phase("B") → phase("C")，C 中判断后 continue 回 A，共 3 轮 | 执行 `loopflow run <name>` | 终端渲染显示回边 C→A（虚线/曲线），标注"第2轮""第3轮"，3 轮后正常结束 | 自动化 |
| AC-009-N-3 | workflow.py 中 if/else 分支：phase("A") → phase("B")（条件走 B1）或 phase("A") → phase("C")（条件走 C1） | 执行 `loopflow run <name>` | 终端渲染显示分叉 `┌─→ B` `└─→ C`，实际走的路径高亮，未走的路径不显示或灰显 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-B-1 | workflow.py 中只有 1 个 phase | 执行 `loopflow run <name>` | 渲染单个节点 `● A ✓`，无边，不报错 | 自动化 |
| AC-009-B-2 | workflow.py 不调用 phase() | 执行 `loopflow run <name>` | 不渲染图，不报错，不显示空图 | 自动化 |
| AC-009-B-3 | workflow.py 中 phase 名称重复（如两次 phase("A")） | 执行 `loopflow run <name>` | 不创建新节点，复用已有节点 A，边计数增加 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-E-1 | events.jsonl 损坏（phase 事件缺少 title 字段） | 执行 `loopflow status <run-id>` | 跳过损坏行，正常渲染其余 phase，stderr 提示解析警告 | 自动化 |
| AC-009-E-2 | events.jsonl 中 phase 事件顺序错乱（ts 不递增） | 执行 `loopflow status <run-id>` | 按事件出现顺序渲染，不依赖 ts 排序 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-F-1 | events.jsonl 不存在（run 刚创建，还没有任何 agent 调用） | 执行 `loopflow status <run-id>` | 显示"无执行记录"或空状态，不崩溃 | 自动化 |
| AC-009-F-2 | 终端宽度 < 40 列 | 执行 `loopflow run <name>`，phase 图很宽 | 渲染器自动截断或换行，不 panic，不输出乱码 | 自动化 |

---

## 模块级验收

以下不依赖运行时，纯单元测试验证。

| 编号 | 测试目标 | 预期结果 | 验证方式 |
|------|---------|---------|---------|
| AC-009-U-1 | PhaseGraph.record("A", "B") 后 edges() | 返回 1 条边，count=1，is_backedge=False | 自动化 |
| AC-009-U-2 | PhaseGraph 连续 record("A","B") → record("B","C") → record("C","A") | 第三条边 is_backedge=True，has_cycle()=True，cycle_nodes()=["A","B","C"] | 自动化 |
| AC-009-U-3 | PhaseGraph.record("A","B") 两次 | edges() 返回 1 条边，count=2 | 自动化 |
| AC-009-U-4 | TerminalGraphRenderer 渲染线性路径 | 输出包含 "A" "B" "C" "D" 和连接字符 "──" | 自动化 |
| AC-009-U-5 | TerminalGraphRenderer 渲染回边 | 输出包含 "↑" 或 "└" 字符和轮次标签 | 自动化 |
| AC-009-U-6 | PhaseGraph 不 import rich | `import graph; "rich" not in sys.modules` | 自动化 |

---

## Declared Phases 预显示（BR-042）

> 2026-07-23 追加。验证 `meta.phases` 声明在终端渲染中的预显示和合并语义，详见 [ADR-0040](../adr/0040-declared-phases-predisplay.md)。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-N-4 | workflow.py 含 `meta.phases = [{"title":"采集"},{"title":"处理"},{"title":"判断"}]` | 执行 `loopflow run <name>`，Run 启动后立即观察终端 | 终端显示占位节点序列 `○ 采集 → ○ 处理 → ○ 判断`，无需等待 phase() 调用 | 自动化 |
| AC-009-N-5 | 同 AC-009-N-4，workflow 运行时调用 phase("采集") → phase("处理") | 观察终端渲染 | 采集、处理占位节点替换为实际节点（`●`），判断保持占位（`○`）；边按实际执行顺序绘制 | 自动化 |
| AC-009-N-6 | workflow.py 含 `meta.phases = [{"title":"采集"},{"title":"处理"}]`，运行时调用 phase("采集") → phase("归档") | 观察终端渲染 | 采集替换为实际节点；归档作为 undeclared 节点出现，标记为未声明；处理保持占位 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-B-4 | workflow.py 无 `meta.phases` 声明 | 执行 `loopflow run <name>` | 终端不预显示占位节点，从空白开始按 events 涌现（现有行为不变） | 自动化 |
| AC-009-B-5 | workflow.py 含 `meta.phases = [{"title":"采集"},{"title":"归档"}]`，运行时只调用 phase("采集") 后 Run done | 观察终端最终渲染 | 采集为实际节点（`● ✓`），归档保持占位（`○`），不报错 | 自动化 |
| AC-009-B-6 | workflow.py 含 `meta.phases` 声明，运行时同名 phase 循环 3 轮 | 观察终端渲染 | 占位节点被首次 occurrence 替换后，后续 occurrence 增加计数并画回边，与 ADR-0009 回边渲染一致 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-E-3 | workflow.py 含 `meta.phases = [{"title":""}]`（title 为空字符串） | 执行 `loopflow run <name>` | 跳过无效声明，不渲染该占位节点，stderr 提示解析警告，其余有效声明正常预显示 | 自动化 |
| AC-009-E-4 | workflow.py 含 `meta.phases = [{"detail":"无标题"}]`（缺 title） | 执行 `loopflow run <name>` | 跳过无效声明，不报错，不崩溃 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-009-F-3 | workflow.py 语法错误，无法加载模块 | 执行 `loopflow run <name>` | 报错退出，不渲染任何占位节点 | 自动化 |
