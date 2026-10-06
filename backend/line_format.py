"""逐行输入格式：让不写 JSON 的人也能录判断。

设计原则：
  * **一行一条**，用中文短语；写错只影响那一行（其余照常导入，并逐行报告）。
  * **宽容**：全角/半角、多余空格、中英文标点都可以；注释行以 # 开头。
  * **不猜领域内容**：解析器只认语法，不认识"市盈率"是什么意思。

六种输入（对应框架的六个部分）：
  inputs      名称 ｜ 数字 / 文字 / 选项 ｜ 甲、乙 / 是-否 / 多项 ｜ 甲、乙
  thresholds  基准 1.3        条件=值 → +0.15
  signals     信号名 = 字段 大于/小于/等于/属于/包含 值        （可用「字段 × 基准线」）
  rules       信号 且 信号 且 信号 → 结论（严重度）
  exceptions  条件 且 条件 → 团队流失权重 ×0.5 / 基准线 ×1.2 / 直接判 结论
  priority    甲 > 乙 > 丙        （> 两边留空格；信号名里自带 > 不受影响）
"""
from __future__ import annotations

import re
from typing import Any

OPS = {"大于": "gt", "不小于": "gte", "小于": "lt", "不大于": "lte", "等于": "eq",
       "不等于": "neq", "属于": "in", "不属于": "not_in", "包含": "contains"}
TYPES = {"文字": "string", "字符串": "string", "数字": "number", "选项": "enum",
         "枚举": "enum", "是-否": "bool", "是否": "bool", "多项": "multi"}
SEV = ("低", "中", "高", "极高")


class LineError(dict):
    pass


def _clean(line: str) -> str:
    s = line.strip()
    s = s.replace("｜", "|").replace("：", ":").replace("，", ",").replace("；", ";")
    return s


def _err(n: int, raw: str, reason: str) -> dict[str, Any]:
    return {"line": n, "text": raw.strip(), "reason": reason}


def _num(text: str) -> float | None:
    t = text.strip().replace("＋", "+").replace("－", "-").replace("％", "%")
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)%?$", t)
    return float(m.group(1)) if m else None


def parse_inputs(lines: list[str]) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 2 or not parts[0]:
            bad.append(_err(n, raw, "格式：名称 ｜ 类型（｜ 可选项）")); continue
        name, tname = parts[0], parts[1]
        t = TYPES.get(tname)
        if not t:
            bad.append(_err(n, raw, f"类型「{tname}」不认识（可用：文字/数字/选项/是-否/多项）")); continue
        item: dict[str, Any] = {"name": name, "type": t}
        if len(parts) >= 3 and parts[2]:
            vals = [v.strip() for v in re.split(r"[、,]", parts[2]) if v.strip()]
            if vals:
                item["values"] = vals
        if t == "enum" and "values" not in item:
            bad.append(_err(n, raw, "类型是「选项」，请把可选项写在第三段")); continue
        ok.append(item)
    return ok, bad


def parse_thresholds(lines: list[str]) -> tuple[dict, list[dict]]:
    base, adj, bad = 1.0, [], []
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        if s.startswith("基准"):
            v = _num(s[2:].strip().lstrip(":").strip())
            if v is None:
                bad.append(_err(n, raw, "基准后面要写数字，例如：基准 1.3"))
            else:
                base = v
            continue
        if "→" not in raw and "->" not in raw:
            bad.append(_err(n, raw, "格式：条件=值 → 调整量（例如 监管环境=收紧 → -0.10）")); continue
        left, right = re.split(r"→|->", raw, maxsplit=1)
        d = _num(right)
        if d is None:
            bad.append(_err(n, raw, "箭头右边要写数字，例如 +0.15")); continue
        cond = {}
        k, _, v = _clean(left).partition("=")
        if not k.strip():
            bad.append(_err(n, raw, "箭头左边要写 字段=值")); continue
        cond[k.strip()] = v.strip()
        adj.append({"condition": cond, "delta": d, "reason": ""})
    return {"base": base, "adjustments": adj}, bad


def parse_signals(lines: list[str]) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        if "=" not in s or " " not in s.split("=", 1)[1]:
            bad.append(_err(n, raw, "格式：信号名 = 字段 大于 值（可写「字段 × 基准线 ｜ 维度」）")); continue
        name, body = s.split("=", 1)
        dimension = None
        if "|" in body:                      # 第四段：这个信号属于哪个权重维度
            body, dimension = body.split("|", 1)
            dimension = dimension.strip() or None
        body = body.strip()
        op_cn = next((o for o in OPS if body.startswith(o)), None)
        if not op_cn:
            m = re.search(r"\s(大于|不小于|小于|不大于|等于|不等于|属于|不属于|包含)\s", body)
            op_cn = m.group(1) if m else None
        if not op_cn:
            bad.append(_err(n, raw, "没找到比较词（大于/小于/等于/属于/包含…）")); continue
        field, rest = body.split(op_cn, 1)
        field, rest = field.strip(), rest.strip()
        if not field or not rest:
            bad.append(_err(n, raw, "比较词两边都要写内容")); continue
        if "×" in rest or "*" in rest:
            ref = re.split(r"[×*]", rest)[0].strip()
            if not ref:
                bad.append(_err(n, raw, "「× 基准线」前面要写字段名")); continue
            value: Any = {"ref": ref, "times": "threshold"}
        else:
            v = _num(rest)
            value = v if v is not None else rest
        item = {"name": name.strip(), "when": {field: {"op": OPS[op_cn], "value": value}}}
        if dimension:
            item["dimension"] = dimension
        ok.append(item)
    return ok, bad


