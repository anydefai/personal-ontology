"""资料项：从 profiles.items 拆分，迁移前后项数与值一致；幂等；可逐步读写。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("  ✓ " if ok else "  ✗ ") + name + ((" — " + str(detail)[:200]) if detail and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Items-Test-11!"}); tk = pl["token"]
    st, pf = await call("POST", "/v1/profiles", token=tk, body={"display_name_zh":"我的实名信息","items":[
        {"key":"姓名","label":"姓名","value":"张三","kind":"text"},
        {"key":"身份证号","label":"身份证号","value":"330101199001011234","kind":"id","verified":True},
        {"key":"手机号","label":"手机号","value":"13800138000","kind":"phone"}]})
    pid = pf["id"]
    check("建资料（3 项）", st == 201 and len(pf.get("items") or []) == 3, (st, pf))

    st, mv = await call("POST", "/v1/profiles/migrate-items", token=tk, body={})
    check("首次迁移创建 3 项", st == 200 and mv.get("created") == 3, (st, mv))
    st2, mv2 = await call("POST", "/v1/profiles/migrate-items", token=tk, body={})
    check("再迁一次幂等（创建 0、跳过 3）", st2 == 200 and mv2.get("created") == 0 and mv2.get("skipped") == 3, (st2, mv2))

    st, lst = await call("GET", f"/v1/profiles/{pid}/items", token=tk)
    items = lst.get("items") or []
    check("按资料列出 3 项", st == 200 and len(items) == 3, (st, len(items)))
    by_label = {x.get("label_zh"): x for x in items}
    check("值一致（身份证号）", (by_label.get("身份证号") or {}).get("item_value") == "330101199001011234", by_label.get("身份证号"))
    check("字段名映射（身份证号 → id_no）", (by_label.get("身份证号") or {}).get("field_key") == "id_no", by_label.get("身份证号"))
    check("证件类默认 critical", (by_label.get("身份证号") or {}).get("item_sensitivity") == "critical")
    check("已验证状态被带过来", (by_label.get("身份证号") or {}).get("item_verified") == "true")
    check("手机号的字段码是 phone", (by_label.get("手机号") or {}).get("field_key") == "phone")

    st, new = await call("POST", f"/v1/profiles/{pid}/items", token=tk, body={"label_zh":"住址","value":"某市某区","sensitivity":"sensitive"})
    check("逐项新增", st == 201 and new.get("id"), (st, new))
    st, up = await call("PATCH", f"/v1/profile-items/{new['id']}", token=tk, body={"value":"新地址"})
    check("逐项修改", st == 200 and up.get("item_value") == "新地址", (st, up))
    st, de = await call("DELETE", f"/v1/profile-items/{new['id']}", token=tk)
    check("逐项删除", st == 200, (st, de))
    st, lst2 = await call("GET", f"/v1/profiles/{pid}/items", token=tk)
    check("删后回到 3 项", len(lst2.get("items") or []) == 3, len(lst2.get("items") or []))
    st, still = await call("GET", "/v1/profiles", token=tk)
    check("profiles.items 原样保留（可回退）", len((still.get("items") or [])[0].get("items") or []) == 3)
asyncio.run(main())
ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
