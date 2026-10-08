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

import json
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
            # 条件调整可以加（delta）也可以乘（factor）：写 × 的走乘法，用来表达「按比例缩放基准线」。
            factor = adj.get("factor")
            if factor is not None:
                base *= float(factor)
                steps.append({"applied": adj.get("reason") or str(cond), "delta": None,
                              "factor": float(factor), "value": round(base, 4)})
            else:
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
    """按框架判定一组输入，返回判定包（结论/严重度/推理路径/证据）。

    约定 B（用户 2026-10-06 选定）：声明在 inputs 里的字段都是调用方【必须提供】的；
    缺任何一项就【不出结论】，只回「信息不足，无法判断」并列出缺哪些 —— 不假装判断过。
    """
    path: list[dict[str, Any]] = []

    required = [str(i.get("name")) for i in (framework.get("inputs") or [])
                if isinstance(i, dict) and i.get("name")]
    missing = [n for n in required if n not in (data or {})]
    if missing:
        return {
            "decision": "信息不足，无法判断", "severity": "未判定",
            "required_inputs": required, "missing_inputs": missing,
            "evidence": [f"缺少 {len(missing)} 项必需输入：{'、'.join(missing)}"],
            "basis": [], "score": 0.0,
            "confidence": confidence, "confidence_status": confidence_status,
            "confidence_basis": confidence_basis,
            "reasoning_path": [{"step": 0, "name": "输入完整性检查",
                                "detail": f"缺少 {len(missing)} 项（{'、'.join(missing)}），按约定不出结论"}],
            "signals": {}, "signal_reasons": {}, "threshold": None,
            "matched_rules": [], "exceptions_applied": [], "rule_cited": [],
        }

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
    weight_factors: dict[str, float] = {}      # 例外里的"降权"真正作用到打分上
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
            weight_factors[str(eff.get("target") or "")] = float(eff.get("factor", 1.0))
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

    # ── 打分：命中的信号 × 该行业该维度的权重（例外里的降权在此生效）──
    weights = weights or {}
    score = 0.0
    for sig in framework.get("signals") or []:
        dim = sig.get("dimension")
        if not dim or not signals.get(sig.get("name")):
            continue
        # 命中分值：不写就是 1（与拆分前完全一致）；写在 signals[].score_value 表示「部分证据」。
        sv = sig.get("score_value")
        sv = 1.0 if sv is None else float(sv)
        score += float(weights.get(dim, 0.0)) * sv * float(weight_factors.get(dim, 1.0))
    score = round(score, 6)

    # ── 第 6 步：综合判定 ──
    forced = [a for a in applied if "直接判定" in a]
    if forced:
        decision = str(forced[0]).split("直接判定")[-1].strip()
        severity = "极高"
    elif matched:
        top = matched[0]
        decision, severity = top.get("conclusion"), top.get("severity") or "中"
    else:
        bands = framework.get("score_bands") or {}
        high, low, mid = bands.get("high") or {}, bands.get("low") or {}, bands.get("mid") or {}
        if high.get("conclusion") and high.get("min") is not None and score >= float(high["min"]):
            decision, severity = str(high["conclusion"]), str(high.get("severity") or "中")
        elif low.get("conclusion") and low.get("max") is not None and score <= float(low["max"]):
            decision, severity = str(low["conclusion"]), str(low.get("severity") or "低")
        elif mid.get("conclusion"):
            decision, severity = str(mid["conclusion"]), str(mid.get("severity") or "中")
        else:
            fb = framework.get("fallback") or {}
            if isinstance(fb, dict) and fb.get("conclusion"):
                decision, severity = str(fb["conclusion"]), str(fb.get("severity") or "低")
            else:
                decision, severity = "无明确结论", "低"
    path.append({"step": 6, "name": "综合判定",
                 "detail": f"结论 {decision}，严重度 {severity}（打分 {score}）"
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

    # 依据：未写适用信号 → 始终附上；写了 → 那些信号全部命中才附上
    basis: list[str] = []
    for c in framework.get("citations") or []:
        if not isinstance(c, dict):
            continue
        sigs = c.get("signals") or []
        if sigs and not all(signals.get(s) for s in sigs):
            continue
        if c.get("text"):
            basis.append(str(c["text"]))

    return {
        "decision": decision, "severity": severity, "basis": basis, "score": score,
        "required_inputs": required, "missing_inputs": [],
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


# ── 对外交付：分层与交付物 ────────────────────────────────────────────────
# 分层来自设计：基础层只给结论；标准层加证据；专业层加推理路径；审计层给完整包。
TIERS = {
    "basic":        ["decision", "severity"],
    "standard":     ["decision", "severity", "evidence", "basis"],
    "professional": ["decision", "severity", "evidence", "reasoning_path", "threshold", "basis"],
    "audit":        ["decision", "severity", "confidence", "confidence_status", "confidence_basis",
                     "reasoning_path", "professional_insight", "evidence", "basis", "rule_cited", "threshold",
                     "signals", "signal_reasons", "exceptions_applied", "matched_rules",
                     "owner_credentials", "owner_signature",
                     "signature_status", "audit_id", "valid_until", "content_fingerprint"],
}
ALWAYS = ["definition_id", "slice_id", "tier", "required_inputs", "missing_inputs"]


def content_fingerprint(package: dict[str, Any]) -> str:
    """内容指纹：对判定核心做 SHA-256。**这不是数字签名**（没有私钥），只用于比对内容是否被改动。"""
    import hashlib
    core = {k: package.get(k) for k in ("decision", "severity", "threshold", "evidence", "reasoning_path")}
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:32]


def apply_tier(package: dict[str, Any], tier: str) -> dict[str, Any]:
    """按付费层裁剪判定包。未知分层按最低层处理（宁少给不多给）。"""
    keys = TIERS.get(tier) or TIERS["basic"]
    out = {k: package[k] for k in keys if k in package}
    for k in ALWAYS:
        if k in package:
            out[k] = package[k]
    out["tier"] = tier if tier in TIERS else "basic"
    return out


def package_identity(package: dict[str, Any], *, insight: str = "", credentials: str = "",
                     audit_id: str = "", valid_until: str = "") -> dict[str, Any]:
    """给判定包补上对外交付需要的身份信息。签名需要密钥对，本项目尚未实现 → 明确标注。"""
    package["professional_insight"] = insight or ""
    package["owner_credentials"] = credentials or ""
    package["owner_signature"] = None
    package["signature_status"] = "not_implemented"      # 不假装已签名
    package["audit_id"] = audit_id or ""
    package["valid_until"] = valid_until or ""
    package["content_fingerprint"] = content_fingerprint(package)
    return package


# Keys a caller may receive. Everything else (the framework itself) stays inside.
CALLER_KEYS = ("definition_id", "slice_id", "tier", "decision", "severity", "score",
               "basis", "evidence", "confidence", "confidence_status",
               "required_inputs", "missing_inputs", "signals", "matched_rules", "fallback_used")


# 调用方可见字段按档位分层；任何档位都不含权重、阈值、规则原文（作者的资产）。
# professional = 升级前的集合（外加 reasoning_steps），不传档位时行为与以前一致。
CALLER_TIER_ORDER = ["basic", "standard", "professional", "audit"]   # 由松到紧
CALLER_TIER_FIELDS: dict[str, list[str]] = {
    "basic": ["decision", "severity", "score", "confidence_status"],
    "standard": ["decision", "severity", "score", "confidence_status", "basis",
                 "required_inputs", "missing_inputs"],
    "professional": list(CALLER_KEYS) + ["reasoning_steps", "decided_by"],
    "audit": list(CALLER_KEYS) + ["reasoning_steps", "decided_by", "tier", "model", "model_version"],
}


def for_caller(package: dict[str, Any], tier: str | None = None) -> dict[str, Any]:
    """把判定包整理成可以递给调用方的版本。

    调用方要拿到的是**结论**与**可追溯的说明**，不是作者的计算方法：
      · 保留 结论/严重度/分数/依据/命中信号/置信度/必填与缺项/档位
      · 去掉 置信度理由（那是作者自己的话）
      · 推理步骤只保留"第几步、做了什么"，去掉其中写着的权重表与阈值算术
    设计文档第七步：调用方拿不到框架、权重与阈值。
    """
    name = str(tier or package.get("tier") or "professional").strip().lower()
    if name not in CALLER_TIER_FIELDS:
        name = "professional"
    out = {k: package.get(k) for k in CALLER_TIER_FIELDS[name] if k in package}
    # matched_rules carries the author's combination conditions; the caller only needs to know which of the
    # signals fired, which is already in `signals`.
    out.pop("matched_rules", None)
    # evidence keeps the caller's own numbers and where they came from, but not the author's benchmark
    # expression or the threshold that was computed from the framework.
    if isinstance(out.get("evidence"), list):
        out["evidence"] = [{k: v for k, v in row.items() if k in ("factor", "value", "source")}
                           for row in out["evidence"] if isinstance(row, dict)]
    if "reasoning_steps" in CALLER_TIER_FIELDS[name]:
        out["reasoning_steps"] = [
            {"step": step.get("step"), "name": step.get("name")}
            for step in (package.get("reasoning_path") or [])
        ] or None
        if out["reasoning_steps"] is None:
            out.pop("reasoning_steps")
    # 结论是怎么来的：只写【哪条例外 / 哪条组合规则】，不写权重、阈值、算式（那些是作者的资产）。
    if name in ("professional", "audit"):
        _forced = [s for s in (package.get("exceptions_applied") or []) if "直接判定" in str(s)]
        _cited = package.get("rule_cited") or []
        if _forced:
            out["decided_by"] = "例外：" + str(_forced[0])   # 保留原因（例如「标的为国资背景」）便于溯源
        elif _cited:
            out["decided_by"] = "组合规则：" + str(_cited[0])
        elif package.get("score") is not None:
            out["decided_by"] = "打分线"
        else:
            out["decided_by"] = "兜底"
    out["tier"] = name
    if name == "audit":
        out.setdefault("model", package.get("model"))
        out.setdefault("model_version", package.get("model_version"))
    return out

# ── 判定模型适配器：把本文件的算法包成一个可注册的模型（引擎只认这个接口）──
MODEL_ID = "scorecard_v1"
MODEL_VERSION = "1"

INPUT_FIELDS = ("inputs", "industry_map", "industry_weights", "thresholds", "signals",
                "combination_rules", "exception_rules", "signal_priority", "citations",
                "score_bands", "fallback")


class ScorecardV1:
    """证据累积型：多信号各自加分 → 落在若干档位。

    分数 = Σ（命中的信号 → 取「该行业类别 × 该信号所属维度」的权重）
      命中算满（1）✓ 未命中不算（0）✓ 未标维度的信号不计分 ✓
      例外的「权重 ×0.5」在这里生效 ✓
    """

    id = MODEL_ID
    version = MODEL_VERSION
    label_zh = "评分卡（证据累积）"
    label_en = "Scorecard, accumulating evidence"
    applicable = ("证据累积型判断：把若干可观察信号按重要性加权，累积成总分，再落到几个档位。"
                  "风控评分卡、保险核保、术前风险分级、合规清单都属于这一族。")
    not_applicable = ["需要顺序分支的判断（先看 A 再决定看不看 B）",
                      "要件组合型（任一满足 / 排除条件 / 嵌套逻辑）",
                      "领域公式型（剂量、折现现金流、精算现值）",
                      "概率型结论（只给分档，不给概率）"]

    def input_contract(self) -> dict:
        return {
            "model": MODEL_ID,
            "fields": {
                "inputs": "需要调用方提交的信息（全部必填）",
                "industry_map": "行业 → 类别（缺它则打分只能是 0）",
                "industry_weights": "类别 → 各维度权重（列名必须与信号末段的维度名一致）",
                "thresholds": "基准值 + 条件调整",
                "signals": "观察点：字段 + 比较 + 值，末段标维度",
                "combination_rules": "多信号同时成立（all_of）→ 结论 + 严重度",
                "exception_rules": "条件 → 调阈值 / 降权 / 直接判",
                "signal_priority": "信号重要性顺序",
                "citations": "依据（全部命中才附上）",
                "score_bands": "分数 → 结论（打分线只做这一件事）",
                "fallback": "什么都不命中时的兜底结论",
            },
            "scoring": ("分数 = Σ（命中的信号 → 该类别 × 该维度 的权重）；命中算满，未命中不算；"
                        "未标维度的信号不计分；例外的权重系数真乘进去。"),
            "precedence": ["组合规则（all_of）", "打分线", "兜底结论", "无明确结论"],
            "report_fields": list(INPUT_FIELDS),
        }

    def validate(self, framework: dict) -> list[dict]:
        """只报会【静默改变结果】的问题：不阻止，但要让用户看见。"""
        problems: list[dict] = []
        dims: set[str] = set()
        for cat, weights in (framework.get("industry_weights") or {}).items():
            if isinstance(weights, dict):
                dims.update(str(k) for k in weights)
        for sig in framework.get("signals") or []:
            if not isinstance(sig, dict):
                continue
            name = str(sig.get("name") or "")
            dim = str(sig.get("dimension") or "")
            if not dim:
                problems.append({"level": "warn", "where": f"信号「{name}」",
                                 "reason": "没有标维度，这个信号不会计分"})
            elif dims and dim not in dims:
                problems.append({"level": "warn", "where": f"信号「{name}」",
                                 "reason": f"维度「{dim}」在权重表里没有同名列，这个信号会按 0 分计"})
        for n, rule in enumerate(framework.get("combination_rules") or [], 1):
            if not isinstance(rule, dict):
                continue
            expr = str(rule.get("expr") or "")
            if expr and not rule.get("all_of") and any(k2 in expr for k2 in ("或", "非", "(", ")", "or", "not")):
                problems.append({"level": "warn", "where": "第 %d 条规则" % n,
                                 "reason": "含「或/非/括号」的规则，评分卡只支持「且」，不会被采用；"
                                           "请把判定模型切成「要件逻辑」"})
        if (framework.get("signals") or []) and not (framework.get("industry_map") or {}):
            problems.append({"level": "warn", "where": "行业归类",
                             "reason": "没有填「行业 → 类别」，任何行业都取不到权重，打分只能是 0"})
        return problems

    def judge(self, framework: dict, data: dict, **kwargs) -> dict:
        return judge(framework, data, **kwargs)

    def output_contract(self) -> dict:
        return {
            "model": MODEL_ID, "model_version": MODEL_VERSION,
            "always": ["decision", "severity", "score", "required_inputs", "missing_inputs"],
            "when_present": ["basis", "evidence", "confidence", "confidence_status", "confidence_basis",
                             "reasoning_path", "signals", "signal_reasons", "threshold",
                             "matched_rules", "exceptions_applied", "rule_cited", "fallback_used"],
            "caller_visible": ["decision", "severity", "score", "basis", "evidence", "confidence",
                               "confidence_status", "required_inputs", "missing_inputs", "signals",
                               "reasoning_steps", "model", "model_version", "tier"],
        }

    def reasoning(self, package: dict) -> list[dict]:
        return [
            {"step": s.get("step"), "name": s.get("name"),
             "detail": s.get("detail") if self.id != "scorecard_v1_external" else None}
            for s in (package.get("reasoning_path") or [])
        ]


SCORECARD_V1 = ScorecardV1()
