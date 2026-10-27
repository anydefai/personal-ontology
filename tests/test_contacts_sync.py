"""通讯录同步：按 contact_id 就地更新，不产生重复；手机删掉的被标记。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from test_api_auth import call
from backend import api, contacts_sync
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
def rows(*triples):
    out = []
    for cid, name, phone in triples:
        out.append(f"Row: 0 contact_id={cid}, mimetype=vnd.android.cursor.item/name, data1={name}")
        if phone:
            out.append(f"Row: 1 contact_id={cid}, mimetype=vnd.android.cursor.item/phone_v2, data1={phone}, data2=2")
    return "\n".join(out)
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Sync-Test-11!"}); tk = pl["token"]
    s = api.store
    # 第一次同步：两个人
    recs = contacts_sync.parse_rows(rows((59,"张三","13800138000"), (60,"李四","13900139000")))
    accounts = {"59": {"account_name":"me@gmail.com","account_type":"com.google"}}
    st1 = contacts_sync.upsert(s, recs, accounts, "OnePlus · b3")
    check("首次同步新增 2 条", st1["created"] == 2, st1)
    lst = s.list("contact-records")
    check("共 2 条", len(lst) == 2, len(lst))
    one = [x for x in lst if str(x.get("source_contact_id")) == "59"][0]
    check("带设备与账户标签", "OnePlus · b3" in (one.get("contact_tags") or []) and "com.google" in (one.get("contact_tags") or []), one.get("contact_tags"))
    # 第二次：改了电话、加了新人、少了李四
    recs2 = contacts_sync.parse_rows(rows((59,"张三","13711112222"), (61,"王五","13600136000")))
    st2 = contacts_sync.upsert(s, recs2, accounts, "OnePlus · b3")
    check("第二次：新增 1 / 更新 1 / 手机已删 1", (st2["created"], st2["updated"], st2["deleted_on_phone"]) == (1,1,1), st2)
    lst2 = s.list("contact-records")
    check("总数仍是 3（无重复）", len(lst2) == 3, len(lst2))
    z = [x for x in lst2 if str(x.get("source_contact_id")) == "59"][0]
    check("电话已就地更新", "13711112222" in str(z.get("contact_phones")), z.get("contact_phones"))
    li = [x for x in lst2 if str(x.get("source_contact_id")) == "60"][0]
    check("手机已删的被标记", str(li.get("from_phone_deleted")) == "true", li.get("from_phone_deleted"))
    # 第三次：完全没变 → 全部未变
    st3 = contacts_sync.upsert(s, contacts_sync.parse_rows(rows((59,"张三","13711112222"))), accounts, "OnePlus · b3")
    check("无变化时全部记为未变", st3["created"] == 0 and st3["updated"] == 0 and st3["unchanged"] == 1, st3)
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
