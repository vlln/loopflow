# 0109 — Web manifest strict 基建修复

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Web manifest strict 基建修复](01-plan-web-manifest-strict.md) | 待完成后创建 | pending |

## 分支

`test/0109-web-manifest-strict`（从 `develop` 拉出）

## 范围

- 为 Web AC-014~019 的非 superseded 场景映射真实测试节点
- strict checker 校验提交节点真实存在，并拒绝 planned 或伪造节点
- 重新生成 Web manifest，执行增量 TEST_INFRA 正反向自证
