"""圈的变更记录：加人、移人都写一条，可按圈查回。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Chg-Test-11!"}); tk = pl["token"]
    st, c = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"工作","circle_type":"work"})
    cid = c["id"]
    st0, ch0 = await call("GET", f"/v1/circles/{cid}/changes", token=tk)
    check("新圈没有变更记录", st0 == 200 and len(ch0.get("items") or []) == 0, (st0, ch0))
    st1, m1 = await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"张三"})
    st, ch1 = await call("GET", f"/v1/circles/{cid}/changes", token=tk)
    items = ch1.get("items") or []
    check("加人后有一条", len(items) == 1 and items[0]["change_kind"] == "member_added", items)
    check("记录里带成员名字", any("张三" in str(x.get("change_detail")) for x in items), items)
    await call("DELETE", f"/v1/circle-members/{m1['id']}", token=tk)
    st2, ch2 = await call("GET", f"/v1/circles/{cid}/changes", token=tk)
    items2 = ch2.get("items") or []
    check("移人后共两条", len(items2) == 2, len(items2))
    check("最新一条是移出", items2[0]["change_kind"] == "member_removed", items2[:1])
    st3, bad = await call("GET", "/v1/circles/circle_nope/changes", token=tk)
    check("不存在的圈 404", st3 == 404, (st3, bad))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
