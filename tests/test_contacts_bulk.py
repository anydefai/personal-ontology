"""批量导入性能与正确性：250 条应秒级完成，且全部 restricted、幂等。"""
import asyncio, json, os, sys, tempfile, pathlib, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
DATA = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = DATA
recs = [{"name": f"联系人{i}", "org": f"公司{i%20}", "phones":[{"number":f"138****{i:04d}","type":"2"}],
         "emails":[], "addresses":[], "notes":[], "group_ids":[]} for i in range(250)]
(pathlib.Path(DATA) / "contacts-import.json").write_text(json.dumps({"source":"bulk-test","records":recs}, ensure_ascii=False), encoding="utf-8")
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Bulk-Test-11!"}); tk = pl["token"]
    t0 = time.time()
    st1, out = await call("POST", "/v1/contacts/import-file", token=tk, body={})
    cost = time.time() - t0
    check("250 条导入成功", st1 == 200 and out.get("created") == 250, (st1, out))
    check(f"耗时 {cost:.1f}s（应 < 30s）", cost < 30, cost)
    st2, lst = await call("GET", "/v1/contact-records", token=tk)
    check("库里有 250 条", len(lst.get("items") or []) == 250, len(lst.get("items") or []))
    check("全部 restricted", all(str(x.get("contact_sensitivity")) == "restricted" for x in (lst.get("items") or [])), "")
    st3, out2 = await call("POST", "/v1/contacts/import-file", token=tk, body={})
    check("再导一次全部跳过", out2.get("created") == 0 and out2.get("skipped") == 250, out2)
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
