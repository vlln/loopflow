---
title: Recovery Control Test Infrastructure
description: 定义恢复、永久停止和人工介入的缓存工厂、Backend 替身、故障注入、进程组与 AC manifest 测试底座
type: adr
status: proposed
created: 2026-07-22T08:00:00Z
---

# ADR 0037: Recovery Control Test Infrastructure

## Context

ADR 0036 与 AC-020..022 冻结了可校验重放、retry/continue、execution epoch、进程组取消和持久化 Intervention。现有 pytest、Web fixture、HTTP helper、AC manifest、Playwright 和门禁已经稳定，不需要引入新的测试框架；但当前 fixture 只能表达单段 `<seq>.jsonl`、简单进程身份和旧 Run 状态，无法可靠制造以下条件：

- 同一 Call 内失败、retry、continue 多生命周期段及半写缓存；
- backend session ID 提前/延后暴露、durable/non-durable 能力组合；
- 原子写失败、迟到 worker、PID 复用和 SIGTERM 后拒绝退出；
- workflow 提前结束、digest 漂移和 persisted Intervention 回答；
- AC-020..022 与新 endpoint/error/status 的静态契约漂移。

TEST_INFRA 需要搭建这些可复用测试能力并反向证明它们能拒绝错误 fixture，但不实现 recover、stop、intervene 或产品 UI。

## Decision

### 1. 复用现有测试栈

继续使用 pytest、标准库 tempfile/subprocess/multiprocessing、现有 `tests/web_support`、Vitest 和 Playwright。恢复专项基础设施放在 `tests/recovery_support/`，基础设施自证放在 `tests/infrastructure/`。不增加运行时或开发依赖，不调用真实 Agent backend。

### 2. Call 缓存与重放 fixture

提供 `CallCacheFactory`，只能在 pytest 临时目录写入以下确定性 fixture：

| fixture | 必备内容 |
|---------|----------|
| succeeded | agent_start + message + succeeded agent_done |
| failed | agent_start + 可选 agent_session + failed agent_done |
| interrupted | agent_start + 可选 agent_session，无 agent_done |
| segmented | failed 段后追加 retry 或 continue 段，两个段消息可区分 |
| corrupt | 合法完整行后追加半行或非法 JSON |
| legacy | 只有旧事件和 exit_code，无 call_id/digest/status |

Factory 使用与 ADR 0036 相同的层级 call-id 和稳定 JSON 序列化，并提供独立 reader 断言 helper，验证消息只能从指定生命周期段提取。它不依赖产品 cache reader，避免用同一个实现同时制造和验证 fixture。

### 3. Backend session 替身

提供实现应用层 backend port 的 `SessionBackendFake`，按构造参数表达：

- `resume_session` / `durable_session_id` capability 组合；
- session ID 在开始时可见、仅完成时可见或永不提供；
- create/resume 成功、非零退出、异常和阻塞；
- create/resume 调用记录、输入 prompt、session ID 和顺序。

替身输出结构对照 Interface 0001 与缓存事件契约。自证必须证明不支持 durable session 时 continue 请求可被测试断言拒绝，以及 retry 不会误调用 resume。

### 4. 持久化与并发故障注入

提供以下无产品逻辑的可注入测试 double：

| double | 能力 |
|--------|------|
| `AtomicWriterFake` | 记录写入；在 publish 前、原子替换时或指定第 N 次写入抛错 |
| `RunLockFake` | 记录 acquire/release；模拟已占用和重复 acquire |
| `ProcessGroupFake` | 记录 TERM/KILL；模拟退出、忽略 TERM、PID 身份变化 |
| `EpochWriterFake` | 接受当前 epoch，拒绝旧 epoch 的迟到终态写入 |
| `ClockFake` | 提供固定时间和可控 grace period 推进 |

另提供仅在 pytest 子进程中使用的真实 process-group smoke helper：启动一个父进程和一个子进程，使用独立 session/process group，确保测试只向自己创建且已验证身份的进程组发信号。CI 不操作用户进程，不依赖 shell 工具。

### 5. Workflow 与 Intervention fixture

提供临时 workflow 工厂，生成确定性的：顺序调用、parallel 分支、state 循环、提前返回、不同 digest 路径和 `intervene()` 请求。Intervention factory 原子创建 pending/answered/closed 文件，支持 replay/continue resume_mode、schema 校验样本和重复回答样本。

Factory 只生成输入文件和 callable，不实现运行时行为。时间、随机数和外部读取通过显式参数注入，测试不得依赖真实墙钟或不设 seed 的随机值。

### 6. AC-020..022 manifest

