import pathlib
import asyncio, json, os, sys, tempfile, shutil
work=tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"]=work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
A={"title":"订酒店","facts":[],"questions":[],"scope":{"mode":"global"},"resource_types":[{"name":"酒店"}],
 "actions":[{"name":"预订酒店"}],
 "required_inputs":[{"name":"budget_per_night","label":"每晚预算","type":"number","required":True,"role":"both","role_reason":"既有上限立场又是本次金额"},
                    {"name":"check_in_date","label":"入住日期","type":"date","required":True,"role":"required","role_reason":"日期每次不同"}],
 "policies":[{"subject":"我（待选择主体）","resource":"酒店","effect":"allow","actions":["预订酒店"],
   "conditions":[{"field":"budget_per_night","operator":"lte","value":400},
                 {"field":"check_in_date","operator":"equals","value":"2026-11-01"}]}]}
async def main():
    st,pl=await call("POST","/v1/setup",body={"password":"Both-Tier-94!"}); token=pl["token"]
    st,pl=await call("POST","/v1/principals",body={"principal_type":"person","display_name_zh":"本人"},token=token); pid=pl["id"]
    await call("POST","/v1/scenario-slices",body={"original_text":"订酒店","status":"analyzed","analysis":A,"updated_at":"2026-01-01T00:00:00Z"},token=token)
    st,pl=await call("GET","/v1/scenario-slices",token=token); sid=pl["items"][0]["id"]
    prefs=[{"field":"budget_per_night","label":"每晚预算","type":"number","value":400,"operator":"lte"}]
    st,pl=await call("POST","/v1/scenario-slices/confirm",body={"scenario_id":sid,"grantor_id":pid,"grantee_id":pid,
        "segmentation":{"mode":"global","dimensions":[],"global_preferences":prefs,"variants":[]}},token=token)
    check("确认成功（兼有字段不再被剔除）", st==200, f"HTTP {st} {str(pl)[:120]}")
    st,g=await call("GET",f"/v1/scenario-slices/{sid}",token=token)
    saved=(g.get("analysis") or {}).get("segmentation",{}).get("global_preferences") or []
    check("兼有字段作为偏好被保留", any(x["field"]=="budget_per_night" for x in saved), str(saved)[:150])
    st,pl=await call("GET","/v1/authorizations",token=token); aid=pl["items"][0]["id"]
    st,pl=await call("GET",f"/v1/authorizations/{aid}",token=token)
    types={}
    for cid in pl["constraints"]:
        st,c=await call("GET",f"/v1/constraints/{cid}",token=token)
        v=c.get("constraint_value")
        v=json.loads(v) if isinstance(v,str) else v
        types[v.get("key")]=c["constraint_type"]
    print("  约束类型:", types)
    check("兼有字段：立场条件保留（numeric_lte）", types.get("budget_per_night")=="numeric_lte", str(types))
    check("纯必填字段：降级为只要求提供（context_exists）", types.get("check_in_date")=="context_exists", str(types))
    p=sum(1 for ok,_ in RESULTS if ok); print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok,l in RESULTS:
        if not ok: print("  失败：",l)
asyncio.run(main()); shutil.rmtree(work,ignore_errors=True)
