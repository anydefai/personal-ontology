"""查看明文会留下记录：写入、计数、可按项查询。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Reveal-Test-11!"}); tk = pl["token"]
    st, pf = await call("POST", "/v1/profiles", token=tk, body={"display_name_zh":"我的实名信息","items":[]})
    st, it = await call("POST", f"/v1/profiles/{pf['id']}/items", token=tk, body={"label_zh":"身份证号","value":"330101199001011234","kind":"id"})
    iid = it["id"]
    st1, r1 = await call("POST", f"/v1/profile-items/{iid}/reveal", token=tk, body={})
    check("第一次查看写入记录", st1 == 200 and r1.get("times_revealed") == 1, (st1, r1))
    st2, r2 = await call("POST", f"/v1/profile-items/{iid}/reveal", token=tk, body={"purpose":"核对证件"})
    check("第二次查看计数为 2", st2 == 200 and r2.get("times_revealed") == 2, (st2, r2))
    st3, lst = await call("GET", f"/v1/profile-items/{iid}/reveals", token=tk)
    items = lst.get("items") or []
    check("能按项查回两条", st3 == 200 and len(items) == 2, (st3, len(items)))
    check("带用途", any(str(x.get("reveal_purpose")) == "核对证件" for x in items), items[:1])
    check("记录里不含明文值", all("330101199001011234" not in str(x) for x in items), items[:1])
    st4, bad = await call("POST", "/v1/profile-items/pi_nope/reveal", token=tk, body={})
    check("不存在的资料项被拒", st4 == 404, (st4, bad))
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
