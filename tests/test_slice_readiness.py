"""启用门槛验收：空的/半成品切片不能启用；完整切片可以。

    ~/personal-ontology/.venv/bin/python tests/test_slice_readiness.py
"""
import asyncio, os, pathlib, sys, tempfile
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

FULL = {"model": "scorecard_v1", "inputs": [{"name": "市盈率", "type": "number"}],
        "signals": [{"name": "贵", "dimension": "财务", "when": {"市盈率": {"op": "gt", "value": 40}}}],
        "industry_map": {"新能源": "科技"}, "industry_weights": {"科技": {"财务": 0.4}},
        "score_bands": {"high": {"min": 0.4, "conclusion": "偏高", "severity": "高"}},
        "fallback": {"conclusion": "中性", "severity": "中"}}

def mk(sid, fw, title):
    return {"id": sid, "original_text": title, "status": "analyzed",
            "scenario_profile": {"kind": "professional"}, "analysis": {"title": title},
            "updated_at": "2026-10-08T00:00:00", "framework": fw}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Ready-Slice-74!"})
    token = pl["token"]
    # 取应用里已有的 principal（setup 会建），不要自己造 id —— 造错 id 会让启用因为"授权对象不存在"而失败
    from backend import store as S
    pids = [str(x.get("id")) for x in S.store.list("principals") if x.get("id")]
    check("应用里已有 principal（setup 建的）", bool(pids), str(pids))
    ME = pids[0] if pids else "p.me"

    # ① 空切片（只填了名字）→ 不能启用
    await call("POST", "/v1/scenario-slices", body=mk("s.empty", {}, "空切片"), token=token)
    st, out = await call("POST", "/v1/scenario-slices/s.empty/enable",
                         body={"grantor_id": ME, "grantee_id": ME}, token=token)
    check("① 空切片启用被拒（422）", st == 422, f"{st} {str(out)[:80]}")
    check("① 拒的时候说清缺什么", "还缺" in str(out.get("detail", "")), str(out)[:120])

    # ② 只填了名字+一条观察点，但没有结论来源 → 仍不能启用
    await call("POST", "/v1/scenario-slices",
               body=mk("s.half", {"inputs": [{"name": "市盈率"}], "signals": [{"name": "贵"}]}, "半成品"), token=token)
    st, out = await call("POST", "/v1/scenario-slices/s.half/enable",
                         body={"grantor_id": ME, "grantee_id": ME}, token=token)
    check("② 没有结论来源的切片启用被拒", st == 422, f"{st} {str(out)[:80]}")

    # ③ 完整切片 → 可以启用
    await call("POST", "/v1/scenario-slices", body=mk("s.full", FULL, "完整切片"), token=token)
    st, out = await call("POST", "/v1/scenario-slices/s.full/enable",
                         body={"grantor_id": ME, "grantee_id": ME}, token=token)
    check("③ 完整切片可以启用（200/201）", st in (200, 201), f"{st} {str(out)[:80]}")
    st2, det = await call("GET", "/v1/scenario-slices/s.full", token=token)
    check("③ 启用后状态是 confirmed", (det or {}).get("status") == "confirmed", str((det or {}).get("status")))

    # ④ 契约里给出 readiness，界面才能提示还缺什么
    st3, ct = await call("GET", "/v1/scenario-slices/s.empty/contract", token=token)
    rd = (ct or {}).get("readiness") or {}
    check("④ 契约里有 readiness 且标为未就绪", rd.get("ready") is False and rd.get("missing"), str(rd)[:140])
    st4, ct2 = await call("GET", "/v1/scenario-slices/s.full/contract", token=token)
    rd2 = (ct2 or {}).get("readiness") or {}
    check("④ 完整切片的 readiness 已就绪", rd2.get("ready") is True, str(rd2)[:140])

    # ⑤ 有权重提醒（不阻断）
    HALF_W = dict(FULL); HALF_W.pop("industry_weights")
    await call("POST", "/v1/scenario-slices", body=mk("s.noweight", HALF_W, "没权重"), token=token)
    st5, ct3 = await call("GET", "/v1/scenario-slices/s.noweight/contract", token=token)
    rd3 = (ct3 or {}).get("readiness") or {}
    check("⑤ 没权重时给提醒但不阻断（ready 仍为真）",
          rd3.get("ready") is True and any("权重" in w for w in (rd3.get("warnings") or [])), str(rd3)[:160])

    p = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok, l in RESULTS:
        if not ok:
            print("  失败：", l)
    sys.exit(0 if p == len(RESULTS) else 1)

asyncio.run(main())
