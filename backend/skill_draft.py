"""用一段自然语言描述，让模型起草技能框架（草稿）。

对应设计的第一步与第二步：专家用自然语言说明自己的判断方式 → 模型泛化出初始框架 →
**再由专家逐项审核调整**（第三步才是专业性的来源，本模块不越俎代庖）。

设计要点：
  * 模型**不知道**专家没说的东西 —— 提示词明确要求：描述里没提到的部分留空，不许编造。
  * 模型输出必须经**归一化校验**才返回：只保留框架的已知部分，丢弃未知字段，类型不符即跳过。
  * 未配置模型时**明确报错**，不返回伪造草稿。
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from .model_service import ModelServiceError, _read as read_model_service, endpoint as model_endpoint

PARTS = ("inputs", "industry_map", "industry_weights", "thresholds", "signals",
         "combination_rules", "exception_rules", "signal_priority")

SYSTEM_PROMPT = """你在帮一位专业人士把他的判断方式整理成结构化的"技能框架"。
严格输出 JSON 对象，只包含下列键；**描述中没有提到的部分请留空或省略，绝对不要编造具体规则**：
{
  "framework_version": "V1",
  "inputs": [{"name": "字段名", "type": "string|number|enum", "values": ["枚举值"]}],
  "industry_map": {"行业": "类别"},
  "industry_weights": {"类别": {"维度": 0.0}},
  "thresholds": {"base": 数值, "adjustments": [{"condition": {"字段": "值"}, "delta": 数值, "reason": "理由"}]},
  "signals": [{"name": "信号名", "when": {"字段": {"op": "gt|gte|lt|lte|eq|neq|in|not_in|contains", "value": 值}}}],
  "combination_rules": [{"all_of": ["信号名"], "conclusion": "结论", "severity": "低|中|高|极高"}],
  "exception_rules": [{"condition": {"all_signals": ["信号名"]}, "override": {"kind": "reduce_weight|adjust_threshold|force_conclusion", "target": "字段", "factor": 0.5, "conclusion": "结论"}, "reason": "理由"}],
  "signal_priority": [{"signal": "信号名", "priority": 1}]
}
只输出 JSON，不要解释。"""


class DraftError(RuntimeError):
    pass


def _call_model(description: str) -> dict[str, Any]:
    """调用已配置的模型；失败抛 DraftError。测试会替换掉这个函数。"""
    try:
        config = read_model_service()
    except ModelServiceError as exc:
        raise DraftError(str(exc)) from exc
    base, model = config.get("base_url"), config.get("model")
    if not base or not model:
        raise DraftError("尚未配置模型服务，请先到「模型服务」填写服务地址与模型名称。")
    payload = json.dumps({
        "model": model, "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": description}],
    }).encode()
    headers = {"Content-Type": "application/json"}
    if config.get("api_key"):
        headers["Authorization"] = "Bearer " + config["api_key"]
    req = urllib.request.Request(model_endpoint(config), data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read(2_000_001))
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as exc:      # 网络/格式问题都要显式报出，不能静默给空框架
        raise DraftError(f"模型调用失败：{str(exc)[:200]}") from exc


def _norm_signals(raw: Any) -> list[dict[str, Any]]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        when = item.get("when")
        if not isinstance(when, dict):
            continue
        out.append({"name": str(item["name"]), "when": when})
    return out


def normalize(draft: Any) -> dict[str, Any]:
    """只保留框架的已知部分；类型不符的字段直接丢弃（宁缺毋滥）。"""
    if not isinstance(draft, dict):
        raise DraftError("模型返回的不是对象")
    fw: dict[str, Any] = {"framework_version": str(draft.get("framework_version") or "V1"),
                          "drafted": True}
    if isinstance(draft.get("inputs"), list):
        fw["inputs"] = [i for i in draft["inputs"] if isinstance(i, dict) and i.get("name")]
    if isinstance(draft.get("industry_map"), dict):
        fw["industry_map"] = {str(k): str(v) for k, v in draft["industry_map"].items()}
    if isinstance(draft.get("industry_weights"), dict):
        fw["industry_weights"] = {str(k): {str(d): w for d, w in v.items() if isinstance(w, (int, float))}
                                  for k, v in draft["industry_weights"].items() if isinstance(v, dict)}
    th = draft.get("thresholds")
    if isinstance(th, dict):
        base = th.get("base")
        fw["thresholds"] = {"base": float(base) if isinstance(base, (int, float)) else 1.0,
                            "adjustments": [a for a in (th.get("adjustments") or []) if isinstance(a, dict)]}
    fw["signals"] = _norm_signals(draft.get("signals"))
    fw["combination_rules"] = [r for r in (draft.get("combination_rules") or [])
                               if isinstance(r, dict) and isinstance(r.get("all_of"), list) and r.get("conclusion")]
    fw["exception_rules"] = [r for r in (draft.get("exception_rules") or [])
                             if isinstance(r, dict) and isinstance(r.get("override"), dict)]
    fw["signal_priority"] = [p for p in (draft.get("signal_priority") or [])
                             if isinstance(p, dict) and p.get("signal")]
    fw["adjustment_log"] = []      # 调整记录留空，等专家在界面上逐项调整时写入
    return fw


def draft(description: str, *, caller=_call_model) -> dict[str, Any]:
    text = (description or "").strip()
    if len(text) < 10:
        raise DraftError("描述太短，请至少写一两句话说明你的判断方式。")
    fw = normalize(caller(text))
    return {"framework": fw,
            "notes": "这是模型草稿：描述里没提到的部分保持为空，需要你逐项调整后才是你的判断。"}
