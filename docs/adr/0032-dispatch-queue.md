---
title: ADR 0032 — 调度机制：dispatch + queue + resource lock
description: 以 pull-based dispatch、文件队列、资源锁实现 loop 调度，不做常驻 daemon
type: adr
status: accepted
created: 2026-07-18T00:00:00Z
---

# ADR 0032: 调度机制 — dispatch + queue + resource lock

## Context

loopflow 已实现编排（workflow.py + agent/parallel/pipeline/phase）和运行实例管理（run/resume/status/list/stop），但缺失调度层。当前 loop 只能通过 `loop run <name>` 手动触发，没有自动触发、任务排队、资源互斥的能力。

引入调度机制需要回答三个问题：
1. 触发信号如何到达 loopflow？
2. 多个任务如何排队？
3. 同一资源上的并发如何互斥？

## Decision

采用最小化 pull-based 调度，不引入常驻 daemon：

### 1. 触发声明

Loop 在 `loop.md` 的 frontmatter 中声明可被什么触发（见 ADR 0031）。Dispatcher 不关心 trigger 的业务含义，只读取声明并决定何时启动 loop。

### 2. 队列

`~/.loopflow/queue/` 目录，每个待执行任务是一个 JSON 文件：

```json
{
    "loop": "fix-issue",
    "args": {"issue_path": "issues/0007.md", "repo": "/path/to/project"},
    "resources": {"repo": "/path/to/project"},
    "priority": 5,
    "created": "2026-07-18T10:00:00Z"
}
```

入队路径：
- `loop enqueue <name> --args '<json>'` → 写入队列
- `loop run <name> --args '<json>'` → 直接执行，不经过队列（保持手动触发语义）

### 3. Dispatch

新命令 `loop dispatch`——幂等、可被 cron/launchd 重复调用：

```
loop dispatch 逻辑:
  1. 扫描 ~/.loopflow/queue/*.json
  2. 按 priority 降序 → created 升序排列
  3. 对每个任务:
     a. 检查资源锁（同一 resource 不能同时跑两个 loop）
     b. 加锁成功 → 从队列删除 → 执行 loop run → 解锁
     c. 加锁失败 → 跳过，留队列
```

关键原则：dispatch 里没有任何智能。优先级排序是全部策略。

### 4. 资源锁

复用 `lock.py` 的文件锁模式，粒度从 "session" 改为 "resource"：

- 锁文件路径：`~/.loopflow/locks/<resource-type>-<sha256(resource-value)>.lock`
- 在 dispatch 时对任务声明的所有 resource 加锁，全部成功才执行
- 锁有 TTL（30 分钟过时），防止崩溃导致死锁
- loop 执行完成后释放锁

### 5. 外部调度器

`loop dispatch` 是一个幂等的 CLI 命令，loopflow 本身不负责周期调用它。用户选择外部调度器来驱动：

```
外部调度器（cron / launchd / systemd / GitHub Actions）
    │
    └── 每 N 分钟调用: loop dispatch
                          │
                          ├── 扫描 ~/.loopflow/queue/
                          ├── 按优先级取任务
                          ├── 加资源锁
                          └── loop run <name>
```

**设计边界：loopflow 不拥有调度节奏。** 调度器的选择、安装、启停是运维操作，不属于 loopflow 的机制。loopflow 只提供 `loop dispatch` 这个命令——它总是安全的（幂等），可以随时被外部定时器调用。

#### macOS 推荐：launchd

```xml
<!-- ~/Library/LaunchAgents/com.loopflow.dispatch.plist -->
<plist>
<dict>
    <key>Label</key>
    <string>com.loopflow.dispatch</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/loop</string>
        <string>dispatch</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>        <!-- 每 5 分钟 -->
    <key>RunAtLoad</key>
    <true/>                       <!-- 启动时执行一次，睡眠唤醒后补跑 -->
</dict>
</plist>
```

激活：`launchctl load ~/Library/LaunchAgents/com.loopflow.dispatch.plist`

#### 其他平台

| 平台 | 调度器 | 配置方式 |
|------|--------|---------|
| Linux | `cron` | `*/5 * * * * loop dispatch` |
| Linux | `systemd timer` | `OnUnitActiveSec=300` + 配套 `.service` |
| GitHub Actions | `schedule` | `cron: "*/5 * * * *"` 触发 workflow |

#### 为什么 launchd 优于 cron（macOS）

- **秒级精度**：`StartInterval` 单位是秒，cron 最小 1 分钟
- **睡眠唤醒**：`RunAtLoad` 让睡眠唤醒后自动补跑，cron 错过就错过了
- **无需额外授权**：macOS 首次使用 cron 需要全磁盘访问权限弹窗

### 架构位置

所有新增模块在基础设施层：

```
src/loopflow/infrastructure/
├── dispatch.py       # dispatch 逻辑（扫描队列、排序、加锁、执行）
├── queue.py          # 队列读写（enqueue、dequeue、list）
└── lock.py           # 已有——扩展为支持 resource 粒度锁
```

CLI 新命令在展示层：

```
src/loopflow/presentation/cli.py  # + loop dispatch / loop enqueue
```

## Consequences

### 正面

- Pull 模型零运行时开销——无 daemon，崩溃自动恢复，和现有 CLI 模型一致
- 文件即队列——无外部依赖，git 可审计
- 资源锁复用已有 lock.py 模式——代码量最小
- dispatch 不 import workflow.py——只读 loop.md frontmatter 和 queue 文件

### 负面

- 延迟受 cron 粒度限制（最小 1 分钟），不适合亚秒级响应
- 文件队列在高并发下有竞争风险——但第一版仅串行，无此问题
- 未来如果需求增长（优先级抢占、分布式调度），文件队列可能需要替换为专用队列

### 不做的

- 不做常驻 daemon——pull 模型足够
- 不做 webhook 触发——留到 `loop serve` 命令
- 不做优先级抢占——只按 priority 排序，不中断正在运行的 loop
- 不做分布式调度——单机场景，loop 和 loopflow 在同一台机器

## 验证

本 ADR 不涉及技术选型，不需要 spike 验证。机制有效性通过后续 DEVELOP 阶段的集成测试验证。