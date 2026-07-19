---
title: WebUI Security Test Report
description: 记录 Web 服务网络、路径、进程、输入、诊断与依赖安全专项结果。
type: report
status: complete
created: 2026-07-19T07:10:00Z
---

# 结果

| 测试层 | 通过/总数 | 失败 | 结果 |
|--------|----------|------|------|
| 定向安全自动化 | 19/19 | — | PASS |
| npm audit（low+） | 0 vulnerabilities | — | PASS |

验证覆盖路径穿越、外链 symlink、二进制/超限文件、默认 loopback、remote opt-in、PID identity、原子写失败、请求体上限、Backend 不存在/超时/启动失败、secret redaction 与非法 UTF-8。未发现敏感信息泄露或未授权访问。
