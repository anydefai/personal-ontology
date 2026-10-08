"""领域公式模型（formula_v1）：判断的核心是一个明确的计算式。

适用：剂量（体重 × 肾功能）、折现现金流、精算现值、成本收益比。
不适用：判断本身没有公式、只有经验权重（那是评分卡）或只有要件（那是要件逻辑）。

表达式只允许白名单里的东西 —— 不用 eval，不做属性访问与下标，不定义函数：
    数字 · 字段名 · 已定义的公式名 · + - * / · 括号 · 一元负号
    min(a,b) max(a,b) abs(x) round(x[,n])
    < <= > >= == != · and or not
    字符串字面量（只用于 == / != 比较选项字段）
"""
from __future__ import annotations

import re
from typing import Any

MODEL_ID = "formula_v1"
MODEL_VERSION = "1"

MAX_LEN = 400
MAX_TOKENS = 200
MAX_DEPTH = 20

TOKEN_RE = re.compile(r"""
    (?P<num>\d+(?:\.\d+)?)
  | (?P<str>"[^"]{0,60}"|'[^']{0,60}')
  | (?P<name>[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*)
  | (?P<op><=|>=|==|!=|[()+\-*/,<>])
  | (?P<ws>\s+)
""", re.X)

KEYWORDS = {"and", "or", "not", "且", "或", "非"}
FUNCS = {"min": 2, "max": 2, "abs": 1, "round": -1}


class FormulaError(ValueError):
    pass


def tokenize(expr: str) -> list[tuple[str, Any, int]]:
    if len(expr) > MAX_LEN:
        raise FormulaError("公式太长（上限 %d 字符）" % MAX_LEN)
    tokens: list[tuple[str, Any, int]] = []
    i = 0
    while i < len(expr):
        m = TOKEN_RE.match(expr, i)
        if not m:
            raise FormulaError("第 %d 个字符附近看不懂：%r" % (i + 1, expr[i:i + 8]))
        kind = m.lastgroup
        text = m.group(0)
        pos = i + 1
        if kind != "ws":
            if kind == "num":
                tokens.append(("num", float(text), pos))
            elif kind == "str":
                tokens.append(("str", text[1:-1], pos))
            elif kind == "name":
                low = text.lower()
                if low in ("and", "or", "not"):
                    tokens.append(("op", low, pos))
                elif text in ("且", "或", "非"):
                    tokens.append(("op", {"且": "and", "或": "or", "非": "not"}[text], pos))
                elif low in FUNCS:
                    tokens.append(("func", low, pos))
                else:
                    tokens.append(("name", text, pos))
            else:
                tokens.append(("op", text, pos))
        i = m.end()
    if len(tokens) > MAX_TOKENS:
        raise FormulaError("公式太长（词数上限 %d）" % MAX_TOKENS)
    return tokens


