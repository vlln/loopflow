---
name: rerun-demo
description: Demo loop — validation-driven rerun (BL-062/ADR-0058). Stage A fails once, validate routes back, stage A succeeds on rerun.
file_changes:
  enabled: true
---

# rerun-demo

校验驱动的重试编排端到端黑盒 demo loop（BL-062/ADR-0058），**与 bio-reproducer 无关**。

用 mock backend（`--mock bash`，prompt 作为 shell 命令执行）演示 `rerun_loop`：

1. 阶段 `make`：先 `touch fail-flag.txt`（写失败标记），然后执行
   `rerun_probe.sh`——该脚本第一次运行（fail-flag 存在时）返回 exit 1，
   随后删除 fail-flag；第二次运行返回 exit 0。
2. 校验回调（workflow 内 `validate()`）：检查 `make` 阶段的退出码文件
   （`make_exit.txt`）——非 0 返回 route_key `"make"`，0 返回 None。
3. `rerun_loop` 按 route_map `{"make": "make"}` 回退重跑阶段 make，
   第二次成功 → 终止。

用途：SYSTEM_TEST 验证 rerun_loop 真实链路黑盒（不调付费 Agent，可入 CI）。
