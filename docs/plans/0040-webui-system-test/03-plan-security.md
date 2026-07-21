---
title: WebUI Security Test Plan
description: 验证 Web 服务网络、路径、进程、输入、诊断脱敏与依赖安全边界。
type: plan
status: done
created: 2026-07-19T07:10:00Z
---

# Context

Spec 0001、Interface 0001 与 AC-017/018/019 冻结本地 Web 安全边界。

# Request

执行路径穿越/符号链接、loopback/remote opt-in、进程身份、请求上限、诊断脱敏/非法编码与依赖漏洞测试。

# Output Format

独立 Report，记录自动化通过数与漏洞扫描结论。

# Constraints

不得访问 Loop 根外文件，不输出 fixture secret，不启动未授权远程 listener。

# Checkpoint

全部边界检查通过，低等级及以上依赖漏洞为 0。

# Steps

1. 运行定向 Python 安全用例。
2. 运行 npm audit。
3. 复核日志与响应不含 secret。
