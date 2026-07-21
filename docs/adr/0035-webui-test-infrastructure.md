---
title: ADR 0035 - WebUI 测试与交付基础设施
description: 定义 WebUI 的 Python、前端、浏览器、契约、视觉、覆盖率、测试数据、CI 门禁和 wheel 部署冒烟策略
type: adr
status: accepted
created: 2026-07-19T00:00:00Z
---

# ADR 0035: WebUI 测试与交付基础设施

## Context

ADR 0033/0034 和 Interface 0001 已冻结标准库 HTTP/REST/SSE、React/TypeScript/Vite、`@xyflow/react`、持久化事件游标、Run 生命周期与本地 wheel 交付边界。AC-0010 同时要求服务契约、真实浏览器交互、三种视口、视觉无重叠、路径与进程安全、SSE 故障恢复及性能基准。

现有仓库只有 Python pytest/pytest-cov 和 GitHub Actions。架构 spike 证明了前端构建与 SSE 的技术可行性，但 jsdom 不能验证 React Flow 的实际尺寸、缩放、fit view、响应式布局或截图。TEST_INFRA 需要提供一次性、可重复且能正确拦截错误的测试底座；具体产品断言仍由后续 DEVELOP Plan 按 AC 编写。

## Decision

### 1. 测试层与入口

采用以下分层，每层具有独立命令，并由统一 MR 门禁组合执行：

| 层 | 工具 | 基建职责 | 业务用例归属 |
|----|------|----------|--------------|
| Python 单元/集成 | pytest | markers、共享 fixture、临时 Run/Loop 根目录 | DEVELOP |
| HTTP 契约 | pytest + 标准库 `http.client`/`urllib` | 黑盒 server lifecycle、JSON/SSE 请求助手、schema-shaped fixture | DEVELOP |
| 前端组件 | Vitest + Testing Library + jsdom | DOM setup、API/SSE mock、覆盖率 | DEVELOP |
| 浏览器系统测试 | Playwright Chromium | webServer fixture、trace、截图、视口矩阵 | DEVELOP/SYSTEM_TEST |
| 视觉回归 | Playwright screenshot | 基线目录、确定性字体/动画设置、差异产物 | DEVELOP/SYSTEM_TEST |

Python HTTP 测试不引入 Web 框架或第三方 HTTP 客户端，以保持服务端运行时边界。Playwright 只作为开发和 CI 依赖，使用项目固定的 Chromium 版本。

### 2. 前端工作区与可测试边界

仓库根目录新增 `web/` 作为独立 Node 工作区，包含 TypeScript、Vite、Vitest、Testing Library、Playwright 配置和测试辅助模块。TEST_INFRA 只加入可构建的最小静态壳及基础设施冒烟，不实现 Runs、Loops、Backends 或任何 Interface 0001 业务行为。

构建产物同步到 `src/loopflow/presentation/web/static/`，由 hatch wheel 收录。同步必须清理并完整替换仅该受控生成目录，禁止读取或写入 `references/`。生产 wheel 不包含 Node 运行时和 `node_modules`。

### 3. 测试数据工厂与替身

Python fixture 工厂在 pytest 临时目录中创建确定性的：

- v2 Run：`run.json`、纯 workflow `state.json`、带递增 `event_id` 的 `events.jsonl`；
- legacy Run：无版本事件、可归属与 `unattributed` 事件、malformed 行；
- stale/running/done/failed/stopped/unreadable Run 元数据；
- Loop 根目录、允许预览文件、路径穿越与 symlink escape；
- 1000 Runs、1000 个 1 KiB 事件的性能数据集；
- Backend 探测与 diagnostics 的正常、不可用、超时、启动失败输出。

Backend 替身实现应用层 port，而不是伪造 CLI 文本。其 DTO 字段、枚举和错误形状逐项对照 Interface 0001；secret fixture 只使用显然为测试值的字符串。进程探测器与时钟使用可注入替身，禁止在高频 CI 调用真实付费 Backend。项目没有必须配置的付费沙箱资源，因此付费依赖隔离和沙箱账号门禁不适用。

### 4. 契约与 AC 覆盖清单

测试元数据以稳定的完整 AC 场景 ID 标注，例如 `AC-014-N-1`。`tests/system/cases.json` 是机器可读的系统测试清单，每条至少记录 `ac_id`、测试文件/节点 ID、被测接口或 UI 操作、输入 fixture、预期 HTTP 状态码或 SSE event，以及关键断言字段。静态检查器读取 AC-0010 表格、Interface 0001 的冻结 endpoint/status/event 清单和该 manifest，要求 AC-014..019 的每个场景均存在且不重复、N/B/E/F 分类一致、接口/入参与状态码或 event 合约一致、关键预期不为空，并拒绝未知 ID。测试节点不存在、只有名称没有断言元数据，或接口错误码不合约都必须失败。

