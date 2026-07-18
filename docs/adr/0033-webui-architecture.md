---
title: ADR 0033 — 本地 WebUI 技术栈与分层
description: 以 Python 标准库 HTTP server 提供 REST 与 SSE，以 React、TypeScript、Vite 构建本地单用户控制台
type: adr
status: proposed
created: 2026-07-18T00:00:00Z
---

# ADR 0033: 本地 WebUI 技术栈与分层

## Context

Spec 0001 v12 增加本地 WebUI 控制台。WebUI 需要读取 Loop、Run、Queue 与 Backend 的现有文件模型，实时重放和订阅 Run 事件，并执行 run、stop、resume、reconcile 等受状态约束的命令。

现有 CLI 中仍有直接读取文件、协调用例和格式化输出混合的路径。若 Web 层调用 CLI 子进程并解析文本，会形成不稳定的内部协议；若浏览器直接理解运行目录，则会把路径校验、legacy 兼容和生命周期规则复制到前端。WebUI 还必须保持 loopflow 的本地工具定位，不为 Web 传输层新增 Python 运行时依赖，也不因增加 UI 要求用户常驻 Node.js 服务。

需要决定服务端、浏览器端、实时传输协议及它们与既有领域/应用层的边界，并避免为 Web 传输层新增 Python 运行时依赖。

## Decision

采用一个随 loopflow 安装和启动的本地 Web 服务，以及编译为静态资产的单页应用：

| 层 | 技术 | 职责 |
|----|------|------|
| 浏览器展示层 | React + TypeScript + `@xyflow/react` | Runs、Loops、Backends 主从工作区，状态渲染、Phase 图和用户交互 |
| 前端构建 | Vite | 开发服务器、类型检查、生产静态资产构建；仅为开发/构建依赖 |
| Web 传输适配层 | Python 3.10+ 标准库 HTTP server | 静态资产、JSON REST API、SSE 事件流、HTTP 错误映射 |
| 应用层 | Python application services | 查询读模型，协调 run/stop/resume/reconcile、Loop 文件预览和 Backend 诊断 |
| 基础设施层 | 现有 repository/context/backend/queue 适配器 | 文件系统持久化、进程检查、事件读取和 Backend 调用 |

### 1. 服务进程与网络边界

新增 `loop web` 启动 Python HTTP server，默认绑定 `127.0.0.1`。非 loopback 地址必须同时指定目标 `host` 和独立的 `allow-remote` 显式开关；仅指定 `host` 必须拒绝启动。首版不提供认证、多用户会话或远程协作。

生产安装包携带 Vite 构建后的静态资产。Node.js、Vite 和前端依赖不进入 Python 运行时依赖，也不在用户启动 WebUI 时参与执行。

### 2. REST 与 SSE 分工

JSON REST API 承担有界查询和命令：

- 查询 Runs、单个 Run、Loops、Loop 允许的文件、Queue、Backends；
- 发起 run、stop、resume、rerun、reconcile、enqueue 等状态转换；
- 使用明确的 4xx 冲突、路径拒绝和资源不存在响应，不把 CLI 文本作为 API 契约。

SSE 仅承担服务端到浏览器的 Run 事件流。客户端以 `last_event_id` 游标订阅；服务端先重放已持久化事件，再持续推送新增事件。SSE 连接不创建、恢复或重复执行 Run。

首版不使用 WebSocket：交互命令仍通过 REST，实时数据是单向追加事件，SSE 已覆盖断线恢复和增量推送需求。

### 3. 应用边界

CLI 与 Web 适配器共享同一组应用服务，不互相调用：

```text
CLI adapter ──┐
              ├── application services ── domain/infrastructure ports
Web adapter ──┘
```

- Web handler 不通过 subprocess 调用 `loop`，不解析 CLI stdout/stderr；
- Web handler 不直接拼接 Loop/Run 路径，不自行判定 Run 状态转换；
- 浏览器不读取本地文件系统，也不推断 legacy 事件归属；
- application services 返回结构化 DTO/错误，CLI 和 Web 分别完成文本或 HTTP 表示；
- 文件系统写入、进程身份校验、事件信封与缓存语义由基础设施适配器实现，不进入 React 状态逻辑。

### 4. 前端边界

前端按 Spec 的三个一级工作区实现 `Runs`、`Loops`、`Backends`；Queue 首版作为 Runs 内的模式。视觉 token 只来自 `references/DESIGN.md`。

React 只保存展示状态、筛选条件、当前选择及 SSE 游标。Run 状态、Phase occurrence、Call 关联和 Backend 能力均以服务端结构化响应为准，不从文案、日志位置或前端时间推断。

Phase 图使用成熟的 `@xyflow/react` 处理节点、边、缩放、平移、选中和可访问交互，不自行实现图形交互引擎。服务端 PhaseGraph 读模型提供聚合节点、forward/back edge、occurrence 和 current path 语义；前端只负责布局与渲染，不重新推断循环或分支。

## Alternatives

### 方案 A：Python 标准库 HTTP server + React/TypeScript/Vite（采用）

- 优点：不为 Web 传输层新增 Python 运行时依赖；Node 仅用于构建；REST/SSE 与本地单用户规模匹配；可复用既有 Python 应用层。
- 缺点：路由、请求体上限、错误映射、SSE 连接清理和安全 header 需要自行实现并测试；标准库 server 不是通用生产 Web 框架。

