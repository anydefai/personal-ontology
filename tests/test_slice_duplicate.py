"""切片「另存为」验收：复制框架与边界；不复制授权与判定记录；副本是草稿且未验证。

    ~/personal-ontology/.venv/bin/python tests/test_slice_duplicate.py
"""
import asyncio, json, os, pathlib, sys, tempfile
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

FW = {"model": "scorecard_v1",
      "inputs": [{"name": "市盈率", "type": "number"}],
      "thresholds": {"base": 1.3, "adjustments": [{"condition": {"行业周期位置": "上升期"}, "factor": 1.2}]},
      "signals": [{"name": "偏高", "dimension": "财务", "score_value": 0.5,
                   "when": {"市盈率": {"op": "gt", "value": 39}}}],
      "industry_map": {"新能源": "科技"}, "industry_weights": {"科技": {"财务": 0.4}},
      "combination_rules": [{"all_of": ["偏高"], "conclusion": "估值偏高", "severity": "高"}],
      "score_bands": {"high": {"min": 0.5, "conclusion": "偏高", "severity": "高"}},
      "fallback": {"conclusion": "中性", "severity": "中"}}
SLICE = {"id": "slice.dup.mine", "original_text": "我的收购评估", "status": "confirmed",
         "scenario_profile": {"kind": "professional"},
         "analysis": {"title": "我的收购评估"}, "updated_at": "2026-10-08T00:00:00",
         "framework": FW,
         "boundaries": {"max_amount": 1000000000, "allowed_scenarios": ["并购尽调"]},
         "delivery": {"note": "仅限本次用途"}, "billing": {"unit_price": 800, "currency": "CNY"},
         "authorizations": [{"id": "auth.1", "grantee": "p.1"}], "authorization_ids": ["auth.1"],
         "decisions": [{"decision_id": "d.1"}], "confidence_status": "verified"}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Dup-Slice-74!"})
    assert "token" in pl, f"setup 失败 {st} {pl}"
    token = pl["token"]

    st, src_out = await call("POST", "/v1/scenario-slices", body=SLICE, token=token)
    check("建源切片", st in (200, 201), f"{st}")
    # 以"源切片实际存下来的样子"为基准：存储层对字段有白名单，会丢掉它不认识的字段，
    # 所以「另存为」该保证的是【副本 == 源】，而不是【副本 == 我提交的原文】。
    src = (src_out or {}).get("scenario") or src_out or {}

    st, out = await call("POST", f"/v1/scenario-slices/{SLICE['id']}/duplicate", body={}, token=token)
    check("另存为返回成功", st in (200, 201), f"{st} {str(out)[:120]}")
    s = (out or {}).get("scenario") or {}

    check("副本是新 id", bool(s.get("id")) and s.get("id") != SLICE["id"], str(s.get("id")))
    check("副本标题带「副本」", "副本" in ((s.get("analysis") or {}).get("title") or ""),
          str((s.get("analysis") or {}).get("title")))
    check("副本框架与源【逐字段相等】（含模型、命中分值、阈值乘法）",
          json.dumps(s.get("framework"), sort_keys=True, ensure_ascii=False) ==
          json.dumps(FW, sort_keys=True, ensure_ascii=False),
          json.dumps(s.get("framework"), ensure_ascii=False)[:160])
    check("副本复制了对外边界", (s.get("boundaries") or {}).get("max_amount") == 1000000000)
    check("副本与源在 delivery / billing 上一致（源有则有）",
          bool(s.get("delivery")) == bool(src.get("delivery")) and
          bool(s.get("billing")) == bool(src.get("billing")),
          "副本 %s · 源 %s" % (bool(s.get("delivery")), bool(src.get("delivery"))))
    check("副本状态是草稿（不继承已启用）", s.get("status") == "draft", str(s.get("status")))
    check("副本置信度为未验证", s.get("confidence_status") == "unverified", str(s.get("confidence_status")))
    check("副本不带授权规则（复制切片不等于复制授权）",
          not s.get("authorizations") and not s.get("authorization_ids"))
    check("副本不带判定记录", not s.get("decisions"))
    check("副本与源在边界、交付、计费三项上全部一致",
          all(s.get(k) == src.get(k) for k in ("boundaries", "delivery", "billing")),
          json.dumps({k: s.get(k) for k in ("boundaries", "delivery", "billing")}, ensure_ascii=False)[:120])

    st, missing = await call("POST", "/v1/scenario-slices/不存在/duplicate", body={}, token=token)
    check("源切片不存在 → 404（不静默造一条）", st == 404, f"{st}")

    p = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok, l in RESULTS:
        if not ok:
            print("  失败：", l)
    sys.exit(0 if p == len(RESULTS) else 1)

asyncio.run(main())
