"""代理关系：智能体代表某人时，继承那个人所属圈的授权；判定结果说明"凭什么命中"。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
from backend import api
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:200]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "ActsFor-11!"}); tk = pl["token"]
    for pid, typ in (("p_owner","person"), ("agent_buddy","agent"), ("agent_other","agent")):
        await call("POST", "/v1/principals", token=tk, body={"principal_id":pid,"principal_type":typ,"display_name_zh":pid,"display_name_en":pid})
    st, c = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"家人","circle_type":"family"})
    cid = c["id"]
    await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"我","principal_id":"p_owner"})
    await call("POST", "/v1/resource-types", token=tk, body={"type_name":"hotel","display_name_zh":"酒店","display_name_en":"Hotel","matcher_id":"glob","default_priority":0,"is_builtin":False})
    await call("POST", "/v1/actions", token=tk, body={"action_id":"book","display_name_zh":"预订","display_name_en":"Book","applies_to":"hotel","risk_level":"medium"})
    api.store.put("authorizations", "rule_family", {
        "grantor_id":"p_owner","grantee_id":cid,"grantee_kind":"circle","resource_type_id":"hotel",
        "resource_pattern":"*","pattern_type":"glob","actions":["book"],"effect":"allow","priority":0,
        "constraints":[],"source":"test","term":"permanent","revoked":False,
        "created_at":"2026-10-27T00:00:00Z","policy_status":"active"}, create_only=True)
    async def ev(pid):
        s, out = await call("POST", "/v1/decisions/evaluate", token=tk,
            body={"principal_id":pid,"resource_type_id":"hotel","action_id":"book","resource_id":"hotel_1","phase":"pre_planning"})
        return s, out
    st0, r0 = await ev("agent_buddy")
    check("未设代理时，智能体被拒", r0.get("result_id") in ("deny","ask"), (st0, r0.get("result_id")))
    st1, out1 = await call("POST", "/v1/principals/agent_buddy/acts-for", token=tk, body={"represents":"p_owner"})
    check("设置代理成功", st1 == 200 and out1.get("acts_for") == "p_owner", (st1, out1))
    st2, r2 = await ev("agent_buddy")
    check("代表主人后继承家人的授权", r2.get("result_id") == "allow", (st2, r2.get("result_id")))
    check("命中方式可读（circle 或 acting_for）",
          (r2.get("reason_params") or {}).get("matched_via") in ("circle", "acting_for"), r2.get("reason_params"))
    # 直接给"人"授权时，代理应命中 acting_for
    api.store.put("authorizations", "rule_person", {
        "grantor_id":"p_owner","grantee_id":"p_owner","grantee_kind":"principal","resource_type_id":"hotel",
        "resource_pattern":"*","pattern_type":"glob","actions":["book"],"effect":"allow","priority":1,
        "constraints":[],"source":"test","term":"permanent","revoked":False,
        "created_at":"2026-10-27T00:00:00Z","policy_status":"active"}, create_only=True)
    st6, r6 = await ev("agent_buddy")
    check("给『人』的授权经代理命中 acting_for",
          r6.get("result_id") == "allow" and (r6.get("reason_params") or {}).get("matched_via") == "acting_for",
          r6.get("reason_params"))
    st3, r3 = await ev("agent_other")
    check("未设代理的其它智能体仍被拒", r3.get("result_id") in ("deny","ask"), (st3, r3.get("result_id")))
    st4, out4 = await call("POST", "/v1/principals/agent_buddy/acts-for", token=tk, body={"represents":""})
    st5, r5 = await ev("agent_buddy")
    check("清除代理后立刻失效", st4 == 200 and r5.get("result_id") in ("deny","ask"), (st5, r5.get("result_id")))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
