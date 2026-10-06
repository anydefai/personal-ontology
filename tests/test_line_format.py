"""逐行输入格式验收。

    ~/personal-ontology/.venv/bin/python tests/test_line_format.py

最重要的一条：**用"一行一条"写出张律师那套并购估值框架 → 解析 → 判定**，
看能否得出与他文档一致的结果（估值偏高 / 高 / 阈值 1.45 / 43.5）。
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend.line_format import (apply_lines, parse_citations, parse_exceptions, parse_fallback,
                                 parse_inputs, parse_priority, parse_rules, parse_signals,
                                 parse_thresholds)
from backend.skill_framework import judge

RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(("  ✔ " if ok else "  ✗ ") + label + (f" — {detail}" if detail and not ok else ""))

# ── 宽容性 ──
ok, bad = parse_inputs(["市盈率 ｜ 数字", "", "# 注释行", "现金流  |  选项  |  健康, 紧张、危机  "])
check("输入定义：全角竖线/半角竖线/多余空格都认",
      len(ok) == 2 and ok[1]["values"] == ["健康", "紧张", "危机"] and not bad, str(ok))
ok, bad = parse_signals(["市盈率超阈值 = 市盈率 大于 行业平均市盈率 × 基准线"])
check("信号：识别「× 基准线」为与动态阈值比较",
      ok and ok[0]["when"]["市盈率"] == {"op": "gt", "value": {"ref": "行业平均市盈率", "times": "threshold"}}, str(ok))
ok, bad = parse_signals(["客户集中度>50 = 客户集中度 大于 50"])
check("信号：数值被解析为数字而非字符串", ok and ok[0]["when"]["客户集中度"]["value"] == 50, str(ok))
ok, bad = parse_priority(["现金流危机 > 团队流失高 > 市盈率超阈值"])
check("优先级：用 > 串起来 → 依次为 1/2/3",
      [x["priority"] for x in ok] == [1, 2, 3] and ok[0]["signal"] == "现金流危机", str(ok))
ok, bad = parse_exceptions(["技术已专利化 且 技术壁垒极高 → 团队流失权重 ×0.5",
                            "监管环境=收紧 且 行业=金融 → 直接判 估值偏高"])
check("例外：降权与直接判定都能识别",
      ok[0]["override"] == {"kind": "reduce_weight", "target": "团队流失", "factor": 0.5}
      and ok[1]["override"]["kind"] == "force_conclusion" and not bad, str(ok))

# ── 错误报告：只影响那一行 ──
ok, bad = parse_inputs(["市盈率 ｜ 数字", "现金流 ｜ 看不懂的类型", "客户集中度 ｜ 数字"])
check("坏行被单独报出，好行照常导入",
      len(ok) == 2 and len(bad) == 1 and bad[0]["line"] == 2 and "不认识" in bad[0]["reason"],
      f"ok={len(ok)} bad={bad}")
ok, bad = parse_rules(["甲 且 乙 → 结论（高）"], ["甲"])
check("规则引用了没定义的信号 → 报错并指出名字",
      not ok and bad and "乙" in bad[0]["reason"], str(bad))
ok, bad = parse_thresholds(["基准 一点三"])
check("基准不是数字 → 报错", not ok or ok, str(bad)) if False else check("基准不是数字 → 报错", bool(bad), str(bad))

# ── 第 7 部分「依据」与「兜底结论」──
ok, bad = parse_citations(["反垄断法第二十六条 → 团队流失高 且 现金流危机", "证券法第七十八条"])
check("依据：可带适用信号，也可不带（不带即始终附上）",
      ok[0] == {"text": "反垄断法第二十六条", "signals": ["团队流失高", "现金流危机"]}
      and ok[1] == {"text": "证券法第七十八条", "signals": []}, str(ok))
ok, bad = parse_fallback(["都不命中 → 估值合理（低）"])
check("兜底结论：解析出结论与严重度", ok == {"conclusion": "估值合理", "severity": "低"}, str(ok))

_fw = apply_lines({}, {"signals": "团队流失高 = 核心团队流失风险 等于 高",
                       "rules": "团队流失高 → 估值偏高（高）",
                       "citations": "反垄断法第二十六条 → 团队流失高\n证券法第七十八条",
                       "fallback": "都不命中 → 估值合理（低）"})["framework"]
_hit = judge(dict(_fw), {"核心团队流失风险": "高"})
_miss = judge(dict(_fw), {"核心团队流失风险": "低"})
check("依据：条件命中时附上有条件的依据（且始终附上无条件的）",
      _hit["basis"] == ["反垄断法第二十六条", "证券法第七十八条"], str(_hit["basis"]))
check("依据：条件未命中时只附无条件的依据", _miss["basis"] == ["证券法第七十八条"], str(_miss["basis"]))
check("兜底：都不命中时给兜底结论（不再是无明确结论）",
      _miss["decision"] == "估值合理" and _miss["severity"] == "低", f"{_miss['decision']}/{_miss['severity']}")
check("没有兜底时仍回落为无明确结论",
      judge({"combination_rules": []}, {})["decision"] == "无明确结论", "回落失败")

# ── 闭环：张律师那套框架，用"一行一条"写出来 ──
T = {
"inputs": """市盈率 ｜ 数字
行业平均市盈率 ｜ 数字
营收增长率 ｜ 数字
客户集中度 ｜ 数字
行业 ｜ 文字
现金流状况 ｜ 选项 ｜ 健康、紧张、危机
技术壁垒 ｜ 选项 ｜ 极高、高、中、低
技术专利化程度 ｜ 选项 ｜ 已专利化、部分专利化、未专利化
核心团队流失风险 ｜ 选项 ｜ 高、中、低
竞业协议覆盖 ｜ 选项 ｜ 全覆盖、部分覆盖、无
行业周期位置 ｜ 选项 ｜ 上升期、平稳期、下行期
监管环境 ｜ 选项 ｜ 宽松、中性、收紧""",
"thresholds": """基准 1.3
行业周期位置=上升期 → +0.15
行业周期位置=下行期 → -0.15
监管环境=收紧 → -0.10
监管环境=宽松 → +0.10""",
"signals": """市盈率超阈值 = 市盈率 大于 行业平均市盈率 × 基准线
客户集中度>50 = 客户集中度 大于 50
客户集中度>70 = 客户集中度 大于 70
团队流失高 = 核心团队流失风险 等于 高
现金流危机 = 现金流状况 等于 危机
技术壁垒极高 = 技术壁垒 等于 极高
已专利化 = 技术专利化程度 等于 已专利化
竞业全覆盖 = 竞业协议覆盖 等于 全覆盖""",
"rules": """市盈率超阈值 且 客户集中度>50 且 团队流失高 → 估值偏高（高）
市盈率超阈值 且 技术壁垒极高 且 已专利化 → 估值可接受（低）
市盈率超阈值 且 团队流失高 且 竞业全覆盖 → 估值偏高但可控（中）
市盈率超阈值 且 现金流危机 → 估值偏高（高）
市盈率超阈值 且 客户集中度>70 且 现金流危机 且 团队流失高 → 估值严重偏高（极高）""",
"exceptions": """已专利化 且 技术壁垒极高 → 团队流失权重 ×0.5
行业周期位置=上升期 且 营收增长率 大于 50 → 基准线 ×1.2
监管环境=收紧 且 行业=金融 → 直接判 估值偏高""",
"priority": """现金流危机 > 团队流失高 > 客户集中度>70 > 市盈率超阈值""",
}
res = apply_lines({}, T)
errs = {k: v["errors"] for k, v in res["report"].items() if v["errors"]}
check("六个部分全部解析成功（无错误行）", not errs, str(errs))
fw = res["framework"]
check("输入定义 12 条", len(fw["inputs"]) == 12, str(len(fw["inputs"])))
check("阈值：基准 1.3 + 4 条调整", fw["thresholds"]["base"] == 1.3 and len(fw["thresholds"]["adjustments"]) == 4,
      str(fw["thresholds"]))
check("信号 8 条 · 组合规则 5 条 · 例外 3 条 · 优先级 4 条",
      (len(fw["signals"]), len(fw["combination_rules"]), len(fw["exception_rules"]), len(fw["signal_priority"])) == (8, 5, 3, 4),
      str((len(fw["signals"]), len(fw["combination_rules"]), len(fw["exception_rules"]), len(fw["signal_priority"]))))

CASE = {"行业": "新能源", "市盈率": 45, "行业平均市盈率": 30, "市销率": 8, "行业平均市销率": 5,
        "营收增长率": 35, "现金流状况": "紧张", "客户集中度": 65, "技术壁垒": "高",
        "技术专利化程度": "部分专利化", "核心团队流失风险": "高", "竞业协议覆盖": "部分覆盖",
        "行业周期位置": "上升期", "监管环境": "中性"}
out = judge(fw, CASE)
check("闭环：判定结论 = 估值偏高", out["decision"] == "估值偏高", str(out["decision"]))
check("闭环：严重度 = 高", out["severity"] == "高", str(out["severity"]))
check("闭环：动态阈值 = 1.45", abs(out["threshold"] - 1.45) < 1e-9, str(out["threshold"]))
check("闭环：市盈率 45 > 30×1.45=43.5 信号成立", out["signals"]["市盈率超阈值"] is True,
      str(out["signal_reasons"].get("市盈率超阈值")))
check("闭环：例外未命中（技术仅部分专利化）", not out["exceptions_applied"], str(out["exceptions_applied"]))

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
sys.exit(0 if p == len(RESULTS) else 1)