HTTP helper 统一验证状态码、content type、错误信封、Location、1 MiB 请求上限与 SSE frame。Interface-shaped mock 的字段和类型由独立 schema 断言验证，防止前后端 fixture 漂移。

### 5. 覆盖率

Python 延续 pytest-cov，MR 门禁以 `pyproject.toml` 的单一阈值为准并生成 XML；前端使用 Vitest V8 coverage，对 `web/src` 的 statements、branches、functions、lines 分别设置阈值并生成 text/JSON。基础设施用一个分支数已知的小模块自证采集值与人工统计一致，随后删除该故意样例，不以它抬高产品覆盖率。

当前 Python 历史基线阈值保持 59，避免测试基建变更伪造业务覆盖提升；每个 DEVELOP Report 仍须记录受影响模块覆盖率，WebUI 合并提测前由 Plan 将新增 Python/TypeScript 代码提升到不低于 80%。提测门禁读取机器生成的 coverage summary，不接受 Report 自报数字。

### 6. 真实浏览器与视觉门禁

Playwright 固定验证 Chromium 下的 `1440x900`、`1024x768`、`390x844` 三个 viewport。基础设施冒烟必须证明浏览器能启动、页面非空、截图与 trace 可产出。业务测试在 DEVELOP/SYSTEM_TEST 中验证：

- React Flow canvas/SVG 有非背景像素且节点 bounding box 非零；
- fit view、缩放、节点选择和键盘路径改变预期可观察状态；
- 页面无水平滚动，主要区域与文字没有非预期相交；
- 长无空格输出不越界；
- 截图基线覆盖三种视口，失败保存 actual/diff/trace。

截图环境关闭动画、固定 locale/timezone/color scheme 和测试数据。Python matrix 固定为 3.10 与 3.14，Node 固定 major 22；npm lockfile 锁定 Playwright package，`playwright install --with-deps chromium` 安装该 package 对应的唯一 Chromium revision。基线只在明确的视觉变更审查中更新，CI 不自动重写基线。像素检查是布局断言的补充，不能替代语义与可访问性断言。

### 7. CI、MR 门禁与提测门禁

GitHub Actions 使用独立 jobs：

1. Python 3.10 与 3.14 运行 pytest 和 coverage；
2. Node 22 执行 lockfile 安装、typecheck、Vitest、coverage、Vite build 和 dependency audit；
3. Linux Chromium 执行 Playwright 冒烟/系统测试并上传失败截图与 trace；
4. 构建 wheel，在无 Node 的隔离环境安装，并通过 `importlib.resources` 读取入口与 hashed 静态资产。

本地 `scripts/mr-gate.sh` 与 CI 调用同一组底层命令。门禁脚本启用 fail-fast shell 语义并传播任一子命令的非零退出码；自证时注入故意失败测试，先确认本地门禁非零，再提交测试分支并记录 GitHub Actions required check 报红和 merge 被阻断的 URL/截图证据；删除失败样例后同一 check 必须转绿。若仓库 required-check 设置不可读或不可配置，TEST_INFRA 门禁不通过，不能用本地执行替代。

`scripts/submission-gate.py` 检查：执行容器 README 状态、Plan=done、Report=complete、Plan 显式声明的 AC 集合与 Report 逐项 `[PASS]` 一一对应、提交引用、机器 coverage 阈值和测试结果文件。局部 DEVELOP Plan 只需通过自己声明的集合；进入 SYSTEM_TEST 前，所有已合并 Plan 的集合并集必须覆盖 manifest 全集。缺失、`[TODO]`、`[FAIL]`、重复/未知 AC、未声明的 PASS 或伪造 coverage 路径均返回非零。自证 fixture 置于专用目录，不污染正式 Report。

### 8. 本地部署底座

loopflow 是本地 CLI 安装包，不配置远程生产平台。TEST_INFRA 适用的部署底座是可复现的 wheel 流水线：前端 production build、静态资产同步、wheel 构建、隔离安装，并通过 `importlib.resources` 读取入口与 hashed asset。浏览器框架使用 tests-only loopback 占位 server 验证静态页面，不注册生产 CLI，也不实现 `/api/v1`。实际 `loop web` 启动、监听和远程绑定双确认留给 DEVELOP 的产品实现与测试。

