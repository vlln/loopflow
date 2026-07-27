"""测试侧参考实现：ADR-0044 失败分类来源优先级。

结构化上报（agent_done payload 的 error_category）优先；
未上报时 stderr 模式匹配兜底；两者皆无按 unknown（策略上视同 task）。

注意：模式表是生产 runner `_TRANSIENT_PATTERNS` 的拷贝——本模块会被
scripts/check-ac-manifest.py 以裸 python3 导入（无 loopflow 包可导入），
不能在模块级依赖生产代码。tests/infrastructure/test_failure_injection_support.py
有漂移守卫测试断言两份模式表一致。
"""

from __future__ import annotations

from typing import Any

# 与 loopflow.application.runner._TRANSIENT_PATTERNS 保持一致的拷贝（漂移有自证守卫）
TRANSIENT_PATTERNS: list[tuple[str, str]] = [
    ("connection_error", "connection_error"),
    ("terminated", "terminated"),
    ("timeout", "timeout"),
    ("rate_limit", "rate_limit"),
    ("rate limited", "rate_limit"),
    ("timed out", "timeout"),
]

ERROR_CATEGORIES = ("auth", "quota", "transient", "task", "unknown")


def resolve_error_category(payload: dict[str, Any]) -> str:
    """按 ADR-0044 §1 优先级解析 agent_done payload 的失败分类。"""
    category = payload.get("error_category")
    if category is not None:
        if category not in ERROR_CATEGORIES:
            raise ValueError(f"unknown error category: {category}")
        return category
    stderr_lower = str(payload.get("stderr") or "").lower()
    if any(pattern in stderr_lower for pattern, _ in TRANSIENT_PATTERNS):
        return "transient"
    return "unknown"