class _Eval:
    """递归下降 → 直接求值。or → and → not → cmp → add → mul → unary → atom。"""

    def __init__(self, tokens: list[tuple[str, Any, int]], values: dict[str, Any], formulas: dict[str, str],
                 resolving: tuple[str, ...] = ()) -> None:
        self.t = tokens
        self.i = 0
        self.values = values
        self.formulas = formulas
        self.resolving = resolving
        self.used: list[str] = []

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None, 0)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        v = self._or()
        if self.i != len(self.t):
            raise FormulaError("第 %d 个字符处有看不懂的内容" % self.peek()[2])
        return v

    def _or(self):
        v = self._and()
        while self.peek()[:2] == ("op", "or"):
            self.take(); r = self._and(); v = bool(v) or bool(r)
        return v

    def _and(self):
        v = self._not()
        while self.peek()[:2] == ("op", "and"):
            self.take(); r = self._not(); v = bool(v) and bool(r)
        return v

    def _not(self):
        if self.peek()[:2] == ("op", "not"):
            self.take(); return not bool(self._not())
        return self._cmp()

    def _cmp(self):
        left = self._add()
        while self.peek()[0] == "op" and self.peek()[1] in ("<", "<=", ">", ">=", "==", "!="):
            op = self.take()[1]
            right = self._add()
            if op == "<": left = left < right
            elif op == "<=": left = left <= right
            elif op == ">": left = left > right
            elif op == ">=": left = left >= right
            elif op == "==": left = left == right
            else: left = left != right
        return left

    def _add(self):
        v = self._mul()
        while self.peek()[0] == "op" and self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            r = self._mul()
            v = (v + r) if op == "+" else (v - r)
        return v

    def _mul(self):
        v = self._unary()
        while self.peek()[0] == "op" and self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            r = self._unary()
            if op == "*":
                v = v * r
            else:
                if r == 0:
                    raise FormulaError("除以 0")
                v = v / r
        return v

    def _unary(self):
        if self.peek()[:2] == ("op", "-"):
            self.take(); return -self._unary()
        if self.peek()[:2] == ("op", "+"):
            self.take(); return self._unary()
        return self._atom()

    def _atom(self):
        kind, value, pos = self.take()
        if kind == "num" or kind == "str":
            return value
        if kind == "op" and value == "(":
            v = self._or()
            if self.peek()[:2] != ("op", ")"):
                raise FormulaError("第 %d 个字符处的括号没有闭合" % pos)
            self.take()
            return v
        if kind == "func":
            if self.peek()[:2] != ("op", "("):
                raise FormulaError("函数 %s 后面要跟括号" % value)
            self.take()
            args = [self._or()]
            while self.peek()[:2] == ("op", ","):
                self.take(); args.append(self._or())
            if self.peek()[:2] != ("op", ")"):
                raise FormulaError("函数 %s 的括号没有闭合" % value)
            self.take()
            need = FUNCS[value]
            if need >= 0 and len(args) != need:
                raise FormulaError("%s 需要 %d 个参数" % (value, need))
            try:
                if value == "min": return min(args)
                if value == "max": return max(args)
                if value == "abs": return abs(args[0])
                return round(args[0], int(args[1]) if len(args) > 1 else 0)
            except TypeError as exc:
                raise FormulaError("%s 的参数类型不对：%s" % (value, exc)) from exc
        if kind == "name":
            if value in self.formulas:
                if value in self.resolving:
                    raise FormulaError("公式互相引用成环：%s" % " → ".join(self.resolving + (value,)))
                if len(self.resolving) >= MAX_DEPTH:
                    raise FormulaError("公式嵌套太深（上限 %d 层）" % MAX_DEPTH)
                sub = _Eval(tokenize(self.formulas[value]), self.values, self.formulas, self.resolving + (value,))
                v = sub.parse()
                self.used.extend(sub.used)
                return v
            if value not in self.values:
                raise FormulaError("没有这个字段或公式：%s" % value)
            self.used.append(value)
            return self.values[value]
        raise FormulaError("第 %d 个字符处语法不对" % pos)


def evaluate(expr: str, values: dict[str, Any], formulas: dict[str, str]) -> tuple[Any, list[str]]:
    ev = _Eval(tokenize(expr), values, formulas)
    return ev.parse(), ev.used