## Alternatives

### 方案 A：只使用 Vitest/jsdom

- 优点：安装和执行更快。
- 缺点：无法证明 React Flow viewport measurement、真实键盘焦点、响应式抽屉、页面滚动或截图，不能覆盖 AC-019。

### 方案 B：Cypress 作为浏览器框架

- 优点：交互式调试成熟。
- 缺点：Playwright 的多 viewport project、trace、内置 webServer 和 screenshot assertion 更直接符合本项目的本地服务与视觉门禁。

### 方案 C：OpenAPI 代码生成作为契约事实源

- 优点：可自动生成 client/schema。
- 缺点：当前冻结接口是 Markdown 表格且服务端使用标准库；在 TEST_INFRA 反向发明一份 OpenAPI 会形成第二事实源。首版使用 Interface-shaped fixture 与显式 schema 断言。

### 方案 D：端到端测试调用真实 Backend

- 优点：更接近用户环境。
- 缺点：环境不确定、可能消耗配额、输出不可重复。CI 使用 port-level 替身；真实可用性只在明确的手动诊断或发布验证中检查。

## Consequences

### 正面

- Python、TypeScript、HTTP、SSE、真实浏览器和 wheel 交付都有稳定入口。
- 三视口、React Flow 像素、截图和无重叠约束在真实 Chromium 中验证。
- fixture 与 schema 检查使 legacy、故障和 Backend 输出可以确定性复现。
- MR 与提测门禁由同一脚本在本地和 CI 运行，并能用故意失败样例自证。

### 负面

- CI 增加 Node、Chromium 下载、截图和 wheel 冒烟时间。
- Markdown Interface 的 schema helper 需要随冻结接口显式维护。
- 视觉基线在不同渲染环境下敏感，因此只能在固定 Linux Chromium 环境比较。

### 不做的

- TEST_INFRA 不编写 AC-014..019 的产品实现或完整业务测试。
- 不让 jsdom 结果替代真实浏览器证据。
- 不自动接受或更新视觉基线。
- 不在 CI 调用真实付费 Agent Backend。
- 不把 `references/code*.html` 当作可执行契约或视觉基线。

## Architecture Boundary

```text
tests/                       # Python unit/integration/contract/system helpers
web/                         # React source, Vitest and Playwright infrastructure
scripts/mr-gate.sh           # MR 组合门禁
scripts/submission-gate.py   # Plan/Report/AC/coverage 提测门禁
.github/workflows/test.yml   # CI jobs and artifacts
src/loopflow/presentation/web/static/  # wheel 内生成资产
```

测试 helper 可以依赖冻结的 Interface/AC 和公开应用 port；产品代码不得依赖测试目录、Playwright 或 Node 工具链。

## Verification

ADR 已在一次性基建完成后依据以下证据接受：

| 验证项 | 通过条件 | 证据位置 |
|--------|----------|----------|
| MR 拦截 | 故意失败测试使本地门禁非零且远端 required check 报红/阻断 merge，删除后全绿 | PR #1；失败 run `29669931354` / commit `eee2fd1` 为 `BLOCKED`；恢复 run `29672196161` 五项全绿 |
| 提测拦截 | invalid Report、缺 AC、低 coverage 均被拒绝 | `tests/infrastructure/test_submission_gate.py` 四类反例通过；commit `23dd4ab` |
| Mock 契约 | Run/Loop/Queue/Backend/SSE fixture schema 全部通过 | `tests/infrastructure/test_web_test_support.py`；远端 Python 3.10/3.14 checks 通过 |
| 覆盖率准确 | 已知分支 fixture 的工具结果等于人工统计 | `./scripts/verify-coverage.sh`：2/2 branches，100% |
| 浏览器冒烟 | Chromium 启动、页面非空、截图/trace 可生成 | run `29672196161` browser check；1440x900、1024x768、390x844 均产出 smoke.png 与 trace.zip |
| AC 静态覆盖 | manifest 覆盖 AC-014..019 全场景，接口/入参/status/event/断言元数据与 Interface 一致，任一偏差即失败 | `python3 scripts/check-ac-manifest.py --allow-planned`：60 scenarios；缺失/漂移反例测试通过 |
| Wheel 冒烟 | 隔离安装后无 Node 可通过 `importlib.resources` 读取入口与 hashed asset | run `29672196161` wheel check；Python 3.10 读取 index + 2 hashed assets |
