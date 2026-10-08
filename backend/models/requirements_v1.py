"""要件逻辑模型（requirements_v1）：结论来自"哪条规则的要件成立"。

与评分卡的分工：
  · 评分卡：多信号各自加分 → 落在档位（证据累积）
  · 本模型：每条结论对应一个【要件表达式】，成立就用它（要件逻辑，法律最常用）
它不做加权求和；命中哪条规则就是哪条，规则按声明顺序取第一条成立的。

表达式语法（写在 combination_rules 的 expr 里，或沿用 all_of）：
    且 / 或 / 非 / ( )
    例：  A 且 B 且 (C 或 D) 且 非 E
也接受英文： and / or / not
"""
from __future__ import annotations

import re
from typing import Any

MODEL_ID = "requirements_v1"
MODEL_VERSION = "1"

TOKEN = re.compile(r"\s*(\(|\)|且|或|非|and|or|not|[^()\s且或非]+)")


def tokenize(expr: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(expr):
        m = TOKEN.match(expr, i)
        if not m:
            i += 1
            continue
        tok = m.group(1)
        # 「且/或/非」可能贴着信号名，需要再切一次
        if tok not in ("(", ")") and any(k in tok for k in ("且", "或", "非")) and len(tok) > 1:
            pos = 0
            for part in re.split(r"(且|或|非)", tok):
                if part:
                    out.append(part)
            i = m.end()
            continue
        out.append(tok)
        i = m.end()
    return [t for t in out if t]


class _Parser:
    """递归下降：or → and → not → atom。"""

    def __init__(self, tokens: list[str], hit: dict[str, bool]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.hit = hit
        self.unknown: list[str] = []

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str | None:
        t = self.peek()
        if t is not None:
            self.pos += 1
        return t

    def parse(self) -> bool:
        return self._or()

    def _or(self) -> bool:
        value = self._and()
        while self.peek() in ("或", "or"):
            self.take()
            right = self._and()
            value = value or right
        return value

    def _and(self) -> bool:
        value = self._not()
        while self.peek() in ("且", "and"):
            self.take()
            right = self._not()
            value = value and right
        return value

    def _not(self) -> bool:
        if self.peek() in ("非", "not"):
            self.take()
            return not self._not()
        return self._atom()

    def _atom(self) -> bool:
        t = self.take()
        if t == "(":
            value = self._or()
            if self.peek() == ")":
                self.take()
            return value
        if t is None:
            return False
        name = t
        if name not in self.hit:
            self.unknown.append(name)
            return False
        return bool(self.hit[name])


def eval_expression(expr: str, hit: dict[str, bool]) -> tuple[bool, list[str]]:
    """求值一个要件表达式；返回 (是否成立, 认不出的要件名列表)。"""
    if not expr or not expr.strip():
        return False, []
    parser = _Parser(tokenize(expr), hit)
    value = parser.parse()
    return value, parser.unknown


class RequirementsV1:
    id = MODEL_ID
    version = MODEL_VERSION
    label_zh = "要件逻辑（成立就用它）"
    label_en = "Requirement logic"
    applicable = ("要件型判断：每条结论对应一个要件表达式，成立即用该结论。"
                  "合同效力、诉讼时效、主体资格、准入条件都属于这一族。")
    not_applicable = ["需要按重要性加权、排先后次序的判断（那是评分卡的活）",
                      "领域公式型（剂量、折现现金流、精算现值）",
                      "概率型结论（只给结论，不给概率）"]

    def input_contract(self) -> dict:
        return {
            "model": MODEL_ID,
            "fields": {
                "inputs": "需要调用方提交的信息（全部必填）",
                "signals": "要件：对数据的一个布尔判断（写法与评分卡一致）",
                "combination_rules": "每条规则：要件表达式（且/或/非/( )可嵌套）+ 结论 + 严重度；"
                                     "也接受沿用 all_of（等价于「且」）",
                "citations": "依据（其列出的要件全部成立才附上）",
                "fallback": "什么都不成立时的兜底结论",
            },
            "expression": "A 且 B 且 (C 或 D) 且 非 E　（也接受 and/or/not）",
            "precedence": ["第一条成立的要件规则", "兜底结论", "无明确结论"],
            "report_fields": ["decision", "severity", "satisfied_requirements",
                              "failed_requirements", "rule_cited", "reasoning_path"],
        }

    def validate(self, framework: dict) -> list[dict]:
        problems: list[dict] = []
        names = {str(s.get("name")) for s in (framework.get("signals") or []) if isinstance(s, dict)}
        for n, rule in enumerate(framework.get("combination_rules") or [], 1):
            if not isinstance(rule, dict):
                continue
            expr = str(rule.get("expr") or "")
            if not expr:
                continue
            _v, unknown = eval_expression(expr, {k: False for k in names})
            for u in unknown:
                problems.append({"level": "warn", "where": "第 %d 条规则" % n,
                                 "reason": "要件「%s」不在「我观察什么」里，这条永远不成立" % u})
        if not (framework.get("combination_rules") or []):
            problems.append({"level": "warn", "where": "要件规则", "reason": "没有规则，任何输入都只能落到兜底"})
        return problems

    def judge(self, framework: dict, data: dict, **kwargs: Any) -> dict:
        from backend.models import scorecard_v1 as sc

        required = [str(x.get("name")) for x in (framework.get("inputs") or []) if isinstance(x, dict) and x.get("name")]
        missing = [k for k in required if k not in data or data[k] in (None, "")]
        threshold, threshold_steps = sc.compute_threshold(framework, data)
        hit, why = sc.eval_signals(framework, data, threshold)
        path: list[dict[str, Any]] = []

        confidence = kwargs.get("confidence")
        confidence_status = str(kwargs.get("confidence_status") or "unverified")
        confidence_basis = str(kwargs.get("confidence_basis") or "")

        if missing:                                    # 约定 B：少一项就不给结论
            return {
                "decision": "信息不足，无法判断", "severity": "未判定",
                "required_inputs": required, "missing_inputs": missing,
                "evidence": ["缺少 %d 项必需输入：%s" % (len(missing), "、".join(missing))],
                "basis": [], "score": None,
                "confidence": confidence, "confidence_status": confidence_status,
                "confidence_basis": confidence_basis,
                "reasoning_path": [{"step": 0, "name": "输入完整性检查",
                                    "detail": "缺少 %d 项（%s），按约定不出结论" % (len(missing), "、".join(missing))}],
                "signals": {}, "signal_reasons": {}, "threshold": None,
                "satisfied_requirements": [], "failed_requirements": [], "rule_cited": [],
            }

        path.append({"step": 1, "name": "要件判定", "detail": "逐条规则求值（短路），取第一条成立的"})
        cited: list[dict[str, Any]] = []
        satisfied: list[str] = []
        failed: list[str] = []
        decision = severity = None
        for n, rule in enumerate(framework.get("combination_rules") or [], 1):
            if not isinstance(rule, dict):
                continue
            expr = str(rule.get("expr") or "")
            if not expr:
                all_of = [str(x) for x in (rule.get("all_of") or [])]
                expr = " 且 ".join(all_of)
            ok, unknown = eval_expression(expr, hit)
            if unknown:
                path.append({"step": n + 1, "name": "规则 %d" % n,
                             "detail": "认不出的要件：%s" % "、".join(unknown)})
            if ok:
                decision = rule.get("conclusion")
                severity = rule.get("severity")
                cited.append({"rule": n, "expr": expr, "conclusion": decision, "severity": severity})
                satisfied = [k for k, v in hit.items() if v]
                failed = [k for k, v in hit.items() if not v]
                path.append({"step": n + 1, "name": "规则 %d 成立" % n,
                             "detail": "%s → %s（%s）" % (expr, decision, severity)})
                break
            path.append({"step": n + 1, "name": "规则 %d 不成立" % n, "detail": expr})

        if decision is None:
            fb = framework.get("fallback") or {}
            if fb.get("conclusion"):
                decision, severity = fb.get("conclusion"), fb.get("severity") or "低"
                path.append({"step": 99, "name": "兜底结论", "detail": "没有规则成立 → %s" % decision})
            else:
                decision, severity = "无明确结论", "低"
                path.append({"step": 99, "name": "无明确结论", "detail": "没有规则成立，也没有兜底结论"})

        # 依据：其列出的要件全部成立才附上
        basis: list[str] = []
        for c in (framework.get("citations") or []):
            if not isinstance(c, dict):
                continue
            need = [str(x) for x in (c.get("signals") or [])]
            if need and not all(hit.get(k) for k in need):
                continue
            if c.get("text"):
                basis.append(str(c["text"]))

        return {
            "decision": decision, "severity": severity, "score": None,
            "required_inputs": required, "missing_inputs": [],
            "evidence": [{"factor": k, "value": data.get(k), "source": "调用方提供"}
                         for k in required if k in data],
            "basis": basis,
            "confidence": confidence, "confidence_status": confidence_status,
            "confidence_basis": confidence_basis,
            "reasoning_path": path,
            "signals": hit, "signal_reasons": why, "threshold": threshold,
            "satisfied_requirements": satisfied, "failed_requirements": failed,
            "rule_cited": cited, "matched_rules": cited, "exceptions_applied": [],
        }

    def output_contract(self) -> dict:
        return {
            "model": MODEL_ID, "model_version": MODEL_VERSION,
            "always": ["decision", "severity", "required_inputs", "missing_inputs"],
            "when_present": ["satisfied_requirements", "failed_requirements", "rule_cited",
                             "basis", "evidence", "reasoning_path", "signals", "threshold"],
            "caller_visible": ["decision", "severity", "basis", "required_inputs", "missing_inputs",
                               "signals", "reasoning_steps", "model", "model_version", "tier"],
        }

    def reasoning(self, package: dict) -> list[dict]:
        return [{"step": s.get("step"), "name": s.get("name")} for s in (package.get("reasoning_path") or [])]


REQUIREMENTS_V1 = RequirementsV1()