在现有 manifest 机制上增加独立的 recovery manifest 与映射，覆盖 AC-020..022 的每个 N/B/E/F 场景。每项至少包含：

- 完整 ac_id、fixture、action、assertion；
- unit/integration/http/ui/process target；
- endpoint、HTTP status/error code 或 CLI exit expectation；
- retry/continue、cache/session/process/intervention 的关键断言标签；
- TEST_INFRA 阶段使用 `planned::` node，DEVELOP 严格模式拒绝 planned node。

静态检查器必须拒绝缺失/重复 AC、未知 error code、旧 `/resume` Web endpoint、`stopped` 可恢复、continue 静默降级、缺少 target 和空断言。现有 AC-014..019 manifest 保持可运行；被 AC-0011 替代的旧场景由 checker 明确排除，不删除历史记录。

### 7. 契约 schema 与前端 mock

增加 v13 RunSummary、AgentCallSummary、InterventionSummary、Backend capability 和新错误码的 schema fixture。为了保持 TEST_INFRA 绿色，新增 v13 schema 与现有产品 schema 并存；DEVELOP 切换产品契约测试后再删除 legacy schema。前端 mock 增加 waiting_input、cancelled、retry/continue availability，但不实现 UI。

### 8. 自证与门禁

基础设施必须通过正向 fixture，并通过反例证明能够拦截：

1. digest 漂移仍返回缓存；
2. segmented cache 串入失败段消息；
3. non-durable backend 被标记可 continue；
4. 旧 epoch 覆盖 cancelled；
5. TERM 被忽略后没有 KILL；
6. response 被第二次覆盖；
7. manifest 使用 `/resume` 或缺少 AC。

恢复专项基础设施测试加入现有 Python MR gate。浏览器只增加 mock 可加载冒烟，不新增业务截图基线。项目无付费测试资源，沙箱账号不适用。

## Alternatives

### 直接在业务测试中手写 JSONL 和进程 mock

短期文件更少，但多段缓存、session 能力和竞态 fixture 会在不同测试中漂移，难以证明反例确实被拒绝。

### 使用真实 Backend 做 continue 测试

能覆盖供应商行为，但依赖安装、认证、配额和非确定输出，不适合 CI。产品 backend 的手动兼容验证留给 SYSTEM_TEST。

### 引入数据库或 property-based testing 库

当前持久化仍是文件，确定性状态矩阵规模有限。标准库和参数化 pytest 足够；真实缺陷证明需要更广生成空间时再评估 property-based testing。

## Consequences

### Positive

- DEVELOP 可以直接组合稳定 fixture 编写 AC 测试，不重复搭建并发和故障场景。
- Backend 能力、JSONL 分段和进程终止都有独立反向自证。
- v13 schema 可先验证 mock，不迫使 TEST_INFRA 提前修改产品实现。
- 现有门禁、依赖和 Web 测试设施保持不变。

### Negative

- legacy 与 v13 schema 在一个迭代内并存，需要 DEVELOP 完成后清理迁移层。
- 真实 process-group smoke 需要 macOS/Linux 分支处理和严格进程清理。
- manifest 增加第二份 AC 源，需要通用 checker 避免复制解析逻辑。

## Architecture Boundary

```text
tests/recovery_support/             # fixture、fake、schema、manifest mapping
tests/infrastructure/               # 基建正反向自证
tests/system/recovery_cases.json    # AC-020..022 planned manifest
scripts/check-ac-manifest.py        # 支持显式 AC/manifest profile
```

产品代码不得依赖 `tests/recovery_support`。TEST_INFRA 不修改 runtime、AgentRunner、Run application service、Web endpoint 或前端业务组件。

## Verification

| 验证项 | 通过条件 | 证据位置 |
|--------|----------|----------|
| Cache factory | 六类 fixture 可生成，跨段错误提取被反例拦截 | 待 0042 Report 回填 |
| Backend fake | durable/non-durable、ID 时机和 create/resume 路由可断言 | 待 0042 Report 回填 |
| Fault injection | write/lock/epoch/process/time 五类 double 正反例通过 | 待 0042 Report 回填 |
| Process smoke | macOS/Linux 安全启动并清理自有进程组 | 待 0042 Report 回填 |
| AC manifest | AC-020..022 全覆盖，七类漂移反例被拒绝 | 待 0042 Report 回填 |
| Contract mock | v13 schema 正例通过、字段/枚举错误被拒绝 | 待 0042 Report 回填 |
| MR gate | 恢复专项基础设施测试纳入现有 Python job 且全绿 | 待 0042 Report 回填 |
