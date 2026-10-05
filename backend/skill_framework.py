"""技能框架执行器：把专业判断框架应用到一组输入数据上，产出可追溯的判定包。

设计原则（与项目既有纪律一致）：
  * **声明式，不可执行任意代码**：条件只用注册过的操作符；派生只允许声明式引用（如"与阈值比较"）。
  * **未知一律不放行**：操作符未注册、字段缺失、类型不符 → 该条不匹配，并在结果里说明原因。
  * **过程可回溯**：返回 reasoning_path（分步明细）与 evidence（逐项依据），供调用方核对。

框架结构（对应「张律师并购估值」那套逻辑）：
  inputs            输入字段定义（名称/类型/枚举取值）
  industry_map      行业 → 类别（用于第 1 步分类）
  industry_weights  类别 → 权重组（技术/团队/财务/市场…）
  thresholds        base + 条件调整（第 2 步）
  signals           具名布尔信号（可引用"动态阈值"做比较）
  combination_rules 多信号 AND → 结论 + severity（第 3 步）
  exception_rules   条件 → override（降权 / 调阈值 / 直接判定）（第 4 步）
  signal_priority   信号重要性顺序（第 5 步）
"""
from __future__ import annotations

from typing import Any

OPS = {
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
}
SEVERITY_ORDER = {"低": 0, "中": 1, "高": 2, "极高": 3}


class FrameworkError(Exception):
    pass


def _resolve(ref: Any, data: dict[str, Any], threshold: float | None) -> tuple[Any, str | None]:
    """把条件右侧解析成值。支持：
       {"ref": 字段}                       取输入字段
       {"ref": 字段, "times": "threshold"} 取输入字段 × 动态阈值（声明式派生，不允许任意公式）
    """
    if not isinstance(ref, dict):
        return ref, None
    if "ref" not in ref:
        return None, "右侧引用缺少 ref"
    field = ref["ref"]
    if field not in data:
        return None, f"缺少字段 {field}"
    try:
        value = float(data[field])
    except (TypeError, ValueError):
        return None, f"字段 {field} 不是数值"
    if ref.get("times") == "threshold":
        if threshold is None:
            return None, "尚未计算动态阈值"
        return value * threshold, None
    return value, None


