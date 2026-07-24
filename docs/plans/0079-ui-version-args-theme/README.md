# 0079 版本同步 / Args 声明预填 / 日夜主题

对应阶段：`DEVELOP`（RELEASE 验收增强）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [版本同步、Args 声明预填、日夜主题](01-plan-ui-version-args-theme.md) | [Report](01-report-ui-version-args-theme.md) | done |

## 范围

- UI 版本号同步：`GET /api/v1/system/meta` 运行时下发版本，rail 显示（替换硬编码 v0.17）
- Args 声明预填：loop frontmatter `meta.args` 声明（name/default/description/required）→ Loop API 返回 `declared_args` → New Run 对话框预填键值行
- 日夜主题：light 调色板 + rail 切换开关 + localStorage 持久化 + 系统偏好默认值
- 来源：0.20.0 RELEASE 人工验收意见，完成后重新拉 release/0.20.0

## 非范围

- args 声明的服务端强制校验（仅预填与提示）
- 主题色全面重设计（light 为既有变量体系的调色板映射）
