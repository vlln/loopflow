---
title: manifest strict 欠账清理 Plan
description: AC-010-N-2/E-2 契约漂移按裁决修 AC 文本对齐 ADR-0031 现行实现；web profile 6 个历史 planned 场景（AC-015-F-3/N-7/N-8、AC-016-B-3/F-3、AC-019-B-3）补真实测试，漂移场景实证后修 AC 文本；三 profile manifest strict 全绿
type: plan
status: in_progress
created: 2026-07-25T07:40:00Z
---

# Context

三 profile AC manifest 中剩 8 个 `planned::` 占位：scheduling 2 个（AC-010-N-2/E-2，BL-010 契约漂移，用户已裁决改 AC 文本对齐实现）、web 6 个（AC-015-F-3/N-7/N-8、AC-016-B-3/F-3、AC-019-B-3）。本容器是 SYSTEM_TEST→TEST_INFRA 的基建欠账修复，不收新需求。

实证结论（2026-07-25，读码 + scratch 脚本 + 既有测试）：

- AC-010-N-2：`discovery.list_loops` 对缺 loop.md 的目录直接 `continue`（不可发现），无 workflow.py meta 回退（ADR-0031：loop.md 必选）；`load_loop` 则报错退出。既有覆盖 `tests/unit/test_discovery.py::TestListLoops::test_no_loop_md_not_discoverable`。
- AC-010-E-2：frontmatter 非法 YAML → `_load_loop_meta` 打印 stderr 并 SystemExit，`list_loops` 捕获后跳过该 loop，不影响其他 loop。既有覆盖 `TestLoopMd::test_loop_md_bad_yaml`。
- AC-015-F-3：declared phases 实际来自 loop.md frontmatter（`web_resources._extract_declared_phases`），workflow.py 语法错误不影响提取；WebUI 启动 Run 时子进程 `load_loop` 失败 → `BackgroundRunExecutor.start` 抛 `RuntimeError("run_process_start_failed")` → API 500 `internal_error`，不创建 Run，服务不崩溃。
- AC-015-N-7/N-8：合并语义在前端 `PhaseGraph`（App.tsx :201-213）：runtime 节点替换占位、未声明 runtime 节点打 `is-undeclared` 类（accent 边框色，无文字 badge）。phase graph 数据来自 Run 详情投影，SSE 事件不直接更新图（`connectRunEvents` 只进 eventReducer/fileChanges），占位替换在 Run 详情（重新）加载时发生。
- AC-016-B-3：server `_events` 仅当 `ev_terminal and fc_terminal` 才发 `stream_end`，fc 未 terminal 时继续轮询推送——与 AC 文本一致（scratch 脚本验证事件序：run_event → file_changes×2 → stream_end 带双游标）。
- AC-016-F-3（漂移）：file_changes 读取抛 OSError 时，轮询路径落入 server `_events` 通用 `except Exception`，发 `stream_error {code: event_read_failed, last_event_id}`（无 topic 字段）后关闭连接，run_event 不再推送；首次 replay 抛错则 200 头后写入 500 错误体。与 AC 文本「topic=file_changes、run_event 不受影响」不符——按裁决修 AC 文本，不改行为。
- AC-019-B-3：light 主题对比度，沿用 AC-019 视觉场景既有层（playwright `web/tests/webui.spec.ts`），light colorScheme 下断言面板/徽章计算色对比并截图。

# Request

8 个 planned 占位全部转真实测试节点，三 profile strict 全绿。漂移场景（AC-010-N-2/E-2、AC-015-F-3/N-7/N-8、AC-016-F-3）只修 AC 文本对齐实证行为，不改实现。

# Output Format

- AC 文本：`docs/ac/0004-scheduling.md`（AC-010-N-2/E-2 两行）；`docs/ac/0010-webui.md`（AC-015-F-3/N-7/N-8、AC-016-F-3 四条）
- backlog：`docs/backlog.md` BL-010 状态 done（关联迭代 0.21.0）
- 测试：
  - `tests/unit/test_discovery.py`：两条既有用例补「合法 loop 并存不受影响」断言
  - `tests/integration/test_web_api.py`：AC-015-F-3（语法错误 loop 启动 Run → 500 internal_error、loop 详情与 declared_phases 不受影响、服务存活）、AC-016-B-3（fake app 双 topic 门控）、AC-016-F-3（fake app fc OSError 实证行为）
  - `web/src/App.test.tsx`：AC-015-N-7（占位→实际节点合并）、AC-015-N-8（undeclared 标记）
  - `web/tests/webui.spec.ts`：AC-019-B-3（light 主题对比 + 截图）
- manifest：`tests/scheduling_support/manifest.py` TEST_NODES +2；`tests/system/scheduling_cases.json`、`tests/system/cases.json` 8 条换真实节点并同步文本
- Report：`docs/plans/0086-manifest-debt-cleanup/01-report-manifest-debt-cleanup.md`

# Constraints

- 不改任何实现行为；漂移一律修 AC 文本并在 Report 记录实证依据
- 文档与代码分开 commit：`docs(ac)`（AC-010 + backlog）、`docs(ac)`（web 漂移）、`test(...)`（各层补测试）、`test(infra)`（manifest 登记）、`docs(plan)`（容器与 Report）
- uv.lock 既有未提交修改不触碰、不入任何 commit
- playwright 只用于 AC-019-B-3（视觉场景既有层）；其余优先 pytest / vitest

# Steps

1. 容器文档（README + Plan）+ plans/README 索引，分支 `test/0086-manifest-debt-cleanup`
2. 任务 A：AC-010-N-2/E-2 文本修正 → discovery 测试增强 → scheduling manifest 登记 → backlog BL-010 done
3. 任务 B：4 条漂移 AC 文本修正 → 6 个测试补写（pytest×3、vitest×2、playwright×1）→ web manifest 登记
4. 门禁：三 profile strict、`uv run pytest tests/ -q`、`cd web && npm run test:coverage && npm run build`、playwright 新增部分
5. Report 归档，合并 develop（--no-ff），删分支，不 push

# Acceptance

- AC-010-N-2：loop.md 缺失（workflow.py 含 meta）时 `loopflow list` 正常输出但不包含该 loop，无 meta 回退，其他 loop 不受影响
- AC-010-E-2：frontmatter 非法 YAML 时该 loop 被跳过，stderr 记录解析错误，其他 loop 不受影响
- AC-015-F-3：workflow.py 语法错误的 loop 启动 Run，API 返回错误，不创建 Run、无占位节点，服务不崩溃
- AC-015-N-7： declared 占位的 phase 执行后（详情重新加载）替换为实际节点，未执行的 declared phase 保持占位
- AC-015-N-8：未声明的 runtime phase 以 undeclared 视觉标记（is-undeclared 类）出现
- AC-016-B-3：run_event 已 terminal 而 file_changes 未 terminal 时不发 stream_end，fc 数据继续推送，双 topic 均 terminal 后才 stream_end
- AC-016-F-3：file_changes 读取 OSError 时服务发 stream_error（event_read_failed，实证行为）后关闭连接
- AC-019-B-3：light 主题下面板背景与前景文字不同色、status 徽章可辨，截图留存
- 三 profile `check-ac-manifest.py` strict 全绿；`uv run pytest tests/ -q` 全绿；`npm run test:coverage && npm run build` 绿
