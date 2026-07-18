"""Capabilities — backend static capability declaration (domain value object)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    """Backend 的静态能力声明。值对象，领域层可安全依赖。

    Backend 在定义时确定其能力，不需要运行时计算。应用层查询后
    传入领域服务作为 marshalling 规则输入。
    """

    native_goal: bool = False
    structured_output: bool = False
    native_skills: bool = False