def compute_threshold(framework: dict[str, Any], data: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    cfg = framework.get("thresholds") or {}
    base = float(cfg.get("base", 1.0))
    steps: list[dict[str, Any]] = [{"applied": "基准阈值", "delta": None, "value": round(base, 4)}]
    for adj in cfg.get("adjustments") or []:
        cond = adj.get("condition") or {}
        if match_conditions(cond, data, None)[0]:
            base += float(adj.get("delta", 0))
            steps.append({"applied": adj.get("reason") or str(cond), "delta": adj.get("delta"),
                          "value": round(base, 4)})
    return base, steps


def match_conditions(conditions: dict[str, Any], data: dict[str, Any],
                     threshold: float | None) -> tuple[bool, list[str]]:
    """全部条件必须满足（AND）。返回 (是否满足, 未满足原因列表)。"""
    reasons: list[str] = []
    for field, spec in (conditions or {}).items():
        if isinstance(spec, dict):
            op = spec.get("op")
            if op not in OPS:
                reasons.append(f"操作符未注册：{op}")
                continue
            if field not in data:
                reasons.append(f"缺少字段 {field}")
                continue
            right, err = _resolve(spec.get("value"), data, threshold)
            if err:
                reasons.append(err)
                continue
            try:
                ok = OPS[op](data[field], right)
            except TypeError:
                reasons.append(f"类型不符：{field} {op} {right!r}")
                continue
            if not ok:
                reasons.append(f"不满足：{field} {op} {right!r}")
        else:
            if data.get(field) != spec:
                reasons.append(f"不满足：{field} = {spec!r}")
    return (not reasons), reasons


def eval_signals(framework: dict[str, Any], data: dict[str, Any],
                 threshold: float) -> tuple[dict[str, bool], dict[str, str]]:
    hit: dict[str, bool] = {}
    why: dict[str, str] = {}
    for sig in framework.get("signals") or []:
        name = sig.get("name")
        ok, reasons = match_conditions(sig.get("when") or {}, data, threshold)
        hit[name] = ok
        why[name] = "满足" if ok else "；".join(reasons[:1]) or "不满足"
    return hit, why


def _exception_effect(rule: dict[str, Any], data: dict[str, Any], threshold: float,
                      signals: dict[str, bool]) -> dict[str, Any] | None:
    """例外规则：条件满足时返回其 override 描述。"""
    cond = rule.get("condition") or {}
    if cond.get("all_signals"):
        if not all(signals.get(s) for s in cond["all_signals"]):
            return None
    if cond.get("conditions"):
        if not match_conditions(cond["conditions"], data, threshold)[0]:
            return None
    if cond.get("requires_field"):
        f, v = cond["requires_field"], cond.get("equals")
        if data.get(f) != v:
            return None
    return rule.get("override") or {}


def judge(framework: dict[str, Any], data: dict[str, Any],
          *, confidence: float | None = None, confidence_status: str = "unverified",
          confidence_basis: str = "") -> dict[str, Any]:
    """按框架判定一组输入，返回判定包（结论/严重度/推理路径/证据）。"""
    path: list[dict[str, Any]] = []

    # ── 第 1 步：行业分类 ──
    industry = data.get("行业")
    category = (framework.get("industry_map") or {}).get(industry)
    weights = (framework.get("industry_weights") or {}).get(category) if category else None
    path.append({"step": 1, "name": "行业分类",
                 "detail": (f"归入 {category} 类别，权重 {weights}" if category
                            else f"行业 {industry!r} 未在映射表中，沿用默认权重")})

    # ── 第 2 步：动态阈值 ──
    threshold, threshold_steps = compute_threshold(framework, data)
    path.append({"step": 2, "name": "动态阈值计算",
                 "detail": "；".join(f"{s['applied']}"
                                     + (f" {s['delta']:+g}" if s["delta"] is not None else "")
                                     + f" → {s['value']}" for s in threshold_steps)})

    # ── 第 3 步：信号与交叉验证 ──
    signals, why = eval_signals(framework, data, threshold)
    matched = [r for r in (framework.get("combination_rules") or [])
               if all(signals.get(s) for s in (r.get("all_of") or []))]
    path.append({"step": 3, "name": "风险交叉验证",
                 "detail": "命中 " + ("；".join(f"{r.get('conclusion')}（{'+'.join(r.get('all_of') or [])}）"
                                              for r in matched) if matched else "无组合规则命中")
                           + "｜信号：" + "、".join(f"{k}={'是' if v else '否'}" for k, v in signals.items())})

    # ── 第 4 步：例外识别（可改写阈值并重算信号）──
    applied: list[dict[str, Any]] = []
    for rule in framework.get("exception_rules") or []:
        eff = _exception_effect(rule, data, threshold, signals)
        if not eff:
            continue
        kind = eff.get("kind")
        if kind == "adjust_threshold":
            threshold *= float(eff.get("factor", 1.0))
            signals, why = eval_signals(framework, data, threshold)
            matched = [r for r in (framework.get("combination_rules") or [])
                       if all(signals.get(s) for s in (r.get("all_of") or []))]
            applied.append(f"{rule.get('reason') or '例外'}：阈值 → {round(threshold, 4)}")
        elif kind == "reduce_weight":
            applied.append(f"{rule.get('reason') or '例外'}：{eff.get('target')} 权重 × {eff.get('factor')}")
        elif kind == "force_conclusion":
            applied.append(f"{rule.get('reason') or '例外'}：直接判定 {eff.get('conclusion')}")
        else:
            applied.append(f"{rule.get('reason') or '例外'}：{eff}")
    path.append({"step": 4, "name": "例外识别",
                 "detail": "；".join(applied) if applied else "无例外条件命中"})

    # ── 第 5 步：优先级 ──
    prio = {p.get("signal"): int(p.get("priority", 99)) for p in (framework.get("signal_priority") or [])}
    def rank(rule: dict[str, Any]) -> int:
        return min([prio.get(s, 99) for s in (rule.get("all_of") or [])] or [99])
    matched.sort(key=lambda r: (rank(r), -SEVERITY_ORDER.get(r.get("severity") or "", 0)))
    path.append({"step": 5, "name": "信号优先级",
                 "detail": "；".join(f"{s} 第 {p} 位" for s, p in
                                     sorted(prio.items(), key=lambda kv: kv[1])[:3]) or "未定义优先级"})

    # ── 第 6 步：综合判定 ──
    forced = [a for a in applied if "直接判定" in a]
    if forced:
        decision = str(forced[0]).split("直接判定")[-1].strip()
        severity = "极高"
    elif matched:
        top = matched[0]
        decision, severity = top.get("conclusion"), top.get("severity") or "中"
    else:
        decision, severity = "无明确结论", "低"
    path.append({"step": 6, "name": "综合判定",
                 "detail": f"结论 {decision}，严重度 {severity}"
                           + ("（由例外规则直接判定）" if forced else
                              f"（按优先级取命中组合：{'、'.join(r.get('conclusion') or '' for r in matched[:2])}）"
                              if matched else "（无组合规则命中）")})

    evidence = []
    for field in (framework.get("evidence_fields") or ["市盈率", "行业平均市盈率", "客户集中度",
                                                       "现金流状况", "核心团队流失风险"]):
        if field in data:
            item = {"factor": field, "value": data[field], "source": "调用方提供"}
            if field == "市盈率":
                item["benchmark"] = f"行业平均 {data.get('行业平均市盈率')}"
                item["dynamic_threshold"] = f"{round(float(data.get('行业平均市盈率') or 0) * threshold, 4)}"
            evidence.append(item)

    return {
        "decision": decision, "severity": severity,
        "confidence": confidence, "confidence_status": confidence_status,
        "confidence_basis": confidence_basis,
        "reasoning_path": path,
        "signals": signals, "signal_reasons": why,
        "threshold": round(threshold, 6),
        "matched_rules": [{"conclusion": r.get("conclusion"), "severity": r.get("severity"),
                           "all_of": r.get("all_of")} for r in matched],
        "exceptions_applied": applied,
        "evidence": evidence,
        "rule_cited": framework.get("framework_version") or framework.get("skill_id"),
    }
