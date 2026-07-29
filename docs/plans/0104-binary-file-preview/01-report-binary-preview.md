---
title: BL-051 WebUI 二进制文件预览 Report
description: 图片/PDF 预览实现完成，raw 端点流式返回，12 个单元测试 + 44 个集成测试全绿，前端构建通过
type: report
status: complete
created: 2026-07-29T07:15:00Z
---

# Report: BL-051 WebUI 二进制文件预览

## 验收结果

| 验收项 | 结果 | 证据 |
|--------|------|------|
| preview() 对图片/PDF 返回 encoding=raw | PASS | `test_loop_preview_binary_image_and_pdf` |
| preview() 对超限二进制文件拒绝 | PASS | `test_loop_preview_rejects_oversized` |
| file_summary 标记图片为 previewable | PASS | `test_loop_file_summary_marks_binary_previewable` |
| 既有二进制文件（.bin）仍被拒绝 | PASS | `test_loop_preview_rejects_traversal_symlink_binary_and_large` |
| 既有文本预览不受影响 | PASS | 同上（workflow.py preview 正常） |
| Web API 集成测试不回归 | PASS | `test_web_api.py` 44/44 |
| 前端构建通过 | PASS | `npm run build` ✓ |

测试：`uv run pytest tests/unit/test_web_resources.py -v` 12/12 passed；`uv run pytest tests/integration/test_web_api.py -x -q` 44/44 passed。前端 `npm run build` 通过。

## 实现摘要

- 后端：`web_resources.py` 新增 `_BINARY_PREVIEW_EXTS` + `RAW_LIMIT` + `serve_raw()`；`preview()` 和 `file_summary()` 对图片/PDF 格式放行
- 应用层：`web.py` 的 preview 方法注入 `raw_url`；新增 `serve_run_file_raw` / `serve_loop_file_raw`
- 服务器：`server.py` 路由匹配 `file/raw`，流式返回 bytes + Content-Type
- 前端：`types.ts` 加 `encoding?` / `raw_url?`；`App.tsx` 按类型渲染 `<img>` / `<iframe>` / `<pre>`；`styles.css` 加图片和 PDF 样式

## 与 Plan 的偏差

无偏差。
