"""通讯录导入：读本机文件、去重、一律 restricted。"""
import asyncio, json, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
DATA = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = DATA
(pathlib.Path(DATA) / "contacts-import.json").write_text(json.dumps({"source":"test","records":[
  {"name":"甲","org":"某公司","phones":[{"number":"138****","type":"2"}],"emails":[],"addresses":[],"notes":["备注一"],"group_ids":["1"]},
  {"name":"乙","org":"","phones":[],"emails":[{"address":"b@example.com","type":"1"}],"addresses":[],"notes":[],"group_ids":[]},
  {"name":"甲","org":"某公司","phones":[],"emails":[],"addresses":[],"notes":[],"group_ids":[]},
]}, ensure_ascii=False), encoding="utf-8")
from test_api_auth import call
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Contacts-Test-11!"}); tk = pl["token"]
    st1, out = await call("POST", "/v1/contacts/import-file", token=tk, body={})
    check("导入成功（2 新增 / 1 重复跳过）", st1 == 200 and out.get("created") == 2 and out.get("skipped") == 1, (st1, out))
    st2, lst = await call("GET", "/v1/contact-records", token=tk)
    items = lst.get("items") or []
    check("列表两条", len(items) == 2, len(items))
    check("全部 restricted", all(str(x.get("contact_sensitivity")) == "restricted" for x in items), items[:1])
    check("电话与备注被带过来", any(x.get("contact_phones") for x in items) and any(x.get("contact_note") for x in items), items[:1])
    st3, out2 = await call("POST", "/v1/contacts/import-file", token=tk, body={})
    check("再导一次全部跳过（幂等）", out2.get("created") == 0 and out2.get("skipped") == 3, out2)
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
