"""技能框架执行器验收：用「张律师并购估值」的真实逻辑端到端跑一遍。

    ~/personal-ontology/.venv/bin/python tests/test_skill_framework.py

这个测试就是"框架能不能表达专业逻辑"的判据：
把用户给出的框架（行业权重 / 动态阈值 / 信号交叉验证 / 例外 override / 信号优先级）
与那一组标的（新能源 / 市盈率 45 / 客户集中度 65 / 现金流紧张 / 团队流失高 / 部分专利化 …）
原样编进来，期望跑出用户写的那个结论：**估值偏高，severity 高**。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.skill_framework import apply_tier, judge

RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(("  ✔ " if ok else "  ✗ ") + label + (f" — {detail}" if detail and not ok else ""))

FRAMEWORK = {
  "skill_id": "SKILL-MA-VALUATION-001", "skill_name": "并购估值判断",
  "framework_version": "JUDGMENT-FRAMEWORK-V2",
  "industry_map": {"新能源": "科技/互联网", "半导体": "科技/互联网", "机械制造": "传统制造", "生物医药": "医疗/生物"},
  "industry_weights": {
    "科技/互联网": {"tech": 0.35, "team": 0.25, "financial": 0.20, "market": 0.20},
    "传统制造": {"financial": 0.40, "team": 0.20, "market": 0.20, "tech": 0.20},
    "医疗/生物": {"tech": 0.40, "regulatory": 0.25, "team": 0.20, "financial": 0.15}},
  "thresholds": {"base": 1.3, "adjustments": [
    {"condition": {"行业周期位置": "上升期"}, "delta": 0.15, "reason": "上升期可容忍更高溢价"},
    {"condition": {"行业周期位置": "下行期"}, "delta": -0.15, "reason": "下行期要求更低估值"},
    {"condition": {"监管环境": "收紧"}, "delta": -0.10, "reason": "监管风险增加"},
    {"condition": {"监管环境": "宽松"}, "delta": 0.10, "reason": "监管友好"}]},
  "signals": [
    {"name": "市盈率超阈值", "when": {"市盈率": {"op": "gt", "value": {"ref": "行业平均市盈率", "times": "threshold"}}}},
    {"name": "客户集中度 > 50%", "when": {"客户集中度": {"op": "gt", "value": 50}}},
    {"name": "客户集中度 > 70%", "when": {"客户集中度": {"op": "gt", "value": 70}}},
    {"name": "团队流失风险 = 高", "when": {"核心团队流失风险": "高"}},
    {"name": "现金流 = 危机", "when": {"现金流状况": "危机"}},
    {"name": "技术壁垒 = 极高", "when": {"技术壁垒": "极高"}},
    {"name": "技术专利化程度 = 已专利化", "when": {"技术专利化程度": "已专利化"}},
    {"name": "竞业协议覆盖 = 全覆盖", "when": {"竞业协议覆盖": "全覆盖"}}],
  "combination_rules": [
    {"all_of": ["市盈率超阈值", "客户集中度 > 50%", "团队流失风险 = 高"], "conclusion": "估值偏高", "severity": "高"},
    {"all_of": ["市盈率超阈值", "技术壁垒 = 极高", "技术专利化程度 = 已专利化"], "conclusion": "估值可接受", "severity": "低"},
    {"all_of": ["市盈率超阈值", "团队流失风险 = 高", "竞业协议覆盖 = 全覆盖"], "conclusion": "估值偏高但可控", "severity": "中"},
    {"all_of": ["市盈率超阈值", "现金流 = 危机"], "conclusion": "估值偏高", "severity": "高"},
    {"all_of": ["市盈率超阈值", "客户集中度 > 70%", "现金流 = 危机", "团队流失风险 = 高"], "conclusion": "估值严重偏高", "severity": "极高"}],
  "exception_rules": [
    {"condition": {"all_signals": ["技术专利化程度 = 已专利化", "技术壁垒 = 极高"]},
     "override": {"kind": "reduce_weight", "target": "团队流失风险", "factor": 0.5},
     "reason": "技术已沉淀为专利，对团队依赖降低"},
    {"condition": {"conditions": {"行业周期位置": "上升期", "营收增长率": {"op": "gt", "value": 50}}},
     "override": {"kind": "adjust_threshold", "factor": 1.2}, "reason": "高增长可支撑更高估值"},
    {"condition": {"conditions": {"监管环境": "收紧", "行业": "金融"}},
     "override": {"kind": "force_conclusion", "conclusion": "估值偏高"}, "reason": "金融行业监管收紧是系统性风险"}],
  "signal_priority": [
    {"signal": "现金流 = 危机", "priority": 2}, {"signal": "团队流失风险 = 高", "priority": 3},
    {"signal": "客户集中度 > 70%", "priority": 4}, {"signal": "市盈率超阈值", "priority": 5}],
}

CASE = {"行业": "新能源", "市盈率": 45, "行业平均市盈率": 30, "市销率": 8, "行业平均市销率": 5,
        "营收增长率": 35, "现金流状况": "紧张", "客户集中度": 65, "技术壁垒": "高",
        "技术专利化程度": "部分专利化", "核心团队流失风险": "高", "竞业协议覆盖": "部分覆盖",
        "行业周期位置": "上升期", "监管环境": "中性"}

out = judge(FRAMEWORK, CASE, confidence=0.78, confidence_status="backtested",
            confidence_basis="基于50个历史案例回测，准确率78%")

check("结论为「估值偏高」", out["decision"] == "估值偏高", out["decision"])
check("严重度为「高」", out["severity"] == "高", out["severity"])
check("动态阈值 = 1.3 + 0.15 = 1.45", abs(out["threshold"] - 1.45) < 1e-9, out["threshold"])
check("推理路径为 6 步", len(out["reasoning_path"]) == 6, str(len(out["reasoning_path"])))
check("第 1 步做了行业分类（新能源 → 科技/互联网）",
      "科技/互联网" in out["reasoning_path"][0]["detail"], out["reasoning_path"][0]["detail"])
check("第 2 步写明基准与调整后的阈值",
      "1.45" in out["reasoning_path"][1]["detail"] and "上升期" in out["reasoning_path"][1]["detail"],
      out["reasoning_path"][1]["detail"][:90])
check("命中组合规则：市盈率超阈值 + 客户集中度>50% + 团队流失高",
      any(set(r["all_of"] or []) == {"市盈率超阈值", "客户集中度 > 50%", "团队流失风险 = 高"}
          for r in out["matched_rules"]), str(out["matched_rules"])[:120])
check("例外未命中（技术仅部分专利化）",
      not out["exceptions_applied"] and "无例外条件命中" in out["reasoning_path"][3]["detail"],
      out["reasoning_path"][3]["detail"])
check("市盈率超阈值信号成立（45 > 30×1.45=43.5）", out["signals"]["市盈率超阈值"] is True,
      str(out["signal_reasons"].get("市盈率超阈值")))
check("现金流=危机 信号不成立（本次为紧张）", out["signals"]["现金流 = 危机"] is False)
check("证据含动态阈值 43.5", any(e.get("dynamic_threshold") == "43.5" for e in out["evidence"]),
      str(out["evidence"])[:150])
check("置信度与来源透传", out["confidence"] == 0.78 and out["confidence_status"] == "backtested",
      f"{out['confidence']}/{out['confidence_status']}")
check("引用框架版本", out["rule_cited"] == "JUDGMENT-FRAMEWORK-V2", str(out["rule_cited"]))

# —— 失败场景：即使"监管收紧 + 金融"的例外成立，也应直接判定 ——
金融 = dict(CASE, 行业="金融", 监管环境="收紧")
out2 = judge(FRAMEWORK, 金融)
check("例外 override：监管收紧+金融 → 直接判定偏高",
      out2["decision"] == "估值偏高" and any("直接判定" in a for a in out2["exceptions_applied"]),
      f"{out2['decision']} / {out2['exceptions_applied']}")

# —— 安全：未注册操作符与缺失字段都不得命中 ——
BAD = dict(FRAMEWORK)
BAD["combination_rules"] = [{"all_of": ["怪信号"], "conclusion": "不该出现", "severity": "高"}]
BAD["signals"] = [{"name": "怪信号", "when": {"市盈率": {"op": "regex_match", "value": ".*"}}}]
out3 = judge(BAD, CASE)
check("未注册操作符不放行", out3["decision"] == "无明确结论", out3["decision"])
check("未注册操作符给出原因", "操作符未注册" in out3["signal_reasons"].get("怪信号", ""),
      out3["signal_reasons"].get("怪信号"))
MISS = dict(FRAMEWORK)
MISS["signals"] = [{"name": "缺字段信号", "when": {"不存在的字段": {"op": "gt", "value": 1}}}]
MISS["combination_rules"] = [{"all_of": ["缺字段信号"], "conclusion": "不该出现", "severity": "高"}]
out4 = judge(MISS, CASE)
check("缺失字段不放行", out4["decision"] == "无明确结论", out4["decision"])
check("缺失字段给出原因", "缺少字段" in out4["signal_reasons"].get("缺字段信号", ""),
      out4["signal_reasons"].get("缺字段信号"))

# ── 约定 B（用户选定）：声明在 inputs 里的字段都是调用方必须提供的；缺任何一项都不出结论 ──
_fw_b = {
    "inputs": [{"name": "a", "type": "number"}, {"name": "b", "type": "string"}],
    "thresholds": {"base": 1.3, "adjustments": []},
    "signals": [{"name": "s1", "when": {"a": {"op": "gt", "value": 10}}}],
    "combination_rules": [{"all_of": ["s1"], "conclusion": "偏高", "severity": "高"}],
}
_miss = judge(dict(_fw_b), {"a": 45})
check("B：缺必填就不出结论（不假装判断过）",
      _miss["decision"] == "信息不足，无法判断" and _miss["severity"] == "未判定",
      str(_miss["decision"]))
check("B：判定包同时给出输入契约与缺项",
      _miss["required_inputs"] == ["a", "b"] and _miss["missing_inputs"] == ["b"],
      str((_miss.get("required_inputs"), _miss.get("missing_inputs"))))
check("B：推理路径第 0 步说明缺什么",
      _miss["reasoning_path"][0]["name"] == "输入完整性检查" and "b" in _miss["reasoning_path"][0]["detail"],
      str(_miss["reasoning_path"][0]))
_ok_b = judge(dict(_fw_b), {"a": 45, "b": "x"})
check("B：给全了就正常出结论，且缺项为空",
      _ok_b["decision"] == "偏高" and _ok_b["missing_inputs"] == [] and _ok_b["required_inputs"] == ["a", "b"],
      f"{_ok_b['decision']}/{_ok_b['missing_inputs']}")
check("B：缺项信息不受层级过滤影响（basic 层也带）",
      "missing_inputs" in apply_tier(dict(_miss), "basic") and "required_inputs" in apply_tier(dict(_miss), "basic"))

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
sys.exit(0 if p == len(RESULTS) else 1)
