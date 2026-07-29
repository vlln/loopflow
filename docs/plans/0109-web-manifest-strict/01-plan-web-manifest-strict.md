---
title: Web manifest strict 基建修复
description: 修复 Web AC manifest 无条件生成 planned 节点导致 strict SYSTEM_TEST 不可通过的基础设施缺陷
type: plan
status: done
created: 2026-07-29T00:00:00Z
---

# Context

0108 SYSTEM_TEST 的集成层 99 项、CLI E2E 22 项和 recovery、scheduling、agent、singleagent、iteration027 五个 strict profile 已通过。全局 Web profile 对 86 个 AC 场景无条件生成 `planned::`，即使真实测试已经存在也无法通过 strict，分类为测试基础设施缺陷并回退 TEST_INFRA。

# Request

1. 为 AC-014~019 全部非 superseded 场景建立可审计的真实测试节点映射。
2. 让生成器使用映射节点，并让 strict checker 验证文件及测试 selector 真实存在。
3. 添加正反向基建测试，证明 strict 接受完整真实映射并拒绝 planned、漂移映射和伪造节点。
4. 重新生成提交的 Web manifest，完成增量 TEST_INFRA 自证和独立 subagent 审查。

# Constraints

- 不修改 active Spec/AC/Interface、accepted ADR 或产品实现。
- 不以 `--allow-planned` 放宽 SYSTEM_TEST strict 语义。
- 保留 superseded AC ID 的兼容处理；非 superseded 场景必须全部映射。
- 仅重跑本次修复相关的基础设施门禁；SYSTEM_TEST 恢复后从失败的 manifest 层继续。
- 文档与测试基建代码分开提交。

# Checkpoint

- [ ] AC-014~019 非 superseded 场景均映射真实测试节点（54 个场景因设计漂移或覆盖不足未完成）
- [x] generator 与提交 manifest 一致
- [x] strict checker 拒绝 planned、漂移映射和不存在节点
- [ ] 增量基础设施测试与 Web strict profile 通过（infra 81/81；strict 正确拒绝 54 planned）
- [x] subagent 审查通过，Report 记录分类与证据
