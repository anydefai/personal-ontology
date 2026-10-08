"""MCP 目录的行为验收（用打桩的后端把目录真跑一遍，而不是只搜源码）。

要证明三件事：
  1. 生活侧场景的 required_inputs / preferences 会真的带出来（智能体据此知道该问什么）
  2. 专业切片会带上 kind=professional 与完整调用说明（要传什么、怎么调）
  3. 两者都【不含】框架/权重/阈值（设计文档第七步）

    ~/personal-ontology/.venv/bin/python tests/test_mcp_catalog_behavior.py
"""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import backend.mcp_server as m

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

HOTEL = {"id": "scene_hotel", "status": "confirmed", "scenario_profile": {"kind": "daily"},
         "analysis": {"title": "预订酒店", "intent": "订酒店",
                      "required_inputs": [{"name": "destination_city", "label": "目标城市", "required": True},
                                          {"name": "check_in", "label": "入住日期", "required": True}],
                      "instance_preferences": [{"field": "budget_per_night", "label": "每晚价格上限", "value": 300}],
                      "facts": [{"name": "budget_per_night", "value": 300}],
                      "segmentation": {"mode": "global", "dimensions": [], "variants": [],
                                       "global_preferences": [{"field": "budget_per_night", "value": 300}]},
                      "resource_types": ["酒店"], "actions": ["查询酒店", "预订酒店"], "policies": []}}
PRO = {"id": "slice_pro", "status": "confirmed", "scenario_profile": {"kind": "professional"},
       "framework": {"inputs": [{"name": "行业"}],
                     "industry_weights": {"科技": {"技术": 0.5}},
                     "thresholds": {"base": 1.3, "adjustments": [{"delta": 0.2}]},
                     "signals": [{"name": "s", "dimension": "技术"}],
                     "combination_rules": [{"all_of": ["s"], "conclusion": "偏高"}],
                     "billing": {"unit_price": 200, "currency": "CNY"}},
       "analysis": {"title": "并购估值"}}
CONTRACT = {"slice_id": "slice_pro", "title": "并购估值", "enabled": True,
            "how_to_call": {"method": "POST", "path": "/v1/scenario-slices/slice_pro/judge"},
            "fields": [{"name": "行业", "type": "string", "required": True}],
            "all_fields_required": True, "on_missing": "少任何一项都返回信息不足",
            "allowed_purposes": ["估值"], "max_amount": 1000000, "no_resale_required": True,
            "you_will_receive": ["decision"], "billing": {"unit_price": 200, "currency": "CNY"}}

class Stub(m.MCPServer):
    def __init__(self, slices, contract=None):
        super().__init__()
        self._slices, self._contract = slices, contract or CONTRACT
        self.calls = []
    def _api(self, method, path, body=None):
        self.calls.append((method, path))
        if path == "/v1/resource-types": return {"items": [{"id": "hotel"}]}
        if path == "/v1/actions": return {"items": [{"id": "book"}]}
        if path == "/v1/scenario-slices": return {"items": self._slices}
        if path.endswith("/contract"): return self._contract
        if path.endswith("/judge"): return {"judgment": {"decision": "偏高"}, "decision_id": "d1"}
        return {}
    def _write_session(self, name): pass

srv = Stub([HOTEL, PRO])
out = srv._call_tool("get_governance_catalog", {})
items = {x["id"]: x for x in out["scenario_instances"]}

check("生活侧场景带出 required_inputs（智能体据此知道该问什么）",
      len(items["scene_hotel"].get("required_inputs") or []) == 2, str(items["scene_hotel"].get("required_inputs"))[:80])
check("生活侧场景带出 preferences", len(items["scene_hotel"].get("preferences") or []) >= 1)
check("专业切片标注 kind=professional 与中文标签",
      items["slice_pro"].get("kind") == "professional" and items["slice_pro"].get("kind_label") == "专业技能场景")
prof = items["slice_pro"].get("professional") or {}
check("专业切片带出完整调用说明（字段/必填/怎么调）",
      bool(prof.get("fields")) and prof.get("all_fields_required") is True and "judge" in json.dumps(prof.get("how_to_call"), ensure_ascii=False),
      json.dumps(prof, ensure_ascii=False)[:120])
blob = json.dumps(out, ensure_ascii=False)
leaked = [k for k in ("industry_weights", "thresholds", "combination_rules", "framework", "signals") if k in blob]
check("目录里【不含】框架/权重/阈值/组合规则（第七步）", not leaked, "泄露：" + str(leaked))
check("取说明走的是 contract 接口", any(p.endswith("/contract") for _, p in srv.calls), str(srv.calls))

r = srv._call_tool("judge_professional_slice", {"slice_id": "slice_pro", "data": {"行业": "x"},
                                                "request": {"caller": "A", "purpose": "估值", "amount": 1, "no_resale": True}})
check("judge 工具能把判定包返回给智能体", (r.get("judgment") or {}).get("decision") == "偏高", json.dumps(r, ensure_ascii=False)[:120])

srv2 = Stub([PRO], contract={**CONTRACT, "enabled": False})
try:
    srv2._call_tool("judge_professional_slice", {"slice_id": "slice_pro"})
    check("未启用时明确拒绝", False, "居然放行了")
except RuntimeError as exc:
    check("未启用时明确拒绝并告知去控制台启用", "确认并启用" in str(exc), str(exc)[:90])

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
