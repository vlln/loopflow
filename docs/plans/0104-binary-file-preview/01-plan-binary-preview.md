---
title: BL-051 WebUI 二进制文件预览
description: file changes 面板支持预览 PNG/JPG/GIF/SVG/PDF 等二进制文件，新增 raw 文件端点流式返回
type: plan
status: done
created: 2026-07-29T07:00:00Z
---

# Plan: BL-051 WebUI 二进制文件预览

## 背景

bio-reproducer 远端 run 的 file changes 面板中，PDF 和图片文件点击后显示 `file_not_previewable`。`preview()` 方法拒绝所有含 `\x00` 的二进制文件。用户需要预览 `01_plan/resources/paper.pdf`、`chart.png` 等产物。

## Constraints

- 不引入新依赖（base64 不流式传输大文件；用 raw 端点 + Content-Type 流式返回）
- 文本预览行为不变（仍走现有 `preview()` UTF-8 路径）
- 安全：raw 端点复用现有 `resolve_file()` 路径校验（防 traversal）
- 上限 50 MiB（避免流式传输超大文件）

## 实现要点

1. **`web_resources.py`**：
   - 新增 `_BINARY_PREVIEW_EXTS`（png/jpg/jpeg/gif/svg/webp/bmp/ico/pdf）和 `RAW_LIMIT`（50 MiB）
   - `preview()` 对二进制预览格式返回 `{"content": null, "encoding": "raw", "media_type": ..., "size": ..., "read_only": True}`，不再抛 `FileNotPreviewable`
   - 新增 `serve_raw(loop_dir, relative)` → `(bytes, media_type)` 供 raw 端点调用
   - `file_summary()` 对二进制预览格式标记 `previewable=True`

2. **`application/web.py`**：
   - `preview_run_file()` / `preview_loop_file()` 对 `encoding=="raw"` 的结果注入 `raw_url`
   - 新增 `serve_run_file_raw()` / `serve_loop_file_raw()` → `(bytes, media_type)`

3. **`presentation/web/server.py`**：
   - 路由正则加 `file(?:/raw)?`
   - `file/raw` 分支：流式返回 bytes + Content-Type + Cache-Control: no-store
   - loops 路由同理加 `/file/raw`

4. **前端**：
   - `types.ts`：`RunFileContent` 加 `encoding?` / `raw_url?`
   - `App.tsx`：`RunFilePreviewDialog` 按 `media_type` 渲染 `<img>`（image/*）/ `<iframe>`（application/pdf）/ `<pre>`（文本）
   - `styles.css`：`.file-preview-image` / `.file-preview-pdf` 样式
