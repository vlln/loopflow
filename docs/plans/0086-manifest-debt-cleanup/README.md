# 0086 manifest strict 欠账清理

对应阶段：`SYSTEM_TEST`（SYSTEM_TEST→TEST_INFRA 基建欠账修复，BL-010 / BL-007 尾巴）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [manifest strict 欠账清理](01-plan-manifest-debt-cleanup.md) | [Report](01-report-manifest-debt-cleanup.md) | in_progress |

## 范围

- AC-010-N-2/E-2 契约漂移裁决落地（BL-010，用户已裁决：改 AC 文本对齐 ADR-0031 现行实现），scheduling manifest 登记真实测试节点
- web profile 6 个历史 planned 场景补真实测试：AC-015-F-3、AC-015-N-7、AC-015-N-8、AC-016-B-3、AC-016-F-3、AC-019-B-3；其中 AC 文本与实现漂移的按实证修正 AC 文本（同 BL-010 裁决方式），不强行实现或改行为
- 三个 profile（web / recovery / scheduling）manifest strict 全绿（不允许 --allow-planned）

## 非范围

- 任何实现行为变更（漂移一律修 AC 文本，不改代码行为）
- AC-016-F-3 暴露的 SSE file_changes OSError 未按 topic 隔离问题（记录进 Report，留后续裁决）
- uv.lock 既有未提交修改（与本任务无关，不触碰、不提交）
