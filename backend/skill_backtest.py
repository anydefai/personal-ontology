"""技能框架回测：用历史案例检验框架判断的准确率，得出置信度。

对应设计里的第二步：导入历史案例 → 跑一遍框架 → 对比模型判定与实际结果 → 得到置信度。
没有历史案例时，置信度保持"未验证"，由调用方自行决定是否接受。

置信度分级（本模块实现前两级；后三级需要调用方反馈与第三方认证）：
    unverified   未验证：没有依据
    backtested   回测置信度：基于 N 个历史案例，准确率 X
    preliminary  初步置信度：≥10 次调用反馈（未实现）
    stable       稳定置信度：≥100 次调用反馈（未实现）
    certified    认证置信度：第三方审计（未实现）
"""
from __future__ import annotations

from typing import Any

from .skill_framework import judge

MIN_BACKTEST_CASES = 1
PRELIMINARY_FEEDBACKS = 10      # 供后续阶段使用
STABLE_FEEDBACKS = 100


def run_backtest(framework: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    """对每个历史案例跑一遍框架，与案例记录的实际结果对比。

    cases: [{"case_id": "CASE-001", "inputs": {...}, "actual_result": "估值偏高"}, ...]
    对比规则：模型结论与 actual_result **逐字相等**才算一致（口径必须明示，不做模糊匹配）。
    """
    if not isinstance(cases, list):
        raise ValueError("cases 必须是数组")
    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"第 {idx + 1} 个案例不是对象")
        inputs = case.get("inputs")
        if not isinstance(inputs, dict):
            raise ValueError(f"第 {idx + 1} 个案例缺少 inputs 对象")
        expected = case.get("actual_result")
        if expected is None:
            raise ValueError(f"第 {idx + 1} 个案例缺少 actual_result")
        package = judge(framework, inputs)
        rows.append({
            "case_id": case.get("case_id") or f"case_{idx + 1}",
            "expected": expected,
            "actual": package["decision"],
            "severity": package["severity"],
            "match": expected == package["decision"],
        })
    total = len(rows)
    matched = sum(1 for r in rows if r["match"])
    accuracy = round(matched / total, 4) if total else None
    return {
        "total": total,
        "matched": matched,
        "mismatched": total - matched,
        "accuracy": accuracy,
        "confidence_status": "backtested" if total >= MIN_BACKTEST_CASES else "unverified",
        "mismatch_detail": [r for r in rows if not r["match"]][:20],   # 明细最多列 20 条
        "comparison_rule": "结论与 actual_result 逐字相等",
    }


def confidence_from_feedback(total: int, accurate: int) -> dict[str, Any]:
    """调用方反馈闭环：按反馈量给出置信度分级（设计里的后三级，认证级需第三方审计）。

    反馈量 ≥10 → preliminary；≥100 → stable；不足则保持 unverified。
    准确率 = 认为准确的次数 / 全部反馈次数（口径与回测一致：单一比值，不做加权）。
    """
    total = int(total or 0)
    accurate = int(accurate or 0)
    if total >= STABLE_FEEDBACKS:
        status = "stable"
    elif total >= PRELIMINARY_FEEDBACKS:
        status = "preliminary"
    else:
        status = "unverified"
    rate = round(accurate / total, 4) if total else None
    return {"confidence_status": status, "feedback_total": total, "feedback_accurate": accurate,
            "accuracy_from_feedback": rate}
