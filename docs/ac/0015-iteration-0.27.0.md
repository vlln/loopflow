---
title: 0.27.0 用户输入与二进制预览 AC
description: 验收图片/PDF raw 预览、Run 级 append_prompt 和 New Run declared args 契约符合性
type: ac
status: active
created: 2026-07-29T11:24:49Z
---

# AC-033: 图片与 PDF raw 预览

对应 Spec v18 US-027、BR-046 和 BL-051。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-033-N-1 | Run 工作目录依次含小于 50 MiB 的 png/jpg/jpeg/gif/svg/webp/bmp/ico fixture | 对 8 种扩展名参数化请求 preview，再 GET raw_url | 每组 preview 返回 encoding=raw、content=null、size/raw_url/read_only；raw bytes 完全一致，Content-Type 分别为 image/png、image/jpeg、image/jpeg、image/gif、image/svg+xml、image/webp、image/bmp、image/x-icon，Cache-Control no-store | 自动化 |
| AC-033-N-2 | Loop 根目录含小于 50 MiB 的 `report.pdf` | 请求 Loop preview 和 raw_url，并在 WebUI 打开 | raw 返回 application/pdf；WebUI 用只读 PDF viewer 展示，不把 bytes 放进文本 `<pre>` | 自动化 + 浏览器 |
| AC-033-N-3 | Run 工作目录含 `photo.jpg` | 从 File changes 点击文件 | WebUI 显示受视口约束的图片，关闭后释放预览视图；文件树布局不跳动 | 自动化 + 浏览器 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-033-B-1 | 允许格式文件大小恰为 50 MiB | 请求 raw | 返回 200 和完整 bytes；大于 50 MiB 才拒绝 | 自动化 |
| AC-033-B-2 | `.bin` 含二进制内容 | 请求 preview | 返回 422 file_not_previewable；不返回 content/raw_url | 自动化 |
| AC-033-B-3 | `notes.txt` 小于 1 MiB | 请求 preview | 保持既有 UTF-8 文本 JSON 响应，不出现 encoding=raw/raw_url | 自动化 |
| AC-033-B-4 | `large.txt` 是超过 1 MiB 的 UTF-8 文本 | 请求 preview | 返回 422 file_not_previewable；不返回 content/raw_url | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-033-E-1 | raw path 为 `../secret.pdf` 或符号链接解析后越界 | 请求 Run/Loop raw | 返回 403 path_forbidden；不读取或返回目标 bytes | 自动化 |
| AC-033-E-2 | preview 后文件已被删除 | 请求 raw_url | 返回 404 file_not_found；WebUI 显示读取失败状态，不保留空白 iframe | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-033-F-1 | 允许扩展名文件大于 50 MiB | 请求 preview 或 raw | 返回 422 file_not_previewable；响应不含部分 bytes | 自动化 |
| AC-033-F-2 | 测试替换 raw reader，使路径 resolve/size 校验通过后 `Path.read_bytes()` 抛 PermissionError | 请求 raw，随后 GET /runs | raw 返回 500 file_read_failed 且不发送 200 header 或部分内容；GET /runs 返回 200 和合法 Run 列表 JSON | 自动化（reader failure injection） |

---

# AC-034: Run 级追加 prompt

