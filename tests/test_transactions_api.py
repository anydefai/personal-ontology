"""流水走 ledger 段：新增、列表、删除；写流水不动本体段。"""
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
    st, pl = await call("POST", "/v1/setup", body={"password": "Tx-Test-11!"}); tk = pl["token"]
    st, a = await call("POST", "/v1/assets", token=tk, body={"display_name_zh":"工资卡","asset_kind":"account"})
    aid = a["id"]
    before = api.store.vault.read_document()["sections"]["ontology"]["ciphertext"]
    st1, t1 = await call("POST", "/v1/asset-transactions", token=tk, body={"asset_id":aid,"amount":-38.5,"counterparty":"某商户","category":"餐饮","occurred_at":"2026-10-20T12:00:00Z"})
    check("记一笔支出", st1 == 201 and t1.get("id"), (st1, t1))
    check("方向自动为 out", (t1 or {}).get("direction") == "out", (t1 or {}).get("direction"))
    st2, t2 = await call("POST", "/v1/asset-transactions", token=tk, body={"asset_id":aid,"amount":12000,"counterparty":"某公司"})
    check("记一笔收入", st2 == 201 and (t2 or {}).get("direction") == "in", (st2, t2))
    st3, bad = await call("POST", "/v1/asset-transactions", token=tk, body={"asset_id":"asset_nope","amount":1})
    check("不存在的资产被拒", st3 == 422, (st3, bad))
    st4, bad2 = await call("POST", "/v1/asset-transactions", token=tk, body={"asset_id":aid,"amount":"不是数字"})
    check("金额非数字被拒", st4 == 422, (st4, bad2))
    st5, lst = await call("GET", "/v1/asset-transactions", token=tk)
    check("列出两笔", len((lst or {}).get("items") or []) == 2, (st5, len((lst or {}).get("items") or [])))
    after = api.store.vault.read_document()["sections"]["ontology"]["ciphertext"]
    check("写流水没有重写本体段", before == after)
    st6, dl = await call("DELETE", f"/v1/asset-transactions/{t1['id']}", token=tk)
    st7, lst2 = await call("GET", "/v1/asset-transactions", token=tk)
    check("删除一笔后剩一笔", st6 == 200 and len((lst2 or {}).get("items") or []) == 1, (st6, len((lst2 or {}).get("items") or [])))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
