"""被拒绝的调用也要留审计记录 —— 拒绝是最该留痕的事件。

    ~/personal-ontology/.venv/bin/python tests/test_refusal_audit.py
"""
import asyncio, os, pathlib, sys, tempfile
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

FW = {"model": "scorecard_v1", "inputs": [{"name": "市盈率", "type": "number"}],
      "signals": [{"name": "贵", "dimension": "财务", "when": {"市盈率": {"op": "gt", "value": 40}}}],
      "industry_map": {"新能源": "科技"}, "industry_weights": {"科技": {"财务": 0.4}},
      "score_bands": {"high": {"min": 0.4, "conclusion": "偏高", "severity": "高"}},
      "fallback": {"conclusion": "中性", "severity": "中"}}
SLICE = {"id": "s.refuse", "original_text": "未启用的切片", "status": "analyzed",
         "scenario_profile": {"kind": "professional"}, "analysis": {"title": "未启用的切片"},
         "updated_at": "2026-10-09T00:00:00", "framework": FW,
         "boundaries": {"max_amount": 1000000000, "allowed_scenarios": ["并购尽调"]}}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Refuse-Audit-74!"})
    token = pl["token"]
    await call("POST", "/v1/scenario-slices", body=SLICE, token=token)
    from backend import api as _api
    before = len(_api.store.list("decisions"))
    st, out = await call("POST", "/v1/scenario-slices/s.refuse/judge",
                         body={"data": {"市盈率": 45}, "request": {"caller": "某某", "purpose": "并购尽调"}},
                         token=token)
    check("未启用的切片调用被拒（409）", st == 409, f"{st} {str(out)[:80]}")
    after = _api.store.list("decisions")
    check("被拒之后【留下了】审计记录", len(after) == before + 1, f"{before} → {len(after)}")
    rec = None
    for x in after:
        if str(x.get("reason_key") or "").startswith("skill.refused"):
            rec = x
    check("记录写明是【拒绝】并给出原因", bool(rec) and rec.get("result_id") == "deny", str(rec)[:110])
    rp = (rec or {}).get("reason_params") or {}
    check("记录里留下调用方与切片", bool(rp.get("caller")) and rp.get("slice_id") == "s.refuse", str(rp)[:110])
    p = sum(1 for ok, _ in RESULTS if ok)
    print("\n===== %d/%d 项通过 =====" % (p, len(RESULTS)))
    for ok, l in RESULTS:
        if not ok:
            print("  失败：", l)
    sys.exit(0 if p == len(RESULTS) else 1)

asyncio.run(main())
