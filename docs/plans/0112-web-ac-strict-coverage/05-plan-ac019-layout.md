---
title: AC-019 WebUI 布局与可访问性覆盖补齐
description: 为 AC-019 的 14 个 planned 场景编写真实测试节点，必要时补产品行为
type: plan
status: pending
created: 2026-07-30T00:00:00Z
---

# Context

AC-019 planned 全部 14 个：N-1（1440x900 三栏可见+LR 无重叠截图）、N-2（键盘路径：focus 可见、逐级详情、recover retry 只发一次）、N-3（默认仅监听 127.0.0.1）、N-4（0.0.0.0 + allow-remote 启动成功+stderr 警告）、N-5（主题切换持久化+默认跟随系统）、B-1（1024x768 Inspector 抽屉）、B-2（390x844 单区域+无水平滚动）、B-3（light 主题对比度）、B-4（error_summary 2 行截断）、E-1（500 字符无空格 overflow-wrap）、E-2（SSE 断线显示中断+保留数据+重连不闪烁）、F-1（图标按钮 accessible name/tooltip）、F-2（禁用颜色后状态仍可文字/图标区分）、F-3（0.0.0.0 无 opt-in → 启动失败非零+stderr 提示）。分支 `feat/0112-ac019-layout`。

# Request

1. 为 14 个场景各写真实测试节点：进程行为（N-3/N-4/F-3，manifest target `process:loop-web`）用 Python 集成测试（监听 socket/退出码/stderr 断言），布局/可访问性/主题（其余 11 个，target `ui:layout`）用 `web/tests/webui.spec.ts` Playwright（截图/视口/键盘/可访问性树）+ 必要时 `web/src/App.test.tsx`。
2. TDD 先红后绿；产品行为不符冻结契约时补最小实现。
3. `TEST_NODES` 仅追加 AC-019 段，重新生成 `cases.json`。
4. 验证 strict 下全 profile 0 planned（本单元是最后一个，完成后 strict 全绿）。

# Constraints

- 不改契约文档；契约存疑停下来上报。
- N-3/N-4/F-3 必须断言真实监听 socket 与进程退出码/stderr，不得 mock 掉进程。
- F-1 必须扫描可访问性树断言每个按钮有 accessible name，不得抽查代替。
- E-2 必须断言断线提示可见且既有数据保留，不得仅断言"不崩溃"。
- 只追加 `TEST_NODES` 本段条目；文档与代码分开提交；commit 标注 AC 编号。

# Checkpoint

- [ ] 14 个测试节点有实质断言
- [ ] MR 门禁通过
- [ ] strict 检查 web profile 全绿（0 planned、0 other errors）
- [ ] Report 留档，可反向定位
