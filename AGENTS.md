## 一、项目简介

loopflow 是一个独立的 AI Agent 循环编排工具。以 Agent（完整 ReAct 实体）为基本单元构建循环工作流，支持 Agent 定义、循环编排、运行实例管理、崩溃恢复。纯 Python 实现，零外部依赖，复用 subagent-skills 的多后端适配层。

技术栈：Python 3.10+，标准库。

---

## 二、文档体系

### 文档类型

| 文档 | 用途 |
|------|------|
| 本文档（AGENTS.md） | 项目入口地图 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 编码/Commit/文档/测试规范 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录（Keep a Changelog） |
| [docs/vision.md](docs/vision.md) | 全局顶层愿景：业务目标、用户范围、长期理想形态（有 frontmatter） |
| [docs/spec/](docs/spec/) | Spec：需求规格。用户故事、模块划分、数据模型 |
| [docs/interface/](docs/interface/) | 接口定义：入参/出参/错误码。适用有 API 时 |
| [docs/ac/](docs/ac/) | 验收标准（AC）：正常/边界/异常/失败四场景。测试唯一权威依据 |
| [docs/adr/](docs/adr/) | 架构决策记录：技术选型、方案对比、取舍 |
| [docs/plans/](docs/plans/) | 执行容器：对应一个 Git 分支，内含多个最小执行单元（Plan + Report 成对） |
| [docs/README.md](docs/README.md) | 子目录索引 + **当前系统状态** |
| 各级 README.md | 该目录的索引和状态说明 |

### 文档目录结构

```
项目根目录
├── AGENTS.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── docs/
│   ├── README.md          # 索引 + 当前系统状态
│   ├── vision.md
│   ├── spec/
│   │   ├── README.md
│   │   └── 0001-template.md
│   ├── interface/
│   │   ├── README.md
│   │   └── 0001-template.md
│   ├── ac/
│   │   ├── README.md
│   │   └── 0001-xxx.md
│   ├── adr/
│   │   ├── README.md
│   │   └── 0001-xxx.md
│   └── plans/
│       ├── README.md
│       └── 0001-任务名/
│           ├── README.md
│           ├── 01-plan-xxx.md
│           ├── 01-report-xxx.md
│           └── artifacts/
├── src/
└── .github/workflows/
```

