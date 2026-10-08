"""大段写入验收：整篇按小节切分 + 对外三段（边界/交付/计费）解析。

    ~/personal-ontology/.venv/bin/python tests/test_line_document.py
"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import line_format as L

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

DOC = """【我的依据】
反垄断法第二十六条
【判断的基准线】
基准 1.3
监管环境=收紧 → -0.10
【需要调用方提交的信息】
市盈率 ｜ 数字
现金流状况 ｜ 选项 ｜ 健康、紧张、危机
【我观察什么】
现金流危机 = 现金流状况 等于 危机
【几个观察点一起出现时】
现金流危机 → 估值偏高（高）
【例外情况】
技术已专利化 且 技术壁垒极高 → 团队流失权重 ×0.5
【哪个更重要】
现金流危机 > 团队流失高
【打分线】
打分 0.5 以上 → 估值偏高（高）
其余 → 估值中性（中）
【对外调用的边界】
金额上限 1000000
允许用途 估值、尽调
不得转售
【对外交付时附上的说明】
强在哪：还看行业与周期
资历：执业 15 年
档位：audit
有效期：30 天
【计费（演示）】
每次 200 CNY"""

texts, errs = L.split_document(DOC)
check("整篇被切成 11 个小节", len(texts) == 11, "切出：" + str(sorted(texts)))
check("切分没有报错", not errs, str(errs)[:120])
check("小节顺序无关：标题能认出来", set(texts) == {"inputs", "thresholds", "signals", "rules", "exceptions",
      "priority", "citations", "score", "boundaries", "delivery", "billing"}, str(sorted(texts)))

out = L.apply_lines({}, texts)
fw, rep = out["framework"], out["report"]
check("各区都有导入（无错误行）", all(not v["errors"] for v in rep.values()),
      {k: v["errors"] for k, v in rep.items() if v["errors"]})
check("需要调用方提交的信息 → inputs（2 项，选项被切出来）",
      len(fw.get("inputs") or []) == 2 and fw["inputs"][1].get("values") == ["健康", "紧张", "危机"], str(fw.get("inputs"))[:140])
check("对外调用的边界 → max_amount / allowed_scenarios / confidentiality",
      fw.get("boundaries") == {"max_amount": 1000000, "allowed_scenarios": ["估值", "尽调"], "confidentiality": "不得转售"},
      str(fw.get("boundaries")))
check("对外交付说明 → insight / 资历 / 档位 / 有效期（天数）",
      fw.get("delivery") == {"insight": "还看行业与周期", "owner_credentials": "执业 15 年",
                             "default_tier": "audit", "valid_days": 30}, str(fw.get("delivery")))
check("计费 → 单价与币种（价格来自用户输入）",
      fw.get("billing") == {"unit_price": 200, "currency": "CNY"}, str(fw.get("billing")))

texts2, errs2 = L.split_document("市盈率 ｜ 数字\n【判断的基准线】\n基准 1.3")
check("标题之前的内容会报错并提示补标题", len(errs2) == 1 and "小节标题" in errs2[0]["reason"], str(errs2)[:120])

texts3, _ = L.split_document("【认不出的标题】\n随便一行")
check("认不出的标题会报错而不是静默丢弃", not texts3 or "认不出" in str(_), str(texts3))

bad_doc = "【计费（演示）】\n每次 免费"
t4, _ = L.split_document(bad_doc)
o4 = L.apply_lines({}, t4)
check("写「免费/不计费」→ 不生成计费配置（软件不编价格）", not (o4["framework"].get("billing")), str(o4["framework"].get("billing")))

bad_doc2 = "【对外调用的边界】\n随便写一句"
t5, _ = L.split_document(bad_doc2)
o5 = L.apply_lines({}, t5)
check("边界里认不出的行会报错", bool(o5["report"]["boundaries"]["errors"]), str(o5["report"]["boundaries"]))

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
