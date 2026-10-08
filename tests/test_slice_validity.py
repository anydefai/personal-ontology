"""交付有效期验收：说明里写的 valid_days 过了就不给结论。

    ~/personal-ontology/.venv/bin/python tests/test_slice_validity.py
"""
import asyncio, json, os, pathlib, shutil, sys, tempfile
from datetime import datetime, timedelta, timezone
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

def iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")

BASE_FW = {"inputs": [{"name": "行业"}, {"name": "市盈率", "type": "number"}],
           "thresholds": {"base": 1.0, "adjustments": []},
           "signals": [{"name": "贵", "when": {"市盈率": {"op": "gt", "value": 30}}}],
           "combination_rules": [{"all_of": ["贵"], "conclusion": "偏高", "severity": "高"}],
           "fallback": {"conclusion": "合理", "severity": "低"}}
DATA = {"行业": "x", "市盈率": 45}
REQ = {"caller": "平台A", "purpose": "估值", "amount": 100, "no_resale": True}
BND = {"max_amount": 10**6, "allowed_scenarios": ["估值"], "confidentiality": "不得转售"}

async def setup(tok, sid, valid_days, updated_ago=0):
    fw = dict(BASE_FW)
    if valid_days is not None:
        fw["delivery"] = {"valid_days": valid_days}
    await call("POST", "/v1/scenario-slices", body={"id": sid, "original_text": "x", "status": "analyzed",
        "scenario_profile": {"kind": "professional"}, "analysis": {"title": sid},
        "updated_at": iso(updated_ago)}, token=tok)
    await call("PATCH", "/v1/scenario-slices/" + sid,
               body={"framework": fw, "status": "confirmed", "boundaries": BND, "updated_at": iso(updated_ago)}, token=tok)

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Ocean-Tide-74!"}); tok = pl["token"]

    await setup(tok, "s.none", None)
    st, c = await call("GET", "/v1/scenario-slices/s.none/contract", token=tok)
    check("没设有效期 → 契约里不设期限", (c.get("validity") or {}).get("expired") is False
          and (c.get("validity") or {}).get("valid_days") is None, json.dumps(c.get("validity"), ensure_ascii=False))
    st, r = await call("POST", "/v1/scenario-slices/s.none/judge", body={"data": DATA, "request": REQ}, token=tok)
    check("没设有效期 → 正常判定", (r.get("judgment") or {}).get("decision") == "偏高", f"HTTP {st}")

    await setup(tok, "s.fresh", 30)
    st, c = await call("GET", "/v1/scenario-slices/s.fresh/contract", token=tok)
    v = c.get("validity") or {}
    check("30 天有效期 → 契约给出到期时间且未过期", bool(v.get("expires_at")) and v.get("expired") is False,
          json.dumps(v, ensure_ascii=False))
    st, r = await call("POST", "/v1/scenario-slices/s.fresh/judge", body={"data": DATA, "request": REQ}, token=tok)
    check("30 天有效期 → 正常判定", (r.get("judgment") or {}).get("decision") == "偏高", f"HTTP {st}")

    await setup(tok, "s.old", 1, updated_ago=10)
    st, c = await call("GET", "/v1/scenario-slices/s.old/contract", token=tok)
    check("1 天有效期但 10 天前更新 → 契约标记已过期", (c.get("validity") or {}).get("expired") is True,
          json.dumps(c.get("validity"), ensure_ascii=False))
    st, r = await call("POST", "/v1/scenario-slices/s.old/judge", body={"data": DATA, "request": REQ}, token=tok)
    check("已过期 → 判定被拒（403）并说明如何续期",
          st == 403 and (r.get("detail") or {}).get("error") == "slice_delivery_expired"
          and "有效期" in json.dumps(r.get("detail") or {}, ensure_ascii=False),
          f"HTTP {st} {json.dumps(r.get('detail'), ensure_ascii=False)[:120]}")

    await setup(tok, "s.zero", 0)
    st, r = await call("POST", "/v1/scenario-slices/s.zero/judge", body={"data": DATA, "request": REQ}, token=tok)
    check("valid_days=0 视为不设期限", (r.get("judgment") or {}).get("decision") == "偏高", f"HTTP {st}")

asyncio.run(main())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
