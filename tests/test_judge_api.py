"""对外判定接口验收（给调用方用的那个口子）。

三层校验：
  ① 未启用 → 409（不对外）
  ② 边界未声明 / 除 allow 外 → 一律不给结论（宁拒答，不递出结论）
  ③ 缺必填 → 约定 B：信息不足，无法判断
    ~/personal-ontology/.venv/bin/python tests/test_judge_api.py
"""
import asyncio, json, os, pathlib, shutil, sys, tempfile
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

FW = {"inputs": [{"name": "行业", "type": "string"}, {"name": "市盈率", "type": "number"}],
      "thresholds": {"base": 1.0, "adjustments": []},
      "signals": [{"name": "贵", "when": {"市盈率": {"op": "gt", "value": 30}}}],
      "combination_rules": [{"all_of": ["贵"], "conclusion": "偏高", "severity": "高"}],
      "fallback": {"conclusion": "合理", "severity": "低"}}
BND = {"max_amount": 1000000, "allowed_scenarios": ["并购尽调"], "confidentiality": "调用方不得转售结论"}
REQ = {"caller": "某律所平台", "purpose": "并购尽调", "amount": 1000,
       "no_resale": True}   # 边界要求调用方承诺不转售（字段名是 no_resale）
DATA = {"行业": "x", "市盈率": 45}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "JudgeApi-94!"})
    token = pl["token"]
    await call("POST", "/v1/scenario-slices", body={"id": "s.j", "original_text": "x", "status": "analyzed",
        "scenario_profile": {"kind": "professional"}, "analysis": {"title": "x"},
        "updated_at": "2026-10-06T00:00:00"}, token=token)

    st, r = await call("POST", "/v1/scenario-slices/s.j/judge", body={"data": DATA, "request": REQ}, token=token)
    check("未启用 → 409（不能对外调用）", st == 409 and r.get("detail", {}).get("error") == "slice_not_enabled",
          f"HTTP {st} {json.dumps(r, ensure_ascii=False)[:120]}")

    await call("PATCH", "/v1/scenario-slices/s.j", body={"framework": FW, "status": "confirmed"}, token=token)

    st, r = await call("POST", "/v1/scenario-slices/s.j/judge", body={"data": DATA, "request": REQ}, token=token)
    check("边界未声明 → 不给结论（默认不放行）",
          st == 200 and r.get("judgment") is None and r.get("refused") == "boundaries",
          f"HTTP {st} judge={r.get('judgment')} refused={r.get('refused')}")

    await call("PATCH", "/v1/scenario-slices/s.j", body={"boundaries": BND}, token=token)
    st, r = await call("POST", "/v1/scenario-slices/s.j/judge", body={"data": DATA, "request": REQ}, token=token)
    check("边界允许 + 数据齐全 → 正常判定", st == 200 and (r.get("judgment") or {}).get("decision") == "偏高",
          f"HTTP {st} authz={json.dumps(r.get('authorize'), ensure_ascii=False)[:140]}")

    st, r = await call("POST", "/v1/scenario-slices/s.j/judge",
                       body={"data": {"行业": "x"}, "request": REQ}, token=token)
    j = r.get("judgment") or {}
    check("缺必填 → 信息不足（约定 B，在边界允许之后才判定）",
          st == 200 and j.get("decision") == "信息不足，无法判断" and j.get("missing_inputs") == ["市盈率"],
          f"HTTP {st} {json.dumps(j, ensure_ascii=False)[:140]}")

    st, r = await call("POST", "/v1/scenario-slices/s.j/judge",
                       body={"data": DATA, "request": dict(REQ, amount=9999999)}, token=token)
    check("金额超限 → 不给结论", st == 200 and r.get("judgment") is None and r.get("refused") == "boundaries",
          f"HTTP {st} judge={r.get('judgment')}")

    st, r = await call("POST", "/v1/scenario-slices/s.j/judge",
                       body={"data": DATA, "request": {"caller": "某平台", "purpose": "别的事", "amount": 1}},
                       token=token)
    check("用途不在允许范围 → 不给结论", st == 200 and r.get("judgment") is None, str(r.get("refused")))

    check("返回里带调用方身份（会话/agent:key）", bool(r.get("caller")), str(r.get("caller"))[:30])

asyncio.run(main())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
