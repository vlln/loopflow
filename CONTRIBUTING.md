<!-- 编码规范。项目自定义。Agent 在 DEVELOP 阶段读取。 -->

---

## 一、开发环境

Python 3.10+。WebUI 开发和构建使用 Node.js 22；用户运行已构建 wheel 时不需要 Node.js。

```bash
uv sync --all-extras
cd web && npm ci
```

**构建/配置入口：**

| 文件 | 用途 |
|------|------|
| `src/loopflow/` | 主程序入口 |
| `tests/` | 测试目录 |
| `web/` | React/TypeScript 源码、组件测试和 Playwright 测试 |
| `scripts/mr-gate.sh` | 本地 MR 组合门禁 |
| `scripts/submission-gate.py` | Plan/Report/AC/coverage 提测门禁 |

---

## 二、代码风格

- 格式化：遵循 PEP 8
- 命名：
  - 文件：snake_case（Python 模块）
  - 变量/函数：snake_case
  - 类/接口：PascalCase
  - 常量：UPPER_SNAKE_CASE

---

## 三、Commit 规则

### 格式

```
<type>(<scope>): <简短描述>
```

| type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档变更（必须独立提交，不与代码混合） |
| refactor | 重构 |
| test | 测试相关 |
| chore | 构建/工具/依赖 |

### devloop 约定

- 文档变更和代码变更永远分开 commit
- 阶段推进伴随独立 commit，前缀 `docs(state):`
- 文档 commit 格式：`docs(<scope>): <简述>`

---

## 四、分支策略

遵循 Gitflow：

```
main     ─────●──────────●────→  (tag: v1.0, v1.1)
              ↑          ↑
release  ──── v1.0 ───── v1.1
              ↑          ↑
develop  ────●──●──●──●──●──→  (持续集成)
              ↑  ↑  ↑
             ci/ feat/ fix/
```

| 分支 | 用途 | 从哪拉 | 合并到哪 |
|------|------|--------|---------|
| `main` | 仅含 release 节点，始终可部署 | — | — |
| `develop` | 持续集成分支 | `main` | — |
| `feat/*` `refactor/*` `perf/*` | 功能开发 | `develop` | `develop` |
| `ci/*` `test/*` `build/*` | 基建搭建 | `develop` | `develop` |
| `fix/*` | 集成修复 | `develop` | `develop` |
| `spike/*` | ADR 技术验证 | `develop` | 不合并（保留） |
| `release/*` | 版本发布 | `develop` | `main` + `develop` |
| `hotfix/*` | 生产热修复 | `main` | `main` + `develop` |

一个执行容器 = 一个分支，编号与执行容器对应。分支类型与 commit type 一致。

Merge 策略：squash merge（保持 develop 历史线性）。

---

## 五、测试

### 测试命令

<!-- 根据项目实际配置 -->

| 命令 | 用途 |
|------|------|
| `uv run pytest tests/unit/ -v` | 单元测试 |
| `uv run pytest tests/integration/ -v` | 集成测试 |
| `uv run pytest tests/infrastructure/ -v` | 测试基础设施自证 |
| `uv run pytest tests/ -v --cov=src/loopflow` | Python 全量测试 + 项目覆盖率门禁 |
| `cd web && npm run test:coverage` | 前端组件测试 + 80% 四维覆盖率 |
| `cd web && npm run test:browser` | Chromium 三视口系统/视觉测试 |
| `python3 scripts/check-ac-manifest.py --allow-planned` | TEST_INFRA 检查 60 个计划场景 |
| `python3 scripts/check-ac-manifest.py` | DEVELOP/SYSTEM_TEST 严格检查真实测试节点 |
| `./scripts/verify-coverage.sh` | 已知 2 分支覆盖率准确性自证 |
| `./scripts/wheel-smoke.sh` | 构建、隔离安装并读取 wheel 静态资产 |
| `./scripts/mr-gate.sh` | 本地执行 MR 全门禁 |

### 测试目录

| 层级 | 目录路径 | 说明 |
|------|---------|------|
| 单元测试 | `tests/unit/` | 纯函数/类测试，无外部依赖 |
| 集成测试 | `tests/integration/` | 模块间协作，需 mock backend |
| 契约/基建 | `tests/infrastructure/`、`tests/web_support/` | Interface fixture、HTTP/SSE helper、门禁自证 |
| 系统测试 | `tests/system/`、`web/tests/` | API 全链路、真实 Chromium、截图与 trace |

覆盖率机器产物写入 `.artifacts/` 或 CI artifact，不以 Report 中手写数字替代。视觉基线只在明确审查后更新，CI 不自动覆盖。

---

## 六、PR 流程

1. 从 `develop` 创建与执行容器一致的分支。
2. 先运行 `./scripts/mr-gate.sh`；任一 Python、前端、浏览器、audit 或 wheel 检查失败均不得合并。
3. GitHub 的 `python`、`frontend`、`browser`、`wheel` checks 必须配置为 `develop` 的 required checks。
4. DEVELOP Plan 在 `# Acceptance` 显式列出负责的完整 AC 场景 ID；Report 逐项记录 `[PASS]` 与 commit。
5. 使用 `scripts/submission-gate.py` 验证 Plan/Report、AC、JUnit 和机器 coverage 证据后才可进入 SYSTEM_TEST。

---

## 七、行为准则

<!-- 项目行为准则，可引用 Contributor Covenant -->

---

## 八、许可证

MIT