class FormulaV1:
    id = MODEL_ID
    version = MODEL_VERSION
    label_zh = "领域公式（核心是一个计算式）"
    label_en = "Domain formula"
    applicable = ("领域里有明确计算式的判断：剂量（体重 × 肾功能）、折现现金流、精算现值、成本收益比。")
    not_applicable = ["判断没有公式、只有经验权重（用评分卡）",
                      "判断只有要件是否成立（用要件逻辑）",
                      "概率型结论（只给分档，不给概率）"]

    # ── 框架里的公式表：支持三种写法 ──
    @staticmethod
    def _formulas(framework: dict) -> dict[str, str]:
        out: dict[str, str] = {}
        raw = framework.get("formulas")
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, str):
                    out[str(k)] = v
                elif isinstance(v, dict) and v.get("expr"):
                    out[str(k)] = str(v["expr"])
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("name") and item.get("expr"):
                    out[str(item["name"])] = str(item["expr"])
        return out

    @staticmethod
    def _bands(framework: dict) -> list[dict]:
        bands = framework.get("bands") or framework.get("score_bands") or {}
        out: list[dict] = []
        if isinstance(bands, dict):
            for key, b in bands.items():
                if isinstance(b, dict):
                    out.append({"key": key, **b})
        elif isinstance(bands, list):
            out = [b for b in bands if isinstance(b, dict)]
        return out

    def input_contract(self) -> dict:
        return {
            "model": MODEL_ID,
            "fields": {
                "inputs": "需要调用方提交的信息（全部必填）",
                "formulas": "具名公式：名字 → 表达式（可用字段名、其它公式名、min/max/abs/round）",
                "bands": "公式结果 → 结论（可写 min / max / expr 条件）",
                "citations": "依据",
                "fallback": "什么都不命中时的兜底结论",
            },
            "expression": "体重 * 肾功能系数　／　min(a, b) + round(c, 1)　／　现金流 / (1 + 折现率)",
            "safety": "白名单算子；不用 eval；无属性访问与下标；长度/词数/嵌套深度都有上限；除零与成环都会报错",
            "precedence": ["第一条成立的分档条件", "兜底结论", "无明确结论"],
            "report_fields": ["decision", "severity", "formula_values", "band_cited", "reasoning_path"],
        }

    def validate(self, framework: dict) -> list[dict]:
        problems: list[dict] = []
        formulas = self._formulas(framework)
        if not formulas:
            problems.append({"level": "warn", "where": "公式", "reason": "没有定义任何公式"})
        names = {}
        for k in (framework.get("inputs") or []):
            if isinstance(k, dict) and k.get("name"):
                names[str(k["name"])] = 0.0
        for name, expr in formulas.items():
            try:
                evaluate(expr, names, {k: v for k, v in formulas.items() if k != name})
            except FormulaError as exc:
                problems.append({"level": "error" if "成环" in str(exc) else "warn",
                                 "where": "公式「%s」" % name, "reason": str(exc)})
        if not self._bands(framework):
            problems.append({"level": "warn", "where": "分档", "reason": "没有分档条件，任何结果都只能落到兜底"})
        return problems

    def judge(self, framework: dict, data: dict, **kwargs: Any) -> dict:
        required = [str(x.get("name")) for x in (framework.get("inputs") or [])
                    if isinstance(x, dict) and x.get("name")]
        missing = [k for k in required if k not in data or data[k] in (None, "")]
        confidence = kwargs.get("confidence")
        confidence_status = str(kwargs.get("confidence_status") or "unverified")
        confidence_basis = str(kwargs.get("confidence_basis") or "")
        formulas = self._formulas(framework)

        if missing:
            return {
                "decision": "信息不足，无法判断", "severity": "未判定",
                "required_inputs": required, "missing_inputs": missing,
                "evidence": ["缺少 %d 项必需输入：%s" % (len(missing), "、".join(missing))],
                "basis": [], "score": None, "confidence": confidence,
                "confidence_status": confidence_status, "confidence_basis": confidence_basis,
                "reasoning_path": [{"step": 0, "name": "输入完整性检查",
                                    "detail": "缺少 %d 项（%s），按约定不出结论" % (len(missing), "、".join(missing))}],
                "signals": {}, "threshold": None, "formula_values": {}, "band_cited": [],
            }

        values = {k: v for k, v in data.items()}
        for k, v in data.items():                       # 能转成数字的选项字段不转，保持原样以支持字符串比较
            values[k] = v

        path: list[dict[str, Any]] = []
        fv: dict[str, Any] = {}
        errors: list[str] = []
        for name in formulas:
            try:
                v, used = evaluate(formulas[name], values, formulas)
                fv[name] = v
                values[name] = v
                path.append({"step": len(path) + 1, "name": "公式 %s" % name,
                             "detail": "%s = %s（用到：%s）" % (name, v, "、".join(used) or "常量")})
            except FormulaError as exc:
                errors.append("公式 %s：%s" % (name, exc))
        if errors:
            return {
                "decision": "公式无法计算", "severity": "未判定",
                "required_inputs": required, "missing_inputs": [],
                "evidence": errors, "basis": [], "score": None,
                "confidence": confidence, "confidence_status": confidence_status,
                "confidence_basis": confidence_basis,
                "reasoning_path": path + [{"step": 99, "name": "公式报错", "detail": "；".join(errors)}],
                "signals": {}, "threshold": None, "formula_values": fv, "band_cited": [],
            }

        decision = severity = None
        cited: list[dict] = []
        for n, band in enumerate(self._bands(framework), 1):
            ok = None
            try:
                if band.get("expr"):
                    ok, _used = evaluate(str(band["expr"]), values, formulas)
                else:
                    target = band.get("min") is not None and "min" or ("max" if band.get("max") is not None else None)
                    ref = fv.get(str(band.get("formula") or "")) if band.get("formula") else None
                    if ref is None and len(fv) == 1:
                        ref = list(fv.values())[0]
                    if ref is None:
                        continue
                    if band.get("min") is not None and band.get("max") is not None:
                        ok = float(band["min"]) <= float(ref) <= float(band["max"])
                    elif band.get("min") is not None:
                        ok = float(ref) >= float(band["min"])
                    else:
                        ok = float(ref) <= float(band.get("max"))
            except (FormulaError, TypeError, ValueError) as exc:
                path.append({"step": len(path) + 1, "name": "分档 %d 报错" % n, "detail": str(exc)})
                continue
            if ok:
                decision = band.get("conclusion")
                severity = band.get("severity") or "中"
                cited.append({"band": n, **{k: v for k, v in band.items() if k in ("key", "min", "max", "expr")},
                              "conclusion": decision, "severity": severity})
                path.append({"step": len(path) + 1, "name": "分档命中",
                             "detail": "%s → %s（%s）" % (band.get("key") or band.get("expr") or "", decision, severity)})
                break

        if decision is None:
            fb = framework.get("fallback") or {}
            if fb.get("conclusion"):
                decision, severity = fb["conclusion"], fb.get("severity") or "低"
                path.append({"step": 99, "name": "兜底结论", "detail": "没有分档命中 → %s" % decision})
            else:
                decision, severity = "无明确结论", "低"
                path.append({"step": 99, "name": "无明确结论", "detail": "没有分档命中，也没有兜底结论"})

        basis: list[str] = []
        for c in (framework.get("citations") or []):
            if isinstance(c, dict) and c.get("text"):
                need = [str(x) for x in (c.get("signals") or [])]
                if need and not all(values.get(k) for k in need):
                    continue
                basis.append(str(c["text"]))

        return {
            "decision": decision, "severity": severity, "score": None,
            "required_inputs": required, "missing_inputs": [],
            "evidence": [{"factor": k, "value": data.get(k), "source": "调用方提供"} for k in required if k in data],
            "basis": basis, "confidence": confidence, "confidence_status": confidence_status,
            "confidence_basis": confidence_basis, "reasoning_path": path,
            "signals": {}, "signal_reasons": {}, "threshold": None,
            "formula_values": fv, "band_cited": cited,
            "matched_rules": [], "exceptions_applied": [], "rule_cited": [],
        }

    def output_contract(self) -> dict:
        return {
            "model": MODEL_ID, "model_version": MODEL_VERSION,
            "always": ["decision", "severity", "required_inputs", "missing_inputs"],
            "when_present": ["formula_values", "band_cited", "basis", "evidence", "reasoning_path"],
            "caller_visible": ["decision", "severity", "basis", "required_inputs", "missing_inputs",
                               "reasoning_steps", "model", "model_version", "tier"],
        }

    def reasoning(self, package: dict) -> list[dict]:
        return [{"step": s.get("step"), "name": s.get("name")} for s in (package.get("reasoning_path") or [])]


FORMULA_V1 = FormulaV1()
