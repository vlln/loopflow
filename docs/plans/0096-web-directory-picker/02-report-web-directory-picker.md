---
title: Report — Web 端跨平台目录选择器
description: BL-009 执行结果：GET /system/list-directory 端点 + 前端模态目录浏览器，替代 macOS-only osascript
type: report
status: complete
created: 2026-07-27T08:15:00Z
---

# Report: Web 端跨平台目录选择器

## AC 验收结果

| 编号 | 结果 | 说明 |
|------|------|------|
| AC-025-N-8 | PASS | `GET /system/list-directory` 返回子目录列表；前端模态浏览器导航 + Select 填充 working directory |
| AC-025-B-7（修改） | PASS | 非 macOS 平台 `GET /system/list-directory` 正常返回 200；Browse 按钮始终可用 |
| AC-025-B-10 | PASS | 不存在路径 → 404 `file_not_found` |
| AC-025-B-11 | PASS | 文件非目录 → 422 `validation_failed` |
| AC-025-N-6 | PASS | 旧 `POST /system/pick-directory` 端点行为不变（向后兼容） |
| AC-025-B-6 | PASS | 旧端点取消行为不变 |

## 实现摘要

### 后端
- `web.py` `list_directory(path)` — `os.scandir` 列子目录，校验绝对路径 + 已存在 + 是目录
- `server.py` — `GET /api/v1/system/list-directory?path=...` 路由

### 前端
- `api.ts` — `listDirectory(path)` 方法
- `types.ts` — `DirectoryEntry` / `DirectoryListing` 类型
- `App.tsx` — `DirectoryPickerModal` 组件（导航 + 路径输入 + Select/Cancel）；`NewRunDialog` 移除 `browseSupported`，Browse 按钮始终显示
- `styles.css` — 目录浏览器样式

### 旧端点
`POST /system/pick-directory` 保留不动（向后兼容），前端不再调用。

## 测试

- 单元测试：7 个（`test_web_application.py`）— 全部 PASS
- 集成测试：1 个（`test_web_api.py`）— PASS
- 全量回归：85 passed, 0 failed

## 产物

| Commit | 说明 |
|--------|------|
| `b85ef74` | docs(design): ADR-0053, AC-025, 接口定义, 执行容器 0096 |
| `cc5abe5` | feat(web): GET /system/list-directory 端点 |
| `c5a3db9` | feat(webui): 前端模态目录浏览器 |
| `a271a3c` | test(web): 单元 + 集成测试 |
