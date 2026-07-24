# 0078 New Run 对话框 UX（目录选择器 + Arguments 编辑器）

对应阶段：`DEVELOP`（RELEASE 验收修复）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [New Run 对话框 UX](01-plan-new-run-dialog-ux.md) | [Report](01-report-new-run-dialog-ux.md) | done |

## 范围

- 目录选择：`POST /api/v1/system/pick-directory` 调起 OS 原生目录选择器（macOS osascript；其他平台 501 回退手动输入）；对话框加 Browse 按钮
- Arguments：键值对编辑器（值智能类型解析）+ JSON 高级模式切换
- 契约补充：interface 端点、AC-0013/AC-0010 场景追加
- 来源：0.20.0 RELEASE 人工验收意见，修复后重新拉 release/0.20.0

## 非范围

- 不做 loop args schema 声明机制（未来迭代）
- 非 macOS 的原生选择器实现（仅 501 回退）
