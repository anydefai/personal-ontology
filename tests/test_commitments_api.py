"""事：建/改/删 + 类型校验（到期筛选放在界面，接口保持无参数）。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Commit-Test-11!"}); tk = pl["token"]
    st, a = await call("POST", "/v1/commitments", token=tk, body={"display_name_zh":"车险续保","commitment_kind":"renewal","due_at":"2026-11-01","remind_before_days":14})
    check("建一条", st == 201 and a.get("id"), (st, a))
    st, lst = await call("GET", "/v1/commitments", token=tk)
    check("列表能读到", st == 200 and len(lst.get("items") or []) == 1, (st, lst if st != 200 else ""))
    st, bad = await call("POST", "/v1/commitments", token=tk, body={"display_name_zh":"","commitment_kind":"renewal"})
    check("空名被拒", st == 422, (st, bad))
    st, bad2 = await call("POST", "/v1/commitments", token=tk, body={"display_name_zh":"X","commitment_kind":"nonsense"})
    check("非法类型被拒", st == 422, (st, bad2))
    st, up = await call("PATCH", f"/v1/commitments/{a['id']}", token=tk, body={"commitment_status":"done"})
    check("标记完成", st == 200 and up.get("commitment_status") == "done", (st, up))
    st, dl = await call("DELETE", f"/v1/commitments/{a['id']}", token=tk)
    st, lst2 = await call("GET", "/v1/commitments", token=tk)
    check("删除后列表为空", st == 200 and len(lst2.get("items") or []) == 0, (st, len(lst2.get("items") or [])))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
