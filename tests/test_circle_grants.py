"""按圈授权：grantee 写成圈 ID 时，圈内成员放行、圈外拒绝；圈同时在主体表里是一条 group 主体。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
from backend import api

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("  ✓ " if ok else "  ✗ ") + name + ((" — " + str(detail)[:160]) if detail and not ok else ""))

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Circle-Grant-11!"})
    tk = pl["token"]
    for pid, name in (("p_boss","老板"), ("p_member","同事甲"), ("p_outsider","圈外人")):
        await call("POST", "/v1/principals", token=tk, body={"principal_id":pid,"principal_type":"person","display_name_zh":name,"display_name_en":name})

    st, c = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"工作","circle_type":"work"})
    cid = c.get("id")
    check("建圈", st == 201 and cid, (st, c))
    st, gp = await call("GET", f"/v1/principals/{cid}", token=tk)
    check("圈同时在主体表里（group）", st == 200 and str((gp or {}).get("principal_type")) == "group", (st, gp))

    await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"同事甲","principal_id":"p_member"})
    await call("POST", "/v1/resource-types", token=tk, body={"type_name":"hotel","display_name_zh":"酒店","display_name_en":"Hotel","matcher_id":"glob","default_priority":0,"is_builtin":False})
    await call("POST", "/v1/actions", token=tk, body={"action_id":"book","display_name_zh":"预订","display_name_en":"Book","applies_to":"hotel","risk_level":"medium"})

    api.store.put("authorizations", "rule_circle_1", {
        "grantor_id":"p_boss","grantee_id":cid,"grantee_kind":"circle","resource_type_id":"hotel",
        "resource_pattern":"*","pattern_type":"glob","actions":["book"],"effect":"allow","priority":0,
        "constraints":[],"source":"test","term":"permanent","revoked":False,
        "created_at":"2026-10-20T00:00:00Z","policy_status":"active"}, create_only=True)

    async def ev(pid):
        s, out = await call("POST", "/v1/decisions/evaluate", token=tk,
            body={"principal_id":pid,"resource_type_id":"hotel","action_id":"book","resource_id":"hotel_1","phase":"pre_planning"})
        return s, str((out or {}).get("result_id") or (out or {}).get("detail"))

    st_a, r_a = await ev("p_member")
    check("圈内成员被放行", st_a == 200 and r_a == "allow", (st_a, r_a))
    st_b, r_b = await ev("p_outsider")
    check("圈外的人被拒绝", st_b == 200 and r_b in ("deny", "ask"), (st_b, r_b))

    await call("DELETE", f"/v1/circle-members/{ (await call('GET', f'/v1/circles/{cid}/members', token=tk))[1]['items'][0]['id'] }", token=tk)
    st_c, r_c = await ev("p_member")
    check("移出成员后立即失效", st_c == 200 and r_c in ("deny", "ask"), (st_c, r_c))

    st_d, dc = await call("DELETE", f"/v1/circles/{cid}", token=tk)
    check("还有规则指向圈时拒删（409 且说明条数）", st_d == 409, (st_d, dc))
    api.store.delete("authorizations", "rule_circle_1")
    st_d2, dc2 = await call("DELETE", f"/v1/circles/{cid}", token=tk)
    st_e, gp2 = await call("GET", f"/v1/principals/{cid}", token=tk)
    check("规则清掉后删圈，集体主体一并清理", st_d2 == 200 and (st_e == 404 or not gp2), (st_d2, st_e, gp2))

asyncio.run(main())
ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
