---
title: New Run 对话框 UX Report
description: OS 原生目录选择器（pick-directory 端点 + Browse 按钮）与 Arguments 键值编辑器实现结果留档
type: report
status: done
created: 2026-07-24T06:30:00Z
---

# Summary

0.20.0 RELEASE 人工验收的两条 UX 意见已修复：工作目录支持 OS 原生目录选择器（macOS osascript，其他平台 501 回退手动输入），Arguments 从手写 JSON 改为键值编辑器（智能类型解析）+ JSON 高级模式切换。

# Changes

| 层 | 内容 |
|----|------|
| `application/web.py` | `pick_directory()`：darwin 调 osascript `choose folder`（120s timeout）；选中规范化路径（去尾斜杠保留根 `/`）；取消/超时 → `{path: null, cancelled: true}`；非 darwin 或 osascript 缺失 → 501 `not_supported` |
| `presentation/web/server.py` | `POST /api/v1/system/pick-directory` 路由 + `not_supported: 501` 错误映射 |
| `web/` | `api.pickDirectory()`；NewRunDialog 重写：Working directory 行 Browse 按钮（调用中禁用、cancelled 不变、501 隐藏）；Arguments 键值编辑器（空行忽略、智能类型解析、重复 key 后者覆盖、无条目 args={}）+ JSON 高级模式切换（保留非法 JSON 校验） |
| `tests/web_support/ac_manifest.py` | AC-014-N-9/B-3/B-4 TARGETS 登记；顺带修复 AC-016-N-1 断言漂移（web profile 报错从 2 项断言漂移减为 1 项） |

# AC Results

| AC | 结果 | 测试 |
|----|------|------|
| AC-025-N-6 | [PASS] | 前端 Browse 填充 + 提交测试；后端 `test_pick_directory_returns_normalized_path` / `test_pick_directory_endpoint` |
| AC-025-B-6 | [PASS] | 前端 cancelled 输入不变测试；后端 cancel/timeout 用例 |
| AC-025-B-7 | [PASS] | 前端 501 隐藏 Browse 测试；后端非 darwin/osascript 缺失 501 用例 |
| AC-014-N-9 | [PASS] | `AC-014-N-9: arguments editor builds a typed args object`（`{"name":"review","count":2,"debug":true}` 类型正确） |
| AC-014-B-3 | [PASS] | `AC-014-B-3: blank-key rows are ignored and an empty editor submits {}` |
| AC-014-B-4 | [PASS] | `AC-014-B-4: invalid JSON in JSON mode shows an error and sends nothing` |
| AC-025-N-3 | [PASS] | 回归通过（留空不带 working_directory） |

# Verification Results

| 层 | 结果 |
|----|------|
| Python 全量 | 405 passed, 1 skipped（401 → 405） |
| 前端 vitest | 30 passed（24 → 30，既有未破坏） |
| typecheck / build | clean / 成功，静态资源已同步 |
| Playwright e2e | 10 passed, 2 skipped |
| web profile manifest | 既有漂移仍存（AC-016-N-2 + cases.json 缺失列表），沿用 0077 分类：非阻塞基建缺口，另立 test 容器 |

# Notes

- 键值编辑器忽略规则：空 key 行与 key 非空但 value 为空的行均忽略（plan Constraints "值为空行忽略"）。
- 非 macOS 原生选择器未实现（501 回退），未来可按需补 zenity（Linux）/ PowerShell FolderBrowser（Windows）。
- 选择器弹窗出现在 server 所在机器——本地 loopback 使用场景与 WebUI 同机，符合预期；`--allow-remote` 远端使用时选择器在服务端机器弹出，为已知边界。
