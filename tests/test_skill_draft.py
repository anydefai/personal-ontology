"""框架草稿生成验收（第一步+第二步）。

    ~/personal-ontology/.venv/bin/python tests/test_skill_draft.py

用桩替换模型调用，因此不依赖网络与真实数据；重点验证：
  · 归一化只保留框架的已知部分，未知字段一律丢弃（宁缺毋滥）
  · 描述过短要报错，不能拿一句话去生成框架
  · 未配置模型时**明确报错**，绝不返回伪造草稿
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
from backend import skill_draft

MODEL_REPLY = {
  "framework_version": "V2",
  "inputs": [{"name": "市盈率", "type": "number"}, {"name": "行业", "type": "string"}, {"bad": 1}],
  "industry_map": {"新能源": "科技/互联网"},
  "industry_weights": {"科技/互联网": {"tech": 0.35, "oops": "不是数字"}},
  "thresholds": {"base": 1.3, "adjustments": [{"condition": {"行业周期位置": "上升期"}, "delta": 0.15,
                                               "reason": "上升期可容忍更高溢价"}]},
  "signals": [{"name": "市盈率超阈值", "when": {"市盈率": {"op": "gt", "value": 39}}}, {"没有名称": 1}],
  "combination_rules": [{"all_of": ["市盈率超阈值"], "conclusion": "估值偏高", "severity": "高"},
                        {"all_of": "不是数组", "conclusion": "应被丢弃"}],
  "exception_rules": [{"condition": {"all_signals": ["市盈率超阈值"]},
                       "override": {"kind": "adjust_threshold", "factor": 1.2}, "reason": "高增长"}],
  "signal_priority": [{"signal": "市盈率超阈值", "priority": 1}],
  "未知部分": {"不该保留": True},
}

# ── 纯逻辑 ──
fw = skill_draft.normalize(MODEL_REPLY)
check("保留输入定义（丢弃缺 name 的项）", len(fw["inputs"]) == 2, str(fw["inputs"]))
check("权重表丢弃非数字值", "oops" not in fw["industry_weights"]["科技/互联网"], str(fw["industry_weights"]))
check("信号只保留有名称且有 when 的", len(fw["signals"]) == 1, str(fw["signals"]))
check("组合规则丢弃 all_of 非数组的", len(fw["combination_rules"]) == 1, str(fw["combination_rules"]))
check("未知部分不保留", "未知部分" not in fw, str(list(fw)))
check("调整记录初始为空（等专家逐项调整）", fw["adjustment_log"] == [], str(fw["adjustment_log"]))

result = skill_draft.draft("我判断并购估值时会先分行业，再按行业周期调整阈值。" * 2, caller=lambda text: MODEL_REPLY)
check("草稿返回框架与说明", isinstance(result.get("framework"), dict) and "草稿" in result.get("notes", ""),
      str(result.get("notes"))[:60])
try:
    skill_draft.draft("太短", caller=lambda text: MODEL_REPLY)
    check("描述过短应报错", False, "没有报错")
except skill_draft.DraftError as exc:
    check("描述过短明确报错", "描述太短" in str(exc), str(exc))

# ── 经接口（临时数据目录，模型未配置 → 必须明确报错，不能伪造草稿）──
async def api_part():
    st, pl = await call("POST", "/v1/setup", body={"password": "Draft-94!"}); token = pl["token"]
    # 测试自建场景（不依赖内置种子：内置场景已按用户要求删除）
    for _sid, _zh in (("test.scenario", "测试场景"), ("test.scenario2", "测试场景二")):
        await call("POST", "/v1/scenario-definitions", body={
            "id": _sid, "display_name_zh": _zh, "display_name_en": _zh,
            "domain_pack_ids": ["legal.cn"], "version": "1.0.0",
            "lifecycle_state": "active", "is_builtin": False}, token=token)
    st, r = await call("POST", "/v1/scenario-definitions/legal.nope/draft",
                       body={"description": "我判断并购估值时会先分行业，再按行业周期调整阈值。"}, token=token)
    check("定义不存在 → 404", st == 404, f"HTTP {st}")
    st, r = await call("POST", "/v1/scenario-definitions/test.scenario/draft",
                       body={"description": "太短"}, token=token)
    check("描述过短 → 422", st == 422, f"HTTP {st}")
    st, r = await call("POST", "/v1/scenario-definitions/test.scenario/draft",
                       body={"description": "我判断并购估值时会先分行业，再按行业周期调整阈值。"}, token=token)
    check("未配置模型 → 503 明确报错（不返回伪造草稿）",
          st == 503 and "模型" in json.dumps(r, ensure_ascii=False), f"HTTP {st} {str(r)[:140]}")

asyncio.run(api_part())

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
