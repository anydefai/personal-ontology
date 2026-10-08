"""判定模型策略参数化验收：命中分值 · 阈值乘法（默认值必须等于今天的算法）。

    ~/personal-ontology/.venv/bin/python tests/test_model_policies.py
"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import engine
from backend.models.scorecard_v1 import compute_threshold

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

FW = {"model": "scorecard_v1",
      "inputs": [{"name": "行业"}, {"name": "市盈率", "type": "number"}, {"name": "客户集中度", "type": "number"}],
      "industry_map": {"新能源": "科技"},
      "industry_weights": {"科技": {"财务": 0.4, "市场": 0.3}},
      "thresholds": {"base": 1.3, "adjustments": [{"condition": {"行业周期位置": "上升期"}, "delta": 0.15}]},
      "signals": [{"name": "贵", "dimension": "财务", "when": {"市盈率": {"op": "gt", "value": 43.5}}},
                  {"name": "集中", "dimension": "市场", "when": {"客户集中度": {"op": "gt", "value": 50}}}],
      "score_bands": {"high": {"min": 0.5, "conclusion": "偏高", "severity": "高"}},
      "fallback": {"conclusion": "中性", "severity": "中"}}
DATA = {"行业": "新能源", "市盈率": 45, "客户集中度": 65}

p0 = engine.judge(FW, DATA)
check("不写命中分值 → 分数 = 0.4 + 0.3 = 0.7（与今天完全一致）",
      abs(float(p0.get("score") or 0) - 0.7) < 1e-9, str(p0.get("score")))

FW2 = {**FW, "signals": [FW["signals"][0], {**FW["signals"][1], "score_value": 0.5}]}
check("命中分值 0.5 → 分数 = 0.4 + 0.3×0.5 = 0.55",
      abs(float(engine.judge(FW2, DATA).get("score") or 0) - 0.55) < 1e-9,
      str(engine.judge(FW2, DATA).get("score")))

FW3 = {**FW, "signals": [FW["signals"][0], {**FW["signals"][1], "score_value": 0}]}
p3 = engine.judge(FW3, DATA)
check("命中分值 0 → 分数 0.4；信号仍算命中（只是不加分）",
      abs(float(p3.get("score") or 0) - 0.4) < 1e-9 and p3.get("signals", {}).get("集中") is True,
      str(p3.get("score")) + " / " + str(p3.get("signals")))

th_plain, steps_plain = compute_threshold(FW, {**DATA, "行业周期位置": "上升期"})
check("阈值：只有 delta → 1.3 + 0.15 = 1.45（与今天一致）", abs(th_plain - 1.45) < 1e-9, str(th_plain))
check("阈值步骤不重复计数（基准 + 1 条调整 = 2 步）", len(steps_plain) == 2, str(steps_plain))

FW4 = {**FW, "thresholds": {"base": 1.3, "adjustments": [{"condition": {"行业周期位置": "上升期"}, "factor": 1.2}]}}
th_mul, steps_mul = compute_threshold(FW4, {**DATA, "行业周期位置": "上升期"})
check("阈值：×1.2 → 1.3 × 1.2 = 1.56", abs(th_mul - 1.56) < 1e-9, str(th_mul))
check("阈值步骤里带 factor 的恰好一条", sum(1 for s in steps_mul if s.get("factor") is not None) == 1, str(steps_mul))

FW5 = {**FW, "thresholds": {"base": 1.0, "adjustments": []}}
check("没有调整项时阈值就是基准值（1.0）", abs(compute_threshold(FW5, DATA)[0] - 1.0) < 1e-9)

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