def parse_rules(lines: list[str], signal_names: list[str]) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        if "→" not in raw and "->" not in raw:
            bad.append(_err(n, raw, "格式：信号 且 信号 → 结论（严重度）")); continue
        left, right = re.split(r"→|->", raw, maxsplit=1)
        sigs = [x.strip() for x in re.split(r"且|,|、", _clean(left)) if x.strip()]
        right = right.strip()
        m = re.match(r"^(.*?)[（(](低|中|高|极高)[）)]?$", right)
        if m:
            conclusion, severity = m.group(1).strip(), m.group(2)
        else:
            conclusion, severity = right, "中"
        if not sigs or not conclusion:
            bad.append(_err(n, raw, "「且」左边要有信号，箭头右边要有结论")); continue
        unknown = [x for x in sigs if signal_names and x not in signal_names]
        if unknown:
            bad.append(_err(n, raw, f"这些信号还没定义：{'、'.join(unknown)}")); continue
        ok.append({"all_of": sigs, "conclusion": conclusion, "severity": severity})
    return ok, bad


def parse_exceptions(lines: list[str]) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        if "→" not in raw and "->" not in raw:
            bad.append(_err(n, raw, "格式：条件 且 条件 → 改写方式")); continue
        left, right = re.split(r"→|->", raw, maxsplit=1)
        conds = [x.strip() for x in re.split(r"且|,|、", _clean(left)) if x.strip()]
        signals, fields = [], {}
        for c in conds:
            k, sep, v = c.partition("=")
            if sep:
                fields[k.strip()] = v.strip()
            else:
                signals.append(c)
        right = _clean(right)
        ov: dict[str, Any]
        if right.startswith("直接判"):
            ov = {"kind": "force_conclusion", "conclusion": right[3:].strip().lstrip(":").strip()}
        elif "权重" in right and "×" in right or "权重" in right and "*" in right:
            target = re.split(r"权重", right)[0].strip()
            factor = _num(re.split(r"[×*]", right)[-1])
            if not target or factor is None:
                bad.append(_err(n, raw, "格式：某维度权重 ×0.5")); continue
            ov = {"kind": "reduce_weight", "target": target, "factor": factor}
        elif "基准线" in right or "阈值" in right:
            factor = _num(re.split(r"[×*]", right)[-1]) if ("×" in right or "*" in right) else None
            if factor is None:
                bad.append(_err(n, raw, "格式：基准线 ×1.2")); continue
            ov = {"kind": "adjust_threshold", "factor": factor}
        else:
            bad.append(_err(n, raw, "改写方式看不懂（可用：某维度权重 ×0.5 / 基准线 ×1.2 / 直接判 结论）")); continue
        ok.append({"condition": {"all_signals": signals, "conditions": fields}, "override": ov, "reason": ""})
    return ok, bad


def parse_priority(lines: list[str]) -> tuple[list[dict], list[dict]]:
    names, bad = [], []
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        # 分隔符要求「两边留空格」：这样信号名里自带的 > 不会被切开（例如 客户集中度>70）
        parts = [x.strip() for x in re.split(r"\s+>\s+|\s+＞\s+", raw) if x.strip()]
        if len(parts) < 2:
            bad.append(_err(n, raw, "格式：更重要的 > 次重要的（> 两边要留空格，至少两个）")); continue
        names.extend(parts)
    # 去重保序
    seen, ordered = set(), []
    for x in names:
        if x not in seen:
            seen.add(x); ordered.append(x)
    return [{"signal": s, "priority": i + 1} for i, s in enumerate(ordered)], bad


