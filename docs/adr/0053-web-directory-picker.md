---
title: ADR 0053 — Web 端跨平台目录选择器
description: 用 server 端目录列表端点 + 浏览器端模态目录浏览器替代 macOS-only osascript 目录选择器，修复远程/非 macOS 场景下 Browse 按钮失效问题（BL-009）
type: adr
status: proposed
created: 2026-07-27T07:50:00Z
---

# ADR 0053: Web 端跨平台目录选择器

## Context

ADR-0042 为 New Run 对话框引入了 Browse 按钮，通过 `POST /system/pick-directory` 调用 macOS `osascript choose folder`。该方案有两个缺陷：

1. **非 macOS 平台完全失效**：`sys.platform != "darwin"` → 501 `not_supported` → 前端隐藏 Browse 按钮（AC-025-B-7）。远程 Linux 服务器部署时用户点击 Browse 无反应。
2. **远程 Web 访问时 osascript 弹窗出现在 server 屏幕**：即使 server 是 macOS，远程浏览器用户看不到弹窗，无法操作。osascript 方案只在 localhost（server == client 同机）场景有效。

BL-009 已在 backlog 记录此问题。

## Decision

### 1. 新增 `GET /api/v1/system/list-directory` 端点

跨平台目录列表端点，用 `os.scandir` 列出指定路径下的子目录：

- 参数：`path`（可选，缺省 = server cwd）
- 响应：`{"path": "/abs/dir", "parent": "/abs", "entries": [{"name": "subdir", "path": "/abs/dir/subdir"}, ...]}`
- 只返回子目录（不含文件），因为用途是选择目录
- 校验沿用 ADR-0042 §3：绝对路径 + 已存在 + 是目录

### 2. 前端用 Web 模态目录浏览器替代 osascript 调用

New Run 对话框的 Browse 按钮改为打开一个模态目录浏览器：

- 初始显示 server cwd 的子目录列表
- 点击子目录进入、点击 Parent 返回上级
- 路径输入框可手动输入路径跳转
- Select 确认选中路径，填充到 working directory 输入框

所有平台统一走此路径，不再依赖 server 端 GUI。

### 3. 旧端点保留

`POST /system/pick-directory` 保留不动（向后兼容），前端不再调用。

## Security

沿用 ADR-0042 §3 信任边界：本地单用户工具，server 由用户自己启动，仅校验绝对路径 + 已存在 + 是目录。未来若 server 面向多用户暴露，再引入 allow-root 配置。

## Alternatives

| 方案 | 评估 |
|------|------|
| **保留 osascript + 添加非 macOS fallback** | 拒绝。两条代码路径增加复杂度，且 osascript 在远程场景（即使 macOS server）仍无效 |
| **纯前端浏览器 File System Access API** | 拒绝。API 兼容性差（仅 Chromium），且访问的是 client 文件系统而非 server 文件系统，语义错误 |
| **废弃旧端点** | 暂不废弃。旧端点不影响新功能，保留向后兼容 |

## Consequences

- 所有平台和所有访问模式（local/remote）均可浏览目录
- 旧 osascript 端点保留但前端不再使用
- 新端点不暴露文件内容（只列目录名），安全面与 ADR-0042 一致

## Verification

非技术选型类 ADR：使用标准库 `os.scandir`，无新依赖。可行性由 AC-025 新增场景的自动化测试直接证明。
