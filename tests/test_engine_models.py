"""判定引擎与模型验收：引擎不含算法、模型可注册、判定包只新增 model 与 model_version。

    ~/personal-ontology/.venv/bin/python tests/test_engine_models.py
"""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import engine, skill_framework as SF

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

# ① 引擎里不该有算法
src = (ROOT / "backend" / "engine.py").read_text(encoding="utf-8")
check("引擎文件里不含打分算法本身", "score +=" not in src and "weights.get" not in src, "引擎里出现了算法")
check("引擎有注册表与默认模型", "MODELS" in src and "DEFAULT_MODEL" in src)

# ② 注册表与模型接口
check("注册表里有 scorecard_v1", "scorecard_v1" in engine.MODELS)
m = engine.get_model({})
check("未声明 model 的切片取到默认模型", m.id == engine.DEFAULT_MODEL == "scorecard_v1", m.id)
check("模型带 id/version/标签/适用边界/不适用清单",
      all(bool(getattr(m, k, None)) for k in ("id", "version", "label_zh", "label_en", "applicable")) and bool(m.not_applicable))
for name in ("input_contract", "validate", "judge", "output_contract", "reasoning"):
    check("模型实现了 %s()" % name, callable(getattr(m, name, None)))

# ③ 判定包只新增两项，其余字段与拆分前一致（这里用冻结的字段清单核对）
FW = {"inputs": [{"name": "行业"}, {"name": "市盈率", "type": "number"}],
      "industry_map": {"新能源": "科技/互联网"},
      "industry_weights": {"科技/互联网": {"技术": 0.35, "团队": 0.25, "财务": 0.20, "市场": 0.20}},
      "thresholds": {"base": 1.3, "adjustments": [{"condition": {"行业周期位置": "上升期"}, "delta": 0.15}]},
      "signals": [{"name": "市盈率超阈值", "dimension": "财务", "when": {"市盈率": {"op": "gt", "value": 43.5}}},
                  {"name": "团队流失高", "dimension": "团队", "when": {"市盈率": {"op": "gt", "value": 1}}}],
      "combination_rules": [{"all_of": ["市盈率超阈值", "团队流失高"], "conclusion": "估值偏高", "severity": "高"}],
      "score_bands": {"high": {"min": 0.5, "conclusion": "估值偏高", "severity": "高"}},
      "fallback": {"conclusion": "估值中性", "severity": "中"}}
DATA = {"行业": "新能源", "市盈率": 45, "行业周期位置": "上升期"}
pkg = SF.judge(FW, DATA)
FROZEN = {"decision", "severity", "score", "basis", "evidence", "confidence", "confidence_status",
          "confidence_basis", "reasoning_path", "signals", "signal_reasons", "threshold",
          "matched_rules", "exceptions_applied", "rule_cited", "required_inputs", "missing_inputs",
          "model", "model_version"}
missing = sorted(FROZEN - set(pkg))
check("判定包含全部应有字段（含 model/model_version，无遗漏）", not missing, "缺：" + str(missing))
check("判定包盖上了模型名与版本", pkg.get("model") == "scorecard_v1" and pkg.get("model_version") == "1",
      "%s / %s" % (pkg.get("model"), pkg.get("model_version")))
check("结论与打分与拆分前一致（估值偏高 / 0.45）",
      pkg.get("decision") == "估值偏高" and abs(float(pkg.get("score") or 0) - 0.45) < 1e-9,
      "%s / %s" % (pkg.get("decision"), pkg.get("score")))

# ④ 静默风险要报出来（维度对不上 / 缺行业归类 / 信号没标维度）
p = engine.validate({"signals": [{"name": "s1", "dimension": "财务"}, {"name": "s2"}],
                     "industry_weights": {"甲": {"技术": 0.5}}})
reasons = " ".join(x.get("reason", "") for x in p)
check("信号没标维度 → 有提示", "没有标维度" in reasons, str(p)[:120])
check("维度名与权重表对不上 → 有提示", "按 0 分计" in reasons or "没有同名列" in reasons, str(p)[:160])
check("缺行业归类 → 有提示", "行业" in reasons, str(p)[:160])

# ⑤ 未知模型名回落到默认（老切片与写错的名字都不会炸）
check("未知 model 名回落到默认模型", engine.get_model({"model": "不存在"}).id == "scorecard_v1")

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
