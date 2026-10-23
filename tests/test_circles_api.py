"""圈与圈成员：增删改查、级联删除、以及"只存关系不存对方资料"的边界。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("  ✓ " if ok else "  ✗ ") + name + ((" — " + str(detail)[:160]) if detail and not ok else ""))

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Circles-Test-11!"})
    tk = pl["token"]

    st, c1 = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"家人","circle_type":"family","my_role":"父亲"})
    check("建圈", st == 201 and c1.get("id"), (st, c1))
    st, c2 = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"工作","circle_type":"work","my_role":"下属"})
    check("再建一个圈（多圈）", st == 201 and c2.get("id"), (st, c2))
    st, bad = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"","circle_type":"work"})
    check("空名被拒", st == 422, (st, bad))
    st, bad2 = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"X","circle_type":"nonsense"})
    check("非法类型被拒", st == 422, (st, bad2))

    cid = c1["id"]
    st, m1 = await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"张三","member_role":"儿子","strength":"close"})
    check("加成员", st == 201 and m1.get("id"), (st, m1))
    st, m2 = await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"李四","strength":"distant","last_interaction_at":"2025-01-01T00:00:00Z"})
    check("再加一个成员", st == 201 and m2.get("id"), (st, m2))
    st, badm = await call("POST", "/v1/circles/circle_nope/members", token=tk, body={"display_name_zh":"王五"})
    check("往不存在的圈加人被拒", st == 404, (st, badm))
    st, badm2 = await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"王五","strength":"nonsense"})
    check("非法关系强度被拒", st == 422, (st, badm2))
    check("成员不存对方证件/手机（只存关系）",
          all(not any(k in (m or {}) for k in ("id_no","phone","id_card")) for m in (m1, m2)))

    st, lst = await call("GET", f"/v1/circles/{cid}/members", token=tk)
    check("按圈列成员", st == 200 and len(lst.get("items") or []) == 2, (st, lst))

    st, dl = await call("DELETE", f"/v1/circle-members/{m2['id']}", token=tk)
    check("删成员", st == 200, (st, dl))
    st, lst2 = await call("GET", f"/v1/circles/{cid}/members", token=tk)
    check("删后只剩一个", len(lst2.get("items") or []) == 1, lst2)

    st, patched = await call("PATCH", f"/v1/circles/{cid}", token=tk, body={"default_grant_note":"可看行程空闲"})
    check("改圈的默认边界", st == 200 and patched.get("default_grant_note") == "可看行程空闲", (st, patched))

    st, dc = await call("DELETE", f"/v1/circles/{cid}", token=tk)
    check("删圈并级联删成员", st == 200 and dc.get("members_removed") == 1, (st, dc))
    st, left = await call("GET", f"/v1/circles/{cid}/members", token=tk)
    check("级联后该圈无成员", len(left.get("items") or []) == 0, left)
    st, allc = await call("GET", "/v1/circles", token=tk)
    check("另一个圈还在", len(allc.get("items") or []) == 1, allc)

asyncio.run(main())
ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
