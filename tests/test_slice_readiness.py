"""启用门槛验收：空的 / 半成品切片不能启用。

门槛在【查主体之前】执行，所以这个测试不需要真实主体；"完整切片可以启用"由
tests/test_slice_api.py 覆盖（它会自己准备主体）。

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
    who = {"grantor_id": "p.x", "grantee_id": "p.x"}      # 门槛先于主体校验，所以这两个 id 不存在也没关系

    # ① 空切片（只填了名字）→ 不能启用，并且说清缺什么
    await call("POST", "/v1/scenario-slices", body=mk("s.empty", {}, "空切片"), token=token)
    st, out = await call("POST", "/v1/scenario-slices/s.empty/enable", body=who, token=token)
    check("① 空切片启用被拒（422）", st == 422, f"{st} {str(out)[:80]}")
    check("① 拒的时候逐条说清缺什么", "还缺" in str((out or {}).get("detail", "")), str(out)[:140])

    # ② 有观察点但没有结论来源 → 仍不能启用
    await call("POST", "/v1/scenario-slices",
               body=mk("s.half", {"inputs": [{"name": "市盈率"}], "signals": [{"name": "贵"}]}, "半成品"), token=token)
    st2, out2 = await call("POST", "/v1/scenario-slices/s.half/enable", body=who, token=token)
    check("② 没有结论来源的切片启用被拒", st2 == 422, f"{st2} {str(out2)[:80]}")
    check("② 拒绝理由指向「没有结论来源」",
          "结论" in str((out2 or {}).get("detail", "")) or "兜底" in str((out2 or {}).get("detail", "")),
          str(out2)[:140])

    # ②b 前端「确认并启用」走的是【通用 PATCH】，所以那条路也必须被同一个门槛挡住
    st_p, out_p = await call("PATCH", "/v1/scenario-slices/s.empty", body={"status": "confirmed"}, token=token)
    check("②b 通用 PATCH 改 status=confirmed 也被拒（422）", st_p == 422, f"{st_p} {str(out_p)[:90]}")
    st_d, det = await call("GET", "/v1/scenario-slices/s.empty", token=token)
    check("②b 被拒后切片仍是草稿（没有偷偷变成已启用）",
          (det or {}).get("status") != "confirmed", str((det or {}).get("status")))

    # ②c 内容够了就该放行（PATCH 路径不需要主体，所以这里能测完整切片）
    await call("POST", "/v1/scenario-slices", body=mk("s.full", FULL, "完整切片"), token=token)
    st_ok, out_ok = await call("PATCH", "/v1/scenario-slices/s.full", body={"status": "confirmed"}, token=token)
    check("②c 内容完整的切片可以启用（200）", st_ok in (200, 204), f"{st_ok} {str(out_ok)[:90]}")

    # ③ 契约里给出 readiness（界面据此提示还缺什么）
    st3, ct = await call("GET", "/v1/scenario-slices/s.empty/contract", token=token)
    rd = (ct or {}).get("readiness") or {}
    check("③ 契约里有 readiness 且标为未就绪", rd.get("ready") is False and bool(rd.get("missing")), str(rd)[:150])

    # ④ 有内容但没填权重 → 只提醒（不阻断）
    noweight = {k: v for k, v in FULL.items() if k != "industry_weights"}
    await call("POST", "/v1/scenario-slices", body=mk("s.noweight", noweight, "没权重"), token=token)
    st4, ct2 = await call("GET", "/v1/scenario-slices/s.noweight/contract", token=token)
    rd2 = (ct2 or {}).get("readiness") or {}
    check("④ 没权重时只提醒不阻断（ready 仍为真，warnings 提到权重）",
          rd2.get("ready") is True and any("权重" in w for w in (rd2.get("warnings") or [])), str(rd2)[:160])

    p = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok, l in RESULTS:
        if not ok:
            print("  失败：", l)
    sys.exit(0 if p == len(RESULTS) else 1)

asyncio.run(main())
