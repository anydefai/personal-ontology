"""清除导入的通讯录：按来源清，圈里成员不受影响。"""
import asyncio, json, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
DATA = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = DATA
(pathlib.Path(DATA) / "contacts-import.json").write_text(json.dumps({"source":"adb-contacts","records":[
  {"name":"甲","org":"公司","phones":[],"emails":[],"addresses":[],"notes":[],"group_ids":[]},
  {"name":"乙","org":"","phones":[],"emails":[],"addresses":[],"notes":[],"group_ids":[]},
]}, ensure_ascii=False), encoding="utf-8")
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Purge-Test-11!"}); tk = pl["token"]
    await call("POST", "/v1/contacts/import-file", token=tk, body={})
    st, c = await call("POST", "/v1/circles", token=tk, body={"display_name_zh":"家人","circle_type":"family"})
    cid = c["id"]
    await call("POST", f"/v1/circles/{cid}/members", token=tk, body={"display_name_zh":"甲"})
    st1, lst = await call("GET", "/v1/contact-records", token=tk)
    check("导入后有 2 条", len(lst.get("items") or []) == 2, len(lst.get("items") or []))
    st2, out = await call("POST", "/v1/contacts/purge", token=tk, body={"source":"adb-contacts"})
    check("按来源清除 2 条", st2 == 200 and out.get("removed") == 2, (st2, out))
    st3, lst2 = await call("GET", "/v1/contact-records", token=tk)
    check("通讯录清空", len(lst2.get("items") or []) == 0, len(lst2.get("items") or []))
    st4, mem = await call("GET", f"/v1/circles/{cid}/members", token=tk)
    check("圈里的成员不受影响", len(mem.get("items") or []) == 1, mem)
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
