"""财：资产增删改查；只接受掩码与摘要；默认 restricted。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Assets-Test-11!"}); tk = pl["token"]
    st, a = await call("POST", "/v1/assets", token=tk, body={"display_name_zh":"工资卡","asset_kind":"account","identifier_masked":"**** 1234","custodian":"某银行","value_summary":"余额 5 万左右"})
    check("建资产（账户）", st == 201 and a.get("id"), (st, a))
    check("默认敏感级 restricted", (a or {}).get("asset_sensitivity") == "restricted", (a or {}).get("asset_sensitivity"))
    st, b = await call("POST", "/v1/assets", token=tk, body={"display_name_zh":"车险","asset_kind":"insurance","expires_at":"2027-03-01"})
    check("建保险（带到期日）", st == 201 and b.get("id"), (st, b))
    st, bad = await call("POST", "/v1/assets", token=tk, body={"display_name_zh":"","asset_kind":"account"})
    check("空名被拒", st == 422, (st, bad))
    st, bad2 = await call("POST", "/v1/assets", token=tk, body={"display_name_zh":"X","asset_kind":"nonsense"})
    check("非法类型被拒", st == 422, (st, bad2))
    st, lst = await call("GET", "/v1/assets", token=tk)
    check("列出两个", len(lst.get("items") or []) == 2, lst)
    st, up = await call("PATCH", f"/v1/assets/{a['id']}", token=tk, body={"value_summary":"余额 6 万左右"})
    check("改摘要", st == 200 and up.get("value_summary") == "余额 6 万左右", (st, up))
    st, dl = await call("DELETE", f"/v1/assets/{b['id']}", token=tk)
    st, lst2 = await call("GET", "/v1/assets", token=tk)
    check("删后剩一个", st == 200 and len(lst2.get("items") or []) == 1, (st, len(lst2.get("items") or [])))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
