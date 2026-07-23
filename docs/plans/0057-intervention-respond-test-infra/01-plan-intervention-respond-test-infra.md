---
title: Intervention Respond Test Infrastructure Plan
description: 固化 respond 前置条件错误的 AC、接口契约、application contract tests 与 recovery manifest
type: plan
status: done
created: 2026-07-23T16:30:00Z
---

# Goal

让 `POST /runs/{run_id}/interventions/{request_id}/response` 的 4 个框架层错误边界都有冻结 AC、接口说明、机器测试节点和 manifest 证据。

# Acceptance

1. AC-022 覆盖 schema validation、request not found、already answered、invalid run transition 四类 respond 前置条件失败。
2. Interface 0001 明确这四类错误的无副作用边界，且不引入 intervention 特殊恢复失败状态。
3. Application contract tests 分别验证：
   - 422 `validation_failed`：response 不落盘，不启动 executor。
   - 404 `intervention_not_found`：Run/request 不变，不启动 executor。
   - 409 `intervention_already_answered`：response 不覆盖，不重复启动 executor。
   - 409 `invalid_run_transition`：pending request 不变，不启动 executor。
4. Recovery manifest 覆盖新增 AC 场景，并拒绝错误码与 HTTP status 漂移。
5. 运行相关测试和 manifest checker 通过，不修改 `src/` 产品实现。

# Steps

1. 更新 AC-022 和 Interface 0001，补 respond command 前置条件失败契约。
2. 新增/拆分 `tests/unit/test_web_application.py` 的 respond 边界测试。
3. 更新 `tests/recovery_support/manifest.py` 的 target、expectation、test_node 映射。
4. 重新生成 `tests/system/recovery_cases.json`。
5. 运行专项 pytest、recovery manifest checker 和 `git diff --check`。
6. 写 Report，标记容器 done，并提交。

# Exit

本容器 done 后进入 DEVELOP，依据 0056/0057 调整 WebUI 层级和用户回答问题交互。
