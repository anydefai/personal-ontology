"""场景分析契约校验自检。

    ~/personal-ontology/.venv/bin/python tests/test_analysis_contract.py

覆盖 docs/09 记录的五类模型行为陷阱，确保它们**能被自动抓到**而不是只能靠推演发现。
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend.analysis_contract import validate_analysis

RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(f"  {'✔' if ok else '✗'} {label}" + (f" — {detail}" if detail else ""))

def codes(analysis):
    return {n["code"] for n in validate_analysis(analysis)}

def base(**over):
    a = {"title": "订酒店", "resource_types": [{"name": "酒店"}], "actions": [{"name": "预订"}, {"name": "取消"}],
         "required_inputs": [{"name": "city", "label": "城市", "role": "required"}],
         "facts": [{"name": "budget", "label": "预算", "value": 400, "role": "preference"}],
         "policies": [{"effect": "allow", "resource": "酒店", "actions": ["预订"], "conditions": [{"field": "budget", "operator": "lte", "value": 400}]}]}
    a.update(over); return a

check("合规的分析没有说明", not validate_analysis(base()), str(validate_analysis(base())))

a = base(policies=[{"effect": "allow", "conditions": []}]); c = codes(a)
check("陷阱1：策略缺 actions 被抓到", "policy_missing_actions" in c, str(c))

a = base(policies=[{"effect": "allow", "actions": ["预订"], "conditions": []},
                   {"effect": "deny", "actions": ["取消"], "conditions": []}]); c = codes(a)
check("陷阱2：无条件 deny 被抓到", "policy_unconditional_deny" in c, str(c))

a = base(policies=[{"effect": "allow", "actions": ["删除文件"], "conditions": []}]); c = codes(a)
check("陷阱3：策略引用了不存在的动作被抓到", "policy_unknown_action" in c, str(c))

a = base(required_inputs=[{"name": "city", "label": "城市"}, {"name": "日期", "label": "日期"}]); c = codes(a)
check("陷阱5：字段缺 role 被抓到", "field_missing_role" in c, str(c))
check("字段名非英文键被抓到", "field_bad_name" in c, str(c))

a = base(required_inputs=[{"name": "city", "label": "城市", "role": "both"}],
         facts=[{"name": "budget", "label": "预算", "value": 400, "role": "preference"}]); c = codes(a)
check("兼有却不在两个清单里被抓到", "both_not_in_both_lists" in c, str(c))

a = base(required_inputs=[{"name": "city", "label": "城市", "role": "required"},
                          {"name": "city", "label": "城市2", "role": "required"}]); c = codes(a)
check("重复字段名被抓到", "duplicate_field" in c, str(c))

a = base(resource_types=[], actions=[]); c = codes(a)
check("无资源类型/无动作被抓到", {"no_resource_types", "no_actions"} <= c, str(c))

check("非对象输入不崩溃", {n["code"] for n in validate_analysis(None)} == {"not_an_object"})

passed = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
for ok, label in RESULTS:
    if not ok: print("  失败：", label)
sys.exit(0 if passed == len(RESULTS) else 1)
