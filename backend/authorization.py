"""第一层：授权判定 —— "能不能调"。

对应设计里的第一层（第二层是技能判定）。平台公司发起调用时，先由这一层判断：
  · 是否持有有效令牌、受众绑定是否正确   —— 由既有的访问层负责（本模块只接收它的结论）
  · 调用用途是否在授权范围内
  · 交易金额是否超过本人设定的上限
  · 调用方是否承诺不得转售

结果三态（**超上限不是拒绝，而是请本人确认** —— 这是设计里的明确口径）：
    allow    允许
    confirm  需本人确认（超金额上限）
    deny     拒绝

默认拒绝：场景定义里**没有声明边界**就不放行。未声明的空白不等于默许。
"""
from __future__ import annotations

from typing import Any


def authorize(boundaries: dict[str, Any] | None, request: dict[str, Any] | None) -> dict[str, Any]:
    """按本人设定的边界判定一次调用请求。返回 {result, checks, ...}。"""
    b = boundaries if isinstance(boundaries, dict) else {}
    r = request if isinstance(request, dict) else {}
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # ① 边界必须先声明
    if not b:
        add("已声明对外调用边界", False, "这个场景还没有设定对外调用的边界，默认不放行。")

    # ② 调用方与用途要能识别
    caller = str(r.get("caller") or "").strip()
    add("调用方已标明", bool(caller), caller or "请求里没有调用方")

    purpose = str(r.get("purpose") or "").strip()
    scenario = str(r.get("scenario") or "").strip()
    add("用途已标明", bool(purpose or scenario), purpose or scenario or "请求里没有用途")

    # ③ 用途是否在允许范围内
    allowed = [str(x) for x in (b.get("allowed_scenarios") or [])]
    if allowed:
        hit = (scenario in allowed) or (purpose in allowed)
        add("用途在允许范围内", hit, f"允许：{'、'.join(allowed)}；本次：{scenario or purpose or '（空）'}")
    else:
        add("用途在允许范围内", False, "没有声明允许的用途")

    # ④ 不得转售
    add("调用方承诺不得转售", bool(r.get("no_resale")),
        "已承诺" if r.get("no_resale") else "调用方未承诺不得转售")

    # ⑤ 金额上限
    cap = b.get("max_amount")
    over = False
    if cap is None:
        add("已声明金额上限", False, "没有声明金额上限")
    else:
        try:
            amount = float(r.get("amount"))
        except (TypeError, ValueError):
            add("金额可读", False, "缺少金额或金额不是数字")
        else:
            over = amount > float(cap)
            # 超上限**不是拒绝理由**（设计口径：超限 → 需本人确认），所以它不阻断放行
            checks.append({"check": "金额未超过上限", "ok": not over, "blocking": False,
                           "detail": f"本次 {amount:g}；上限 {float(cap):g}"
                                     + (f"（超出 {amount - float(cap):g}）" if over else "")})

    blocking = [c for c in checks if c.get("blocking", True)]     # 只有阻断项决定放不放行
    if not all(c["ok"] for c in blocking):
        result, note = "deny", "有检查项未通过，默认拒绝。"
    elif over:
        result, note = "confirm", "金额超过你设定的上限，需要你本人确认后才放行。"
    else:
        result, note = "allow", "在授权范围内，可以调用。"

    return {"result": result, "note": note, "checks": checks, "over_limit": over}
