"""ledger 独立段：写流水不能重写本体段，且重新登录可读回。"""
import os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from backend import api

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("  ✓ " if ok else "  ✗ ") + name + ((" — " + str(detail)[:160]) if detail and not ok else ""))

st = api.store
st.initialize("Ledger-Test-11!", b"", b"")
sections = list((st.vault.read_document().get("sections") or {}).keys())
check("新建容器即包含 ledger 段", "ledger" in sections, sections)

before = st.vault.read_document()["sections"]["ontology"]["ciphertext"]
st.put_ledger("asset-transactions", "tx_1", {
    "asset_id": "acc_1", "occurred_at": "2026-10-20T12:00:00Z", "amount": -38.5,
    "direction": "out", "counterparty": "某商户", "category": "餐饮", "sensitivity": "restricted"})
after = st.vault.read_document()["sections"]["ontology"]["ciphertext"]
check("写流水不重写本体段", before == after)

check("流水段已落盘", "ledger" in (st.vault.read_document().get("sections") or {}))
check("list_ledger 能列出", len(st.list_ledger("asset-transactions")) == 1)

st.lock()
st.unlock("Ledger-Test-11!")
got = st.get_ledger("asset-transactions", "tx_1")
check("重新登录后读回", bool(got) and str(got.get("counterparty")) == "某商户", got)

check("锁定后 ledger 不可用", (st.lock() or st.get_ledger("asset-transactions", "tx_1") is None))

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