### 方案 B：FastAPI/Starlette + React/TypeScript/Vite

- 优点：路由、校验、流式响应和 OpenAPI 支持成熟，后续扩展更容易。
- 缺点：为 Web 传输层新增 ASGI server、框架及校验栈等 Python 运行时依赖；对仅本机的首版控制台成本偏高。

### 方案 C：Python 服务端渲染 + 少量原生 JavaScript

- 优点：前端构建链简单，初始代码量较小。
- 缺点：Run 工作台包含常驻主从布局、执行图、流式事件和复杂 Inspector，手工 DOM 状态管理会快速失控；组件复用和类型契约较弱。

### 方案 D：Electron/Tauri 桌面应用

- 优点：可以提供独立桌面壳和系统集成。
- 缺点：打包、升级和跨平台复杂度显著增加；偏离现有 CLI 安装模型；首版不需要原生桌面能力。

### 方案 E：WebSocket 作为统一协议

- 优点：双向连接可承载命令和事件。
- 缺点：需要自行设计请求/响应关联、重连和幂等语义；当前命令是低频 REST 操作，事件是单向追加流，复杂度没有对应收益。

## Consequences

### 正面

- 用户运行 WebUI 时只需要已安装的 loopflow，不需要 Node.js 或额外 Python Web 框架。
- REST 命令与 SSE 事件职责明确，SSE 可直接使用持久化 `event_id` 断线恢复。
- CLI 与 WebUI 共享应用规则，避免两套状态转换、路径安全和进程生命周期实现。
- React/TypeScript 适合实现高密度主从工作台、执行图和渐进事件展示。
- `@xyflow/react` 提供经过验证的图交互能力，避免自行维护缩放、选中和边命中逻辑。

### 负面

- 仓库增加前端工具链、静态资产打包和 Python/TypeScript 两套测试。
- 标准库 HTTP server 的协议细节需要项目自行维护；若未来支持远程、多用户或高并发，需要重新评估框架。
- 应用服务边界必须先从 CLI 直读直写路径中提取，首版实现不是单纯增加页面。
- 静态资产与 API 版本需要在同一发行包中保持兼容。

### 不做的

- 不让浏览器直接访问任意文件路径。
- 不通过 shell 调用 CLI 作为 Web 后端。
- 不在首版提供认证、多用户、远程部署或第三方遥测。
- 不用拖拽图编辑器替代 `workflow.py`。
- 不承诺标准库 HTTP server 适用于公网生产服务。

## Architecture Boundary

约束新增 Web adapter、前端应用和共享 application services：

```text
web/                              # React/TypeScript/Vite 源码与测试
src/loopflow/presentation/web/    # HTTP、REST、SSE、静态资产适配
src/loopflow/application/         # CLI/Web 共享查询与命令用例
src/loopflow/infrastructure/      # 文件、进程、事件、Backend 适配
```

具体目录名可在实现 Plan 中按现有代码结构微调，但依赖方向不可反转：application 不依赖 HTTP/React，Web 不绕过 application 写运行状态，frontend 不拥有后端领域规则。

## Verification

本 ADR 包含技术选型，需要在进入实现前以 spike 验证标准库 HTTP server 对 SSE 和打包的可行性。验证记录在完成后回填；spike 分支保留、不合并。

| 验证项 | 复现步骤 | 结论 | 经验 | 验证 Branch |
|--------|---------|------|------|------------|
| SSE 重放与持续推送 | `uv run python -m unittest -v test_server_spike.py` | 可行：重放 2/3 后持续收到 4，last_event_id=3 重连只收到 4 | 持久化 reader 与 condition 通知可组合，连接本身不触发 Run | spike/0033-webui-architecture@ba32790 |
| 慢客户端与连接清理 | 同时建立并关闭 8 个 SSE 客户端，再追加事件 | 可行：8 个 handler 均捕获断连并由 daemon thread 回收，Run 写入未阻塞 | 正式实现仍需连接上限、heartbeat 和故障注入测试 | spike/0033-webui-architecture@ba32790 |
| Vite 资产随 Python 包发布 | `npm run build && ./sync_assets.sh && uv build wheel-fixture`，再从 isolated Python 读取 `importlib.resources` | 可行：wheel 含带 hash 的 JS/CSS 和 index.html，无 Node 环境可读 | 不能从 Python 项目外 force-include dist；构建前必须同步到包内目录 | spike/0033-webui-architecture@ba32790 |
| Phase 图交互 | `npm test && npm run build`，fixture 含两条 forward edge、一条 backedge、current 和 100 occurrence | 可行：2 个组件测试和 Vite production build 通过，Controls/fitView/节点选择可渲染 | 视觉布局与像素回归留给 TEST_INFRA 的浏览器测试 | spike/0033-webui-architecture@ba32790 |
| 默认绑定和路径边界 | Python 测试默认 socket、host+allow_remote 校验、`..` 与 symlink escape | 可行：默认 127.0.0.1；无 allow_remote 拒绝 0.0.0.0；两类路径逃逸均拒绝 | 远程绑定必须是独立双确认，不能把 host 参数本身当确认 | spike/0033-webui-architecture@ba32790 |
