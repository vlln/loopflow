---
title: Agent Skill Support — prompt injection as universal fallback
description: requires.skills 从透传后端 flag 重构为 prompt 注入 + 原生支持双轨策略，所有后端通用
type: adr
status: accepted
created: 2026-07-10T10:00:00Z
---

# ADR 0015: Agent Skill Support

## 动机

当前 `requires.skills` 继承自 subagent-skills，设计为透传给后端 CLI flag（`--skill`、`--skills-dir`）。实际上：

- 8 个后端中仅 kimi（`--skills-dir`）和 pi（`--skill`）支持，其余 6 个静默丢弃
- 没有任何 workflow 在使用 `requires.skills`
- bio-reproducer 的 reader agent 需要 `paperutils`，但写在 agent body 中，而非声明在 `requires.skills`

skill 本质上是注入到 system prompt 的指令。loopflow 应该采用 prompt 注入作为通用策略，后端原生支持作为优先策略。

## 决策

### 1. Skill 声明格式

```yaml
requires:
  skills:
    - git-check
    - security-scan
```

仅 skill 名称。等价写法：

```yaml
requires:
  skills: [git-check, security-scan]
```

### 2. Skill 查找路径

按优先级从以下目录查找（先找到的生效）：

1. `~/.agents/skills/` — 通用规范目录
2. `~/.loopflow/skills/` — loopflow 自有目录

每个 skill 是一个子目录，包含 `SKILL.md`（skill 定义文件）。查找时按名称匹配目录名。

### 3. Skill 定义格式

每个 skill 目录下的 `SKILL.md` 使用 YAML frontmatter：

```yaml
---
name: git-check
description: Check git repository status and branches
path: /path/to/custom/location    # 可选，覆盖默认路径
source: github:owner/repo@ref     # 可选，安装源（未来功能）
---
# Skill body...
```

`path` 和 `source` 为可选字段：
- `path`：指向本机自定义路径，覆盖默认查找路径
- `source`：符合 skill 安装方式的源地址（如 GitHub），当前阶段仅记录，不自动下载

### 4. 双轨策略

```
agent() 调用
  ├── 后端支持原生 skill 参数？
  │     ├── 是 → 优先使用原生参数（保持现有行为：kimi --skills-dir, pi --skill）
  │     └── 否 → loopflow 读取 skill 描述，注入到 system prompt
  └── ACP 后端的 mcps 同理（保持现有行为）
```

**prompt 注入格式**（参考 kimi-code）：

```
## Available skills

Skills are grouped by scope so you can tell where each came from.
DISREGARD any earlier skill listings. Current available skills:

- git-check: Check git repository status and branches
  Path: /Users/xxx/.loopflow/skills/git-check/SKILL.md
- security-scan: Scan code for security vulnerabilities
  Path: /Users/xxx/.agents/skills/security-scan/SKILL.md
```

只注入 skill 名称、描述和路径。Agent 需要时自行读取 skill 文件内容。不注入完整 skill body，避免 system prompt 膨胀。

### 5. 当前不做的事

- **不自动下载**：`source` 字段仅记录，loopflow 不负责 `git clone` 或安装
- **不校验可用性**：声明了 skill 但目录不存在时，注入时标记为 `[not found]`，不阻塞运行
- **不锁定版本**：skill 名称不含版本号，版本管理留给未来

## 影响

- `runtime.py`：`agent()` 调用前，根据 `requires.skills` 查找 skill 目录，构建 prompt 注入段
- `agent.py`：`AgentRequires.skills` 字段保持不变（已是 `list[str]`）
- 现有后端：kimi/pi 的原生 skill flag 行为保持不变（优先策略）
- Workflow 作者：可以在 agent.md 中声明 `requires.skills`，所有后端通用

## 替代方案

**方案 B：纯 prompt 注入，放弃原生 flag。**
- 优点：统一行为，代码更简单
- 缺点：后端原生 skill 机制可能有更好的上下文管理（如 skill 内容不占 token）
- 决策：保留原生 flag 优先，prompt 注入作为 fallback。未来如果后端原生支持更成熟，可以逐步淘汰 prompt 注入

**方案 C：注入完整 skill body。**
- 优点：agent 不需要额外读取文件
- 缺点：system prompt 膨胀，skill 内容可能很长
- 决策：不采用。kimi-code 的"只注入目录"模式已被验证有效