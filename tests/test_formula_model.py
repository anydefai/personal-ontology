"""领域公式模型验收（formula_v1）：白名单表达式的解析与求值，安全边界。

    ~/personal-ontology/.venv/bin/python tests/test_formula_model.py
"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import engine
from backend.models.formula_v1 import FormulaError, evaluate

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

# ── 表达式求值 ──
v, used = evaluate("体重 * 系数 + round(2.345, 2)", {"体重": 10, "系数": 1.5}, {})
check("四则 + round", abs(float(v) - 17.35) < 1e-9, str(v))
check("能报出用到的字段", set(used) >= {"体重", "系数"}, str(used))
check("min/max/abs", evaluate("min(3, 5) + max(1, 2) + abs(-4)", {}, {})[0] == 9)
check("比较与布尔", evaluate("体重 > 10 and 非 体重 == 0", {"体重": 12}, {})[0] is True)
check("公式之间可互相引用", evaluate("甲 + 1", {}, {"甲": "2 * 3"})[0] == 7)
check("中文字段名与中文逻辑词可用", evaluate("体重 且 系数", {"体重": 1, "系数": 1}, {})[0] is True)

# ── 安全边界 ──
def rejects(expr, values=None, formulas=None):
    try:
        evaluate(expr, values or {}, formulas or {})
        return False
    except FormulaError:
        return True
check("拒绝属性访问", rejects("体重.__class__", {"体重": 1}))
check("拒绝下标/列表", rejects("体重[0]", {"体重": 1}))
check("拒绝未知字段", rejects("不存在的字段 + 1"))
check("拒绝超长公式", rejects("1+" * 300 + "1"))
check("除零会报错（不静默给 inf）", rejects("1 / 0"))
check("公式互相引用成环会报错", rejects("甲", {}, {"甲": "乙", "乙": "甲"}))
check("括号不闭合会报错", rejects("(1 + 2", {}))
check("函数参数个数不对会报错", rejects("min(1)", {}))

# ── 剂量样例（医疗）──
DOSE = {
  "model": "formula_v1",
  "inputs": [{"name": "体重"}, {"name": "肾功能系数"}],
  "formulas": {"剂量": "round(体重 * 肾功能系数, 1)"},
  "bands": [
    {"key": "高剂量", "min": 80, "conclusion": "按高剂量给药", "severity": "高"},
    {"key": "常规", "min": 20, "max": 80, "conclusion": "按常规剂量给药", "severity": "中"},
    {"key": "低剂量", "max": 20, "conclusion": "按低剂量给药", "severity": "低"},
  ],
  "citations": [{"text": "某用药指引第 4 条"}],
  "fallback": {"conclusion": "需药师复核", "severity": "中"},
}
pkg = engine.judge(DOSE, {"体重": 70, "肾功能系数": 0.5})
check("剂量样例：70 × 0.5 = 35 → 常规剂量", pkg.get("decision") == "按常规剂量给药", str(pkg.get("decision")))
check("判定包给出公式结果", pkg.get("formula_values", {}).get("剂量") == 35, str(pkg.get("formula_values")))
check("记下命中的分档", bool(pkg.get("band_cited")))
check("模型与版本被盖上", pkg.get("model") == "formula_v1" and pkg.get("model_version") == "1")
check("不做加权求和（score 为 None）", pkg.get("score") is None)
check("依据照旧附上", "某用药指引第 4 条" in (pkg.get("basis") or []))
check("高剂量分支", engine.judge(DOSE, {"体重": 90, "肾功能系数": 1.0}).get("decision") == "按高剂量给药")

# ── 折现样例（财务）──
DCF = {"model": "formula_v1", "inputs": [{"name": "现金流"}, {"name": "折现率"}],
       "formulas": {"现值": "现金流 / (1 + 折现率)"},
       "bands": [{"key": "达标", "min": 90, "conclusion": "现值达标", "severity": "低"},
                 {"key": "未达标", "max": 90, "conclusion": "现值未达标", "severity": "中"}],
       "fallback": {"conclusion": "需复核", "severity": "低"}}
check("折现样例：100 / 1.1 ≈ 90.9 → 达标", engine.judge(DCF, {"现金流": 100, "折现率": 0.1}).get("decision") == "现值达标")

# ── 约定 B 与报错路径 ──
check("少一项必需输入 → 信息不足（约定 B）",
      engine.judge(DOSE, {"体重": 70}).get("decision") == "信息不足，无法判断")
BAD = dict(DOSE); BAD["formulas"] = {"剂量": "体重 / 0"}
check("公式算不出来时明确报「公式无法计算」并给出原因",
      engine.judge(BAD, {"体重": 70, "肾功能系数": 0.5}).get("decision") == "公式无法计算")
probs = engine.validate({"model": "formula_v1", "inputs": [{"name": "体重"}], "formulas": {"x": "体重 * 不存在"}, "bands": []})
check("validate 会报未定义字段与缺分档", any("不存在" in x.get("reason", "") for x in probs) and any("没有分档" in x.get("reason", "") for x in probs), str(probs)[:160])

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
