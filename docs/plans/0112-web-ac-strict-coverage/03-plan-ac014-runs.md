---
title: AC-014 Runs 主从工作台覆盖补齐
description: 为 AC-014 的 14 个 planned 场景编写真实测试节点，必要时补产品行为
type: plan
status: pending
created: 2026-07-30T00:00:00Z
---

# Context

AC-014 planned：N-1（4 状态列表+默认选中最新）、N-2（failed 筛选下原地切换）、N-4（启动 Run → 201/Location/左栏出现）、N-7（Rerun → 新 run_id、原 Run 不变）、N-8（Loop 筛选+文本搜索）、N-10（loop.md args 预填，与 AC-035-N-1 同源）、N-11（/system/meta 版本与 rail 显示）、B-2（空目录空状态）、B-5（loop.md 无 args 时忽略 legacy meta.args）、B-6（working_directory basename 次要标识行+hover 完整路径）、B-7（reconcile 409 run_in_grace）、E-1（非法 run.json → unreadable 摘要不 500）、E-2（stale 检测：原子记录 stale_since、Stop 禁用显示 Reconcile）、F-2（reconcile 超 24h → failed 原子替换清 pid）。已登记：N-9/B-1/B-3/B-4；N-3/N-5/N-6/F-1 已 superseded（AC-020~022 替代）。分支 `feat/0112-ac014-runs`。

# Request

1. 为 14 个场景各写真实测试节点：API 语义（N-4/N-7/B-7/E-1/F-2、N-11 端点、N-10/B-5 的 loops 端点）用 `tests/integration/test_web_api.py`，UI 语义（N-1/N-2/N-8/B-2/B-6/E-2、N-11 rail、N-10/B-5 预填）用 `web/src/App.test.tsx`；B-1 千条列表已登记，此处不动。
2. TDD 先红后绿；产品行为不符冻结契约时补最小实现（注意 N-10/B-5 与 AC-035 已实现逻辑同源，先复用）。
3. `TEST_NODES` 仅追加 AC-014 段，重新生成 `cases.json`。
4. 验证 strict 下 AC-014 段 0 planned，其余段计数不变（57→43 的变化只来自前两单元合并后的基线，本单元自身消 14）。

# Constraints

- 不改契约文档；契约存疑停下来上报。
- F-2 必须断言 run.json 原子替换（不残留中间态）且 pid/process_started_at/stale_since 已清除。
- E-1 必须断言请求不返回 500 且合法 Run 正常返回。
- N-7 必须断言原 Run A 文件不变。
- 只追加 `TEST_NODES` 本段条目；文档与代码分开提交；commit 标注 AC 编号。

# Checkpoint

- [ ] 14 个测试节点有实质断言
- [ ] MR 门禁通过
- [ ] strict 检查 AC-014 段清零
- [ ] Report 留档，可反向定位
