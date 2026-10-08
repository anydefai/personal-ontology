"""判定框架 —— 现在只是一层转发（保留原有函数名，调用方无需改动）。

拆分之后：
  · 引擎（接口 + 注册表 + 调度）在 backend/engine.py，其中不含任何算法
  · 具体算法住在 backend/models/scorecard_v1.py（证据累积 → 分档）
  · 新增一种判定方式 = 加一个 backend/models/*.py + 在 engine.MODELS 注册一行
判定包只新增 model 与 model_version 两项，其余字段与拆分前完全一致。
"""
from __future__ import annotations

from typing import Any

from backend import engine
from backend.models.scorecard_v1 import (  # noqa: F401 - 原样导出，保持向后兼容
    # 模块级常量也必须导出：api.py 直接用 skill_framework.TIERS（我第一版漏了，测试当场抓到）
    OPS,
    SEVERITY_ORDER,
    TIERS,
    ALWAYS,
    CALLER_KEYS,
    compute_threshold,
    match_conditions,
    eval_signals,
    content_fingerprint,
    apply_tier,
    package_identity,
    for_caller,
    _exception_effect,
)


def judge(framework: dict[str, Any], data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """与拆分前行为一致：只是改由引擎按切片声明的模型来算。"""
    return engine.judge(framework, data, **kwargs)


def model_catalog() -> list[dict[str, Any]]:
    """给界面与调用说明用：有哪些判定模型、各自适用什么。"""
    return engine.model_catalog()


def validate(framework: dict[str, Any]) -> list[dict[str, Any]]:
    """模型的静默风险提示（维度对不上、缺行业归类等）。"""
    return engine.validate(framework)
