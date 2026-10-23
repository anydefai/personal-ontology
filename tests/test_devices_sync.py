"""器：从明文清单同步智能体设备，只搬元数据，不复制密钥。"""
import asyncio, json, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
DATA = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = DATA
(DATA_P := pathlib.Path(DATA) / "agent-clients.json").write_text(json.dumps({
    "clients": {
        "key_aaa": {"name": "WorkBuddy", "state": "approved", "scopes": ["catalog", "judgment"],
                    "created_at": "2026-10-01T00:00:00Z", "last_seen": "2026-10-20T00:00:00Z",
                    "secret_hash": "SHOULD-NOT-LEAK"},
        "key_bbb": {"name": "笔记助手", "state": "pending", "scopes": ["catalog"]},
    }
}, ensure_ascii=False), encoding="utf-8")
from test_api_auth import call
RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("  ✓ " if ok else "  ✗ ") + name + ((" — " + str(detail)[:200]) if detail and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Devices-Test-11!"}); tk = pl["token"]
    st, out = await call("POST", "/v1/devices/sync", token=tk, body={})
    check("同步成功", st == 200 and out.get("synced") == 2, (st, out))
    st, lst = await call("GET", "/v1/devices", token=tk)
    items = {x.get("agent_client_id"): x for x in (lst.get("items") or [])}
    check("两条设备都在", set(items) == {"key_aaa", "key_bbb"}, list(items))
    a = items.get("key_aaa") or {}
    check("approved → trusted", a.get("trust_level") == "trusted", a.get("trust_level"))
    check("pending → limited", (items.get("key_bbb") or {}).get("trust_level") == "limited")
    check("范围被带过来", a.get("device_scopes") == ["catalog", "judgment"], a.get("device_scopes"))
    blob = json.dumps(lst, ensure_ascii=False)
    check("密钥/哈希没有进本体", "SHOULD-NOT-LEAK" not in blob and "secret" not in blob.lower())
asyncio.run(main())
ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
