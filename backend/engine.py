"""判定引擎：接口 + 注册表 + 调度。**不含任何具体算法。**

设计见 docs/12-judgment-model-architecture.md：
  · 引擎负责取模型、校验、调度，并在判定包上盖 model 与 model_version
  · 算法住在 backend/models/*.py，每个模型自带输入契约、校验、输出契约与可解释性
  · 新增一种判定方式 = 加一个模型文件 + 在 MODELS 里注册一行，不改本文件

三条硬约束（任何模型都不得违反）：
  ① 可解释：必须能给出 reasoning_path
  ② 无副作用：不联网、不写盘、不读全局状态、不用 eval/exec、不用随机与当前时间
  ③ 可复现：model + model_version + 输入 + 框架 → 必然同一判定包；语义变更必须升 version
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.models.requirements_v1 import REQUIREMENTS_V1
from backend.models.scorecard_v1 import SCORECARD_V1


@runtime_checkable
class JudgmentModel(Protocol):
    """一个判定模型必须提供的东西（引擎只依赖这些）。"""

    id: str
    version: str
    label_zh: str
    label_en: str
    applicable: str
    not_applicable: list[str]

    def input_contract(self) -> dict: ...
    def validate(self, framework: dict) -> list[dict]: ...
    def judge(self, framework: dict, data: dict, **kwargs: Any) -> dict: ...
    def output_contract(self) -> dict: ...
    def reasoning(self, package: dict) -> list[dict]: ...


# 注册表：新增模型只在这里加一行
MODELS: dict[str, JudgmentModel] = {
    SCORECARD_V1.id: SCORECARD_V1,
    REQUIREMENTS_V1.id: REQUIREMENTS_V1,
}
DEFAULT_MODEL = SCORECARD_V1.id


def get_model(framework: dict | None) -> JudgmentModel:
    """切片自己声明用哪个模型；没声明就用默认（老切片行为不变）。"""
    name = str((framework or {}).get("model") or "").strip()
    return MODELS.get(name) or MODELS[DEFAULT_MODEL]


def model_catalog() -> list[dict]:
    """给界面与调用说明用：有哪些模型、各自适用什么。"""
    return [{"id": m.id, "version": m.version, "label_zh": m.label_zh, "label_en": m.label_en,
             "applicable": m.applicable, "not_applicable": list(m.not_applicable),
             "input_contract": m.input_contract(), "output_contract": m.output_contract()}
            for m in MODELS.values()]


def validate(framework: dict) -> list[dict]:
    return get_model(framework).validate(framework or {})


def judge(framework: dict, data: dict, **kwargs: Any) -> dict:
    """调度：取模型 → 算 → 盖上 model 与 model_version（判定包只新增这两项）。"""
    model = get_model(framework)
    package = model.judge(framework or {}, data or {}, **kwargs)
    if isinstance(package, dict):
        package["model"] = model.id
        package["model_version"] = model.version
    return package
