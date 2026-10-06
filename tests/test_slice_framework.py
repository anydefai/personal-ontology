"""切片承载个人判断资产（框架等）验收。

    ~/personal-ontology/.venv/bin/python tests/test_slice_framework.py

要点：框架属于**个人切片**（不属于可共享的场景定义）；两层字段互不干扰。
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
from backend.model import FIELDS

need = ["framework", "boundaries", "insight", "owner_credentials", "valid_days",
        "confidence", "confidence_status", "confidence_basis", "feedback_total", "feedback_accurate"]
check("切片集合已具备个人资产字段", all(k in FIELDS["scenario-slices"] for k in need),
      str([k for k in need if k not in FIELDS["scenario-slices"]]))
check("切片与定义的框架谓词不同（互不覆盖）",
      FIELDS["scenario-slices"]["framework"][0] != FIELDS["scenario-definitions"]["framework"][0])
check("定义字段数未受影响", len(FIELDS["scenario-definitions"]) == 21, str(len(FIELDS["scenario-definitions"])))

FW = {"framework_version": "SLICE-V1", "thresholds": {"base": 1.0, "adjustments": []},
      "signals": [{"name": "偏高", "when": {"市盈率": {"op": "gt", "value": 39}}}],
      "combination_rules": [{"all_of": ["偏高"], "conclusion": "估值偏高", "severity": "高"}]}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Slice-94!"})
    assert "token" in pl, f"setup 失败 {st} {pl}"
    token = pl["token"]
    body = {"id": "slice.ma.online", "original_text": "我的收购评估 · 互联网版", "status": "analyzed",
            "scenario_definition_id": "legal.acquisition", "scenario_profile": {"kind": "professional"},
            "analysis": {"title": "我的收购评估 · 互联网版"}, "updated_at": "2026-10-06T00:00:00",
            "framework": FW, "boundaries": {"max_amount": 1000000000, "allowed_scenarios": ["并购尽调"],
                                            "default_tier": "professional"},
            "insight": "同时看行业周期与监管", "owner_credentials": "执业 15 年",
            "valid_days": 2, "confidence_status": "unverified"}
    st, r = await call("POST", "/v1/scenario-slices", body=body, token=token)
    check("可创建带框架的个人切片", st in (200, 201), f"HTTP {st} {str(r)[:120]}")
    st, one = await call("GET", "/v1/scenario-slices/slice.ma.online", token=token)
    check("切片的框架读得回", isinstance(one.get("framework"), dict)
          and one["framework"].get("framework_version") == "SLICE-V1", str(one.get("framework"))[:80])
    check("切片的边界与洞察读得回",
          (one.get("boundaries") or {}).get("default_tier") == "professional" and one.get("insight"),
          str(one.get("boundaries"))[:80])
    # 两条切片挂同一个场景定义（这正是"一个场景多条切片"的意义）
    st, r = await call("POST", "/v1/scenario-slices", body=dict(body, id="slice.ma.mfg",
                       original_text="我的收购评估 · 制造业版", framework=None, insight=""),
                       token=token)
    check("同一场景可挂多条切片", st in (200, 201), f"HTTP {st}")
    st, all_slices = await call("GET", "/v1/scenario-slices", token=token)
    items = all_slices.get("items") if isinstance(all_slices, dict) else all_slices
    mine = [x for x in items if x.get("scenario_definition_id") == "legal.acquisition"]
    check("两条切片都归属同一场景定义", len(mine) == 2, str(len(mine)))
    # 定义上的框架不受影响（两层互不干扰）
    st, d = await call("GET", "/v1/scenario-definitions/legal.acquisition", token=token)
    check("定义层未被切片的框架覆盖", (d.get("framework") or {}).get("framework_version") != "SLICE-V1",
          str((d.get("framework") or {}).get("framework_version")))

asyncio.run(main())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