def apply_lines(framework: dict[str, Any], texts: dict[str, str]) -> dict[str, Any]:
    """把六个框里的文本并入框架。返回 {framework, report}。

    report = {"<部分>": {"imported": n, "errors": [ {line,text,reason}, … ]}}
    """
    fw = dict(framework or {})
    report: dict[str, Any] = {}

    def lines_of(part: str) -> list[str]:
        return (texts.get(part) or "").split("\n")

    if texts.get("inputs"):
        ok, bad = parse_inputs(lines_of("inputs"))
        fw["inputs"] = ok
        report["inputs"] = {"imported": len(ok), "errors": bad}
    if texts.get("thresholds"):
        th, bad = parse_thresholds(lines_of("thresholds"))
        fw["thresholds"] = th
        report["thresholds"] = {"imported": len(th["adjustments"]) + 1, "errors": bad}
    if texts.get("signals"):
        ok, bad = parse_signals(lines_of("signals"))
        fw["signals"] = ok
        report["signals"] = {"imported": len(ok), "errors": bad}
    names = [s.get("name") for s in (fw.get("signals") or [])]
    if texts.get("rules"):
        ok, bad = parse_rules(lines_of("rules"), names)
        fw["combination_rules"] = ok
        report["rules"] = {"imported": len(ok), "errors": bad}
    if texts.get("exceptions"):
        ok, bad = parse_exceptions(lines_of("exceptions"))
        fw["exception_rules"] = ok
        report["exceptions"] = {"imported": len(ok), "errors": bad}
    if texts.get("citations"):
        ok, bad = parse_citations(lines_of("citations"))
        fw["citations"] = ok
        report["citations"] = {"imported": len(ok), "errors": bad}
    if texts.get("fallback"):
        fb, bad = parse_fallback(lines_of("fallback"))
        if fb:
            fw["fallback"] = fb
        report["fallback"] = {"imported": 1 if fb else 0, "errors": bad}
    if texts.get("score"):
        sc, bad = parse_score(lines_of("score"))
        if sc:
            fw["score_bands"] = sc
        report["score"] = {"imported": len(sc), "errors": bad}
    if texts.get("priority"):
        ok, bad = parse_priority(lines_of("priority"))
        fw["signal_priority"] = ok
        report["priority"] = {"imported": len(ok), "errors": bad}
    return {"framework": fw, "report": report}

def parse_citations(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """依据：一行一条。
       依据名                          → 始终附上
       依据名 → 信号1 且 信号2          → 这些信号**全部命中**时才附上
    """
    ok, bad = [], []
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        if "→" in raw or "->" in raw:
            left, right = re.split(r"→|->", raw, maxsplit=1)
            sigs = [x.strip() for x in re.split(r"且|,|、", _clean(right)) if x.strip()]
        else:
            left, sigs = raw, []
        text = left.strip()
        if not text:
            bad.append(_err(n, raw, "格式：依据名（可写：依据名 → 信号1 且 信号2）")); continue
        ok.append({"text": text, "signals": sigs})
    return ok, bad


def parse_fallback(lines: list[str]) -> tuple[dict, list[dict]]:
    """兜底结论：都不命中时用的结论。一行一条，取第一条。格式：都不命中 → 结论（严重度）"""
    for n, raw in enumerate(lines, 1):
        s = _clean(raw)
        if not s or s.startswith("#"):
            continue
        body = re.split(r"→|->", raw, maxsplit=1)[-1].strip() if ("→" in raw or "->" in raw) else s
        m = re.match(r"^(.*?)[（(](低|中|高|极高)[）)]?$", body)
        conclusion, severity = (m.group(1).strip(), m.group(2)) if m else (body, "低")
        if not conclusion:
            return {}, [_err(n, raw, "格式：都不命中 → 结论（严重度）")]
        return {"conclusion": conclusion, "severity": severity}, []
    return {}, []

def parse_score(lines: list[str]) -> tuple[dict, list[dict]]:
    """打分线：把汇总分变成结论。三行，缺哪行就哪条不生效。

       打分 0.5 以上 → 估值偏高（高）
       打分 0.3 以下 → 估值合理（低）
       其余 → 估值中性（中）
    """
    out: dict = {}
    bad: list[dict] = []
    for n, raw in enumerate(lines, 1):
        t = _clean(raw)
        if not t or t.startswith("#"):
            continue
        if "→" not in raw and "->" not in raw:
            bad.append(_err(n, raw, "格式：打分 0.5 以上 → 结论（严重度）")); continue
        left, right = re.split(r"→|->", raw, maxsplit=1)
        right = right.strip()
        m = re.match(r"^(.*?)[（(](低|中|高|极高)[）)]?$", right)
        conclusion, severity = (m.group(1).strip(), m.group(2)) if m else (right, "中")
        if not conclusion:
            bad.append(_err(n, raw, "箭头右边要写结论")); continue
        ml = _clean(left)
        num = re.search(r"(\d+(?:\.\d+)?)", ml)
        if "以上" in ml or ">=" in ml:
            out.setdefault("high", {})["min"] = float(num.group(1)) if num else None
            out["high"].update({"conclusion": conclusion, "severity": severity})
        elif "以下" in ml or "<=" in ml:
            out.setdefault("low", {})["max"] = float(num.group(1)) if num else None
            out["low"].update({"conclusion": conclusion, "severity": severity})
        elif "其余" in ml or "其他" in ml:
            out["mid"] = {"conclusion": conclusion, "severity": severity}
        else:
            bad.append(_err(n, raw, "要写清楚是「打分 X 以上」「打分 X 以下」还是「其余」")); continue
        if out.get("high", {}).get("min") is None and "high" in out:
            bad.append(_err(n, raw, "「以上」前面要写数字")); continue
        if out.get("low", {}).get("max") is None and "low" in out:
            bad.append(_err(n, raw, "「以下」前面要写数字")); continue
    return out, bad
