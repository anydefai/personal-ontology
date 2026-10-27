"""智能体进圈后可被"给圈授权"命中：这是圈与智能体联动的核心验证。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
from backend import api
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "AgentCircle-11!"}); tk = pl["token"]
    # 主人 + 两个智能体
    for pid, typ in (("p_owner","person"), ("agent_buddy","agent"), ("agent_other","agent")):
        await call("POST", "/v1/principals", token=tk, body={"principal_id":pid,"principal_type":typ,"display_name_zh":pid,"display_name_en":pid})
    st, c = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"代理","circle_type":"work"})
    cid = c["id"]
    st1, mb = await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"WorkBuddy","principal_id":"agent_buddy","member_kind":"agent"})
    check("智能体作为成员加入圈", st1 == 201 and (mb or {}).get("principal_id") == "agent_buddy", (st1, mb))
    check("成员类型记为 agent", (mb or {}).get("member_kind") == "agent", (mb or {}).get("member_kind"))
    await call("POST", "/v1/resource-types", token=tk, body={"type_name":"hotel","display_name_zh":"酒店","display_name_en":"Hotel","matcher_id":"glob","default_priority":0,"is_builtin":False})
    await call("POST", "/v1/actions", token=tk, body={"action_id":"book","display_name_zh":"预订","display_name_en":"Book","applies_to":"hotel","risk_level":"medium"})
    api.store.put("authorizations", "rule_circle_agent", {
        "grantor_id":"p_owner","grantee_id":cid,"grantee_kind":"circle","resource_type_id":"hotel",
        "resource_pattern":"*","pattern_type":"glob","actions":["book"],"effect":"allow","priority":0,
        "constraints":[],"source":"test","term":"permanent","revoked":False,
        "created_at":"2026-10-27T00:00:00Z","policy_status":"active"}, create_only=True)
    async def ev(pid):
        s, out = await call("POST", "/v1/decisions/evaluate", token=tk,
            body={"principal_id":pid,"resource_type_id":"hotel","action_id":"book","resource_id":"hotel_1","phase":"pre_planning"})
        return s, str((out or {}).get("result_id") or (out or {}).get("detail"))
    stA, rA = await ev("agent_buddy")
    check("圈里的智能体被放行", stA == 200 and rA == "allow", (stA, rA))
    stB, rB = await ev("agent_other")
    check("圈外的智能体被拒绝", stB == 200 and rB in ("deny","ask"), (stB, rB))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