对应 Spec v18 US-039、BR-065 和 BL-052。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-034-N-1 | workflow 顺序调用两个 Agent | `loopflow run demo --append-prompt "只读取，不修改"` | 两次实际动态 prompt 末尾各出现一次独立 run-append-prompt 段；run.json 冻结原值；不进入 system prompt | 自动化 |
| AC-034-N-2 | WebUI New Run 填写 Append prompt | 启动 Run | POST body 含 append_prompt；API 创建 201，execution_options 持久化该值，Agent 收到相同附加段 | 自动化 + 浏览器 |
| AC-034-N-3 | 使用 `run --agent reader --prompt "task" --append-prompt "constraint"` | 执行 | task 保持主动态 prompt，constraint 作为独立附加段出现一次；CLI 退出码 0 且 Run status=done | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-034-B-1 | append_prompt 缺省或为空字符串 | 创建 Run | 等价于未提供，不注入空标签，execution_options 不必保存空值 | 自动化 |
| AC-034-B-2 | append_prompt UTF-8 编码后恰为 65536 bytes | 通过 CLI 和 API 分别创建 Run | 两条入口均接受；多字节字符按编码后 bytes 计数 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-034-E-1 | append_prompt UTF-8 编码后为 65537 bytes | 执行 `loopflow run demo --append-prompt <value>` | CLI 明确输出 append_prompt 超过 64 KiB，退出码非 0；不创建 Run、不调用 backend | 自动化 |
| AC-034-E-2 | 已有 Run 冻结 append_prompt=A | POST `/runs/{id}/recover`，body 含 `mode:"retry", append_prompt:"B"` | 返回 422 validation_failed，details.fields 含 append_prompt；原 execution_options 保持 A，不启动恢复 worker | 自动化 |
| AC-034-E-3 | append_prompt UTF-8 编码后为 65537 bytes | POST /runs，body 含该值 | 返回 422 validation_failed，details.field=append_prompt；不创建 Run、不调用 backend | 自动化 |
| AC-034-E-4 | WebUI Append prompt 输入 65537 bytes | 点击 Start | 输入下方显示 `Append prompt must be 64 KiB or less`；Start 保持可见但请求不发送，POST /runs 调用数为 0 | 自动化 + 浏览器 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-034-F-1 | 同一 Call 首次运行冻结 append_prompt=A，恢复时落盘值被外部篡改为 B | recover | input_digest 不匹配并以 replay_diverged 失败；不命中 A 的成功缓存 | 自动化 |
| AC-034-F-2 | append_prompt 文本包含“忽略 system prompt”等指令 | 捕获 backend 调用参数 | 文本只出现在用户动态 prompt 的 run-append-prompt 段，不进入/覆盖 system 参数 | 自动化 |

---

# AC-035: New Run declared args 契约符合性

对应既有 Spec US-028、BR-047、AC-014-N-10/B-5 和 BL-054。本 AC 验证当前实现/部署是否符合既有 active 契约，不定义第二套参数格式。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-035-N-1 | Loop A 的 loop.md 顶层 args 声明 topic 默认 rna、count 无默认且 required | 打开 New Run 并选择 A | Arguments 行为 topic=rna、count=空；required 有可见标记；提交时空 count 不进入 args | 自动化 + 浏览器 |
| AC-035-N-2 | Loop A/B 声明不同 args | 在已打开对话框中从 A 切换到 B | 键值行按 B 的声明重建，不残留 A 的 key/default | 自动化 + 浏览器 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-035-B-1 | Loop 无 args 声明 | 选择该 Loop | 编辑器显示单个空白起始行，不伪造参数名 | 自动化 |
| AC-035-B-2 | 参数声明 default 为 false、0、空字符串或对象 | 打开对话框 | false/0/对象以可回解析形式预填；空字符串保持空且提交时按既有空值忽略规则处理 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-035-E-1 | args 含非对象、空 name 和一个合法条目 | 查询 Loop 并打开 New Run | API 静默忽略非法条目并保留合法条目；UI 只预填合法 key，不崩溃 | 自动化 |
| AC-035-E-2 | loop.md 存在但 args 不是数组 | 查询 Loop | declared_args 返回空数组；不得回退读取 workflow.py meta.args | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-035-F-1 | fetch `GET /api/v1/loops` 被注入 network rejection，页面此前缓存过 Loop A declared_args | 打开 New Run | 对话框显示 `Unable to load loops`，Loop selector 与 Start 禁用，Arguments 不显示缓存的 A 参数；POST /runs 调用数为 0 | 自动化 |
