---
title: Plan — Web 端跨平台目录选择器
description: 实现 GET /system/list-directory 端点 + 前端模态目录浏览器，替代 macOS-only osascript（BL-009）
type: plan
status: pending
created: 2026-07-27T07:50:00Z
---

# Plan: Web 端跨平台目录选择器

## 目标

修复远程服务器部署时 Browse 按钮失效问题（BL-009）。

## 步骤

1. **后端**：`web.py` 添加 `list_directory(path)` 方法（`os.scandir` 列子目录，校验绝对路径+已存在+是目录）；`server.py` 添加 `GET /system/list-directory` 路由
2. **前端**：`api.ts` 添加 `listDirectory`；`types.ts` 添加 `DirectoryListing`；`App.tsx` 新增 `DirectoryPickerModal` 组件替换 `browse()` 中的 `pickDirectory` 调用，移除 `browseSupported` 条件
3. **样式**：`styles.css` 添加目录浏览器样式
4. **测试**：`test_web_application.py` 单元测试 + `test_web_api.py` 集成测试
5. **构建**：`npm run build` 重建前端静态资源

## AC 覆盖

- AC-025-N-8（正常）：Browse → 模态框 → 导航 → Select → 填充路径
- AC-025-B-7（修改）：非 macOS 平台 → `list-directory` 正常返回，Browse 按钮始终可用
- AC-025-B-10（新增）：不存在路径 → 404
- AC-025-B-11（新增）：文件非目录 → 422

## 风险

- 前端构建产物在 `.gitignore` 中（hatchling artifacts），部署时需 `npm run build` 生成 `src/loopflow/presentation/web/static/`
