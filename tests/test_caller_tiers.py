"""调用方返回的档位分层：四档字段集合、无泄漏、以及测试用的"只降不升"覆盖。

    ~/personal-ontology/.venv/bin/python tests/test_caller_tiers.py
"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.models.scorecard_v1 import for_caller, CALLER_TIER_FIELDS, CALLER_TIER_ORDER

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

PKG = {"decision": "风险极高，建议终止", "severity": "极高", "score": 0.725, "basis": ["《民法典》物权编"],
       "signals": {"权属瑕疵": True}, "reasoning_path": [{"step": 1, "name": "行业分类", "detail": "权重 0.4"}],
       "confidence": "依据充分", "confidence_status": "unverified",
       "evidence": [{"factor": "市盈率", "value": 46, "source": "调用方提供", "note": "作者的话"}],
       "required_inputs": ["行业"], "missing_inputs": [], "weights": {"法律": 0.4}, "thresholds": {"base": 1.2},
       "combination_rules": [{"all_of": ["权属瑕疵"]}], "model": "scorecard_v1", "model_version": "1"}
v = {t: for_caller(PKG, t) for t in CALLER_TIER_ORDER}
check("basic 只有结论四件套 + tier", set(v["basic"]) == {"decision", "severity", "score", "confidence_status", "tier"}, str(sorted(v["basic"])))
check("standard 加依据与必填/缺项，无信号/证据/推理", {"basis", "required_inputs", "missing_inputs"} <= set(v["standard"]) and not ({"signals", "evidence", "reasoning_steps"} & set(v["standard"])), str(sorted(v["standard"])))
check("professional 有信号/置信度/证据/推理", {"signals", "confidence", "evidence", "reasoning_steps"} <= set(v["professional"]), str(sorted(v["professional"])))
check("audit 加模型身份", {"model", "model_version"} <= set(v["audit"]), str(sorted(v["audit"])))
for t in CALLER_TIER_ORDER:
    blob = str(v[t])
    check("%s 不含作者资产" % t, not [b for b in ("weights", "thresholds", "combination_rules", "industry_weights") if b in blob])
    check("%s 不含作者数字与措辞" % t, not [w for w in ("0.4", "1.2", "1.76", "权重", "作者的话") if w in blob])
check("不传档位＝professional（兼容）",
      {k: x for k, x in for_caller(PKG).items() if k != "tier"} == {k: x for k, x in v["professional"].items() if k != "tier"})
check("未知档位回落 professional", for_caller(PKG, "乱写").get("tier") == "professional")
ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
