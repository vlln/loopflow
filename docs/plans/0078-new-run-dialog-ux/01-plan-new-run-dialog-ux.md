---
title: New Run 对话框 UX Plan
description: 工作目录 OS 原生选择器（pick-directory 端点 + Browse 按钮）与 Arguments 键值编辑器
type: plan
status: done
created: 2026-07-24T06:30:00Z
---

# Goal

修复 0.20.0 RELEASE 人工验收的两条 UX 意见：工作目录不再手动输入（OS 原生目录选择器），Arguments 不再手写 JSON（键值编辑器 + JSON 高级模式）。

# Constraints

- 浏览器拿不到服务器侧绝对路径 → 选择器必须由后端在本机调起（macOS `osascript choose folder`）；非 macOS 返回 501 `not_supported`，前端隐藏 Browse 按钮回退手动输入
- 手动输入能力保留（选择器是增强不是替代）
- Arguments 键值编辑器：值为空行忽略；值智能解析（JSON.parse 成功则用解析结果，否则按字符串）；重复 key 后者覆盖；JSON 高级模式保留原有校验
- 后端零外部依赖；osascript 调用需处理用户取消（exit -128 → `{path: null, cancelled: true}`）

# Steps

1. 契约：interface 增加 `POST /system/pick-directory`；AC-0013 追加选择器场景；AC-0010 追加 Arguments 编辑器场景
2. 后端：`application/web.py` `pick_directory()`（平台判定 + subprocess 调 osascript + 取消/失败处理）+ `server.py` 路由
3. 前端：`api.pickDirectory()`；NewRunDialog 加 Browse 按钮（501 时隐藏）；Arguments 键值编辑器组件 + JSON 切换
4. 测试：后端端点（mock subprocess：成功/取消/非 macOS 501）；前端（Browse 填充、键值提交 body、JSON 切换、留空不带字段）
5. 全量验证：pytest、vitest/typecheck/build/e2e、静态资源同步

# Acceptance

- AC-025-N-6（选择器返回路径并填充）、AC-025-B-6（取消不改变输入）、AC-025-B-7（非 macOS 501 回退）
- AC-010 Arguments 编辑器新增场景
- AC-025-N-3（对话框带/不带 working_directory 字段）不回归
- 既有 Python 401 + 前端 24 测试全部回归通过

# Checkpoint

- 后端端点完成后前端再联调 Browse 按钮
- 合入前全量测试通过

# Exit

全部 Acceptance 通过，写 Report，合并 develop，重新拉 release/0.20.0。
