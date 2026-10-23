"""地：增删改查、类型校验、地址与坐标可选。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Places-Test-11!"}); tk = pl["token"]
    st, a = await call("POST", "/v1/places", token=tk, body={"display_name_zh":"家","place_kind":"home","address_text":"某市某区某路 1 号","radius_m":200})
    check("建地点（家）", st == 201 and a.get("id"), (st, a))
    st, b = await call("POST", "/v1/places", token=tk, body={"display_name_zh":"公司","place_kind":"work"})
    check("再建一个（公司）", st == 201 and b.get("id"), (st, b))
    st, bad = await call("POST", "/v1/places", token=tk, body={"display_name_zh":"","place_kind":"home"})
    check("空名被拒", st == 422, (st, bad))
    st, bad2 = await call("POST", "/v1/places", token=tk, body={"display_name_zh":"X","place_kind":"nonsense"})
    check("非法类型被拒", st == 422, (st, bad2))
    st, lst = await call("GET", "/v1/places", token=tk)
    check("列出两个", len(lst.get("items") or []) == 2, lst)
    st, up = await call("PATCH", f"/v1/places/{a['id']}", token=tk, body={"address_text":"新地址","radius_m":500})
    check("改地址与半径", st == 200 and up.get("address_text") == "新地址" and up.get("radius_m") == "500", (st, up))
    st, dl = await call("DELETE", f"/v1/places/{b['id']}", token=tk)
    st, lst2 = await call("GET", "/v1/places", token=tk)
    check("删一个后剩一个", st == 200 and len(lst2.get("items") or []) == 1, (st, len(lst2.get("items") or [])))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
