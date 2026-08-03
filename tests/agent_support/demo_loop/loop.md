---
name: demo
description: Demo loop — mock backend generates binary assets and requests approval
file_changes:
  enabled: true
---

# demo

端到端黑盒 demo loop（BL-057/058）：

1. 阶段一：`assets` agent 用 mock backend（`--mock bash`）执行 `python3 gen_assets.py`，
   在工作目录生成 `chart.png` 与 `report.pdf`（真实二进制文件，供 WebUI 预览 AC-033）。
2. 阶段二：workflow 调用 `intervene()` 请求批准（AC-023），等待人工应答后完成。

用途：SYSTEM_TEST 真实链路黑盒（不调付费 Agent，可入 CI）。
