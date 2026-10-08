"""要件逻辑模型验收（requirements_v1）：结论来自"哪条规则的要件成立"。

    ~/personal-ontology/.venv/bin/python tests/test_requirements_model.py
"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import engine
from backend.models.requirements_v1 import eval_expression, tokenize

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

# ── 表达式求值 ──
hit = {"A": True, "B": True, "C": False, "D": False, "E": True}
check("且", eval_expression("A 且 B", hit)[0] is True)
check("或", eval_expression("C 或 D", hit)[0] is False)
check("非", eval_expression("非 E", hit)[0] is False)
check("括号改变结合", eval_expression("(A 或 C) 且 非 D", hit)[0] is True)
check("嵌套：A 且 B 且 (C 或 D) 且 非 E", eval_expression("A 且 B 且 (C 或 D) 且 非 E", hit)[0] is False)
check("英文写法 and/or/not", eval_expression("A and B and not E", hit)[0] is False)
check("认不出的要件名会被报出来", eval_expression("A 且 不存在", hit)[1] == ["不存在"])

# ── 合同效力样例 ──
FW = {
  "model": "requirements_v1",
  "inputs": [{"name": "当事人具备行为能力"}, {"name": "意思表示真实"},
             {"name": "标的合法"}, {"name": "已履行登记"}],
  "signals": [
    {"name": "有能力", "when": {"当事人具备行为能力": {"op": "eq", "value": "是"}}},
    {"name": "意思真实", "when": {"意思表示真实": {"op": "eq", "value": "是"}}},
    {"name": "标的合法", "when": {"标的合法": {"op": "eq", "value": "是"}}},
    {"name": "已登记", "when": {"已履行登记": {"op": "eq", "value": "是"}}},
  ],
  "combination_rules": [
    {"expr": "有能力 且 意思真实 且 标的合法 且 非 已登记", "conclusion": "成立但未生效（需登记）", "severity": "中"},
    {"expr": "有能力 且 意思真实 且 标的合法 且 已登记", "conclusion": "成立且生效", "severity": "低"},
    {"expr": "非 标的合法", "conclusion": "无效", "severity": "高"},
  ],
  "citations": [{"text": "某法第一百四十三条", "signals": ["有能力", "意思真实"]}],
  "fallback": {"conclusion": "需人工复核", "severity": "中"},
}
D_OK = {"当事人具备行为能力": "是", "意思表示真实": "是", "标的合法": "是", "已履行登记": "是"}
D_NOREG = dict(D_OK, **{"已履行登记": "否"})
D_ILLEGAL = dict(D_OK, **{"标的合法": "否"})

pkg = engine.judge(FW, D_OK)
# 第 1 条含「非 已登记」，而已登记=是 → 它本就不成立；所以全部成立时命中的是第 2 条。
check("含「非 已登记」的规则在已登记时不成立 → 命中第 2 条",
      pkg.get("decision") == "成立且生效", str(pkg.get("decision")))
check("判定包记下模型与版本", pkg.get("model") == "requirements_v1" and pkg.get("model_version") == "1")
check("不做加权求和（score 为 None）", pkg.get("score") is None, str(pkg.get("score")))
check("给出成立与未成立的要件清单",
      isinstance(pkg.get("satisfied_requirements"), list) and isinstance(pkg.get("failed_requirements"), list))
check("命中的规则会被引用（rule_cited）", bool(pkg.get("rule_cited")))
check("依据在相关要件成立时附上", "某法第一百四十三条" in (pkg.get("basis") or []), str(pkg.get("basis")))

# 顺序优先：把「已登记」那条放最前，则全部成立时就用它
FW2 = dict(FW); FW2["combination_rules"] = [FW["combination_rules"][1], FW["combination_rules"][0]]
check("规则按声明顺序取第一条成立", engine.judge(FW2, D_OK).get("decision") == "成立且生效")

p2 = engine.judge(FW, D_NOREG)
check("未登记时命中第一条（成立但未生效）", p2.get("decision") == "成立但未生效（需登记）", str(p2.get("decision")))
p3 = engine.judge(FW, D_ILLEGAL)
check("标的违法 → 无效（高）", p3.get("decision") == "无效" and p3.get("severity") == "高",
      "%s / %s" % (p3.get("decision"), p3.get("severity")))

# ── 约定 B：少一项不出结论 ──
p4 = engine.judge(FW, {k: v for k, v in D_OK.items() if k != "标的合法"})
check("少一项必需输入 → 信息不足，无法判断（约定 B）",
      p4.get("decision") == "信息不足，无法判断" and p4.get("missing_inputs") == ["标的合法"], str(p4.get("missing_inputs")))

# ── 兜底与无结论 ──
FW3 = dict(FW); FW3["combination_rules"] = [{"expr": "已登记 且 非 已登记", "conclusion": "不可能", "severity": "低"}]
check("没有规则成立 → 用兜底结论", engine.judge(FW3, D_OK).get("decision") == "需人工复核")
FW4 = dict(FW3); FW4["fallback"] = {}
check("没有兜底 → 无明确结论", engine.judge(FW4, D_OK).get("decision") == "无明确结论")

# ── validate：要件名写错、没有规则都要报 ──
FW5 = dict(FW); FW5["combination_rules"] = [{"expr": "有能力 且 臆造要件", "conclusion": "x", "severity": "低"}]
probs = engine.validate(FW5)
check("要件名不在信号里 → 明确提示（不静默）", any("臆造要件" in x.get("reason", "") for x in probs), str(probs)[:140])
check("没有规则 → 提示只能落到兜底",
      any("没有规则" in x.get("reason", "") for x in engine.validate({"model": "requirements_v1", "signals": []})))

# ── 兼容：沿用 all_of 写法（等价于「且」）──
FW6 = {"model": "requirements_v1", "inputs": FW["inputs"], "signals": FW["signals"],
       "combination_rules": [{"all_of": ["有能力", "意思真实", "标的合法", "已登记"], "conclusion": "成立且生效", "severity": "低"}]}
check("沿用 all_of 写法等价于「且」", engine.judge(FW6, D_OK).get("decision") == "成立且生效")

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
