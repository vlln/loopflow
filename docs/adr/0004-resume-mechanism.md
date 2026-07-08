---
title: ADR-0004
description: 崩溃恢复机制：序号计数器重放 vs 显式状态检查点
type: adr
status: proposed
created: 2026-07-07T12:00:00Z
---

# ADR-0004: Resume 恢复机制

---

## 背景

loopflow 的核心特性之一是崩溃恢复——workflow.py 执行中断后，resume 时已完成的工作不丢失。需要决定恢复机制的实现方式。

---

## 决策内容

使用 **序号计数器重放**。每个 `agent()` 调用分配递增序号，输出缓存到 `<seq>.jsonl`。Resume 时重新执行 workflow.py，已完成的 agent 调用从缓存返回，未完成的继续执行。**不引入显式状态检查点**。

---

## 备选方案

### 方案 A: 序号计数器重放（推荐）

工作方式：workflow.py 从头重跑，`agent()` 内部检查 `<seq>.jsonl` 是否存在且 exit_code=0 → 命中则返回缓存，否则真正执行。

- 优点：workflow 作者零心智负担，不需要写任何 resume 逻辑；机制简单，<50 行代码；与 Claude Code Workflow 的 resume 机制一致
- 缺点：依赖脚本确定性（同一个 workflow.py + 同一个 args → 同一 agent 调用序列）；如果脚本中有 `random` 或 `time` 等非确定性调用，可能导致缓存未命中

### 方案 B: 显式状态检查点

工作方式：workflow 作者在关键位置手动调用 `checkpoint()` 保存状态，resume 时从最近的检查点恢复。

- 优点：可以跳过已执行的非 agent 代码（如计算密集型操作）；支持非确定性脚本
- 缺点：workflow 作者需要显式管理检查点，增加心智负担；检查点数据需要序列化/反序列化；比方案 A 复杂一个数量级

### 方案 C: 外部状态机

工作方式：框架维护一个显式的状态机（DAG 节点 + 转换），resume 时从状态机恢复。

- 优点：可精确控制恢复粒度
- 缺点：与 loopflow 的循环模型冲突——while 循环的状态空间是无限的，无法预定义所有状态；实现复杂度极高

---

## 选择理由

1. loopflow 的 workflow.py 本质上是确定性的——唯一的外部输入是 `args` 和 `agent()` 返回值，后者由缓存保证确定性
2. 方案 A 已被 Claude Code Workflow 和 subagent-skills 验证可行
3. 方案 B/C 的复杂度与 loopflow 的简化目标（零外部依赖，约 2000 行）冲突
4. workflow.py 作者不需要关心 resume——这正是 loopflow 的核心卖点

---

## 验证

| 验证项 | 复现步骤 | 结论 | 经验 | 验证 Branch |
|--------|---------|------|------|------------|
| 序号重放正确性 | 编写 workflow.py 调用 3 个 agent，模拟在第 2 个崩溃（删除第 2 个 jsonl），resume | 可行 | 第 1 个从缓存返回，第 2、3 真正执行，结果和完整运行一致 | spike/0004-resume |
| while 循环 resume | 编写 while 循环调用 5 次 agent，模拟在第 3 次崩溃 | 可行 | 前 3 次缓存命中，后 2 次执行，循环正确退出 | spike/0004-resume |
| parallel 内部 resume | parallel 中 3 个 agent，1 个已完成 2 个未完成，resume | 可行 | 已完成的返回缓存，未完成的执行，parallel 等全部完成后返回 | spike/0004-resume |

---

## 后果

### 正面

- workflow 作者零负担——resume 对 workflow.py 完全透明
- 实现简单，约 50 行代码
- 与 Claude Code / subagent-skills 生态一致

### 负面

- 依赖脚本确定性。如果 workflow.py 中使用了 `random` 或 `time.time()` 等非确定性操作，resume 时缓存可能未命中
- 崩溃在非 agent 调用处（如 Python 异常）时，重跑会重新执行该段 Python 代码（但 agent 调用仍由缓存保护）

---

## 约束范围

`src/loopflow/runtime.py`（agent 调用逻辑）、`src/loopflow/registry.py`（缓存管理）。约束了 resume 的机制和实现方式。

---

## 约束规则

| 规则编号 | 规则 | 适用范围 | 违反时如何检出 |
|----------|------|---------|--------------|
| AR-001 | agent 调用序号从 1 开始严格递增，不可跳跃 | runtime.py | 单元测试检查序号连续性 |
| AR-002 | 缓存 jsonl 文件命名为 `<seq>.jsonl`，4 位零填充 | registry.py | 单元测试 |
| AR-003 | 缓存命中判据：jsonl 文件存在且 agent_done 事件 exit_code=0 | runtime.py | 单元测试 |
| AR-004 | 损坏的缓存文件视为未完成，重新执行并覆盖 | runtime.py | 单元测试 |