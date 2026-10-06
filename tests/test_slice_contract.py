"""调用说明（接口契约）验收：调用方怎么知道要传什么、会给回什么。

    ~/personal-ontology/.venv/bin/python tests/test_slice_contract.py
"""
import asyncio, json, os, pathlib, shutil, sys, tempfile
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

FW = {"billing": {"unit_price": 200, "currency": "CNY"},
      "inputs": [{"name": "行业", "type": "string", "hint": "标的所属行业"},
                 {"name": "市盈率", "type": "number", "unit": "倍"},
                 {"name": "是否已专利化", "type": "bool"}],
      "industry_weights": {"科技": {"技术": 0.5, "财务": 0.2}},
      "thresholds": {"base": 1.0, "adjustments": [{"delta": 0.2}]},
      "signals": [{"name": "市盈率超阈值", "dimension": "财务"}],
      "combination_rules": [{"all_of": ["市盈率超阈值"], "conclusion": "偏高"}],
      "citations": [{"text": "内部规范第12条", "signals": ["市盈率超阈值"]}],
      "confidence_basis": "我十五年的经验"}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Ocean-Tide-74!"}); tok = pl["token"]
    await call("POST", "/v1/scenario-slices", body={"id": "s.c", "original_text": "原始描述", "status": "analyzed",
        "scenario_profile": {"kind": "professional"}, "analysis": {"title": "并购估值"},
        "updated_at": "2026-10-07T00:00:00"}, token=tok)

    st, c = await call("GET", "/v1/scenario-slices/s.c/contract", token=tok)
    check("未启用时也能取到调用说明（但标明未启用）",
          st == 200 and c.get("enabled") is False, f"HTTP {st} enabled={c.get('enabled')}")

    await call("PATCH", "/v1/scenario-slices/s.c", body={"framework": FW, "status": "confirmed",
        "boundaries": {"max_amount": 10**6, "allowed_scenarios": ["估值"], "confidentiality": "不得转售"},
        "delivery": {}}, token=tok)
    st, c = await call("GET", "/v1/scenario-slices/s.c/contract", token=tok)
    raw = json.dumps(c, ensure_ascii=False)
    names = [f.get("name") for f in (c.get("fields") or [])]
    check("说明里列出要传的字段名与类型",
          names == ["行业", "市盈率", "是否已专利化"] and [f.get("type") for f in c["fields"]] == ["string", "number", "bool"],
          str(c.get("fields"))[:160])
    check("每个字段都标明必填，并说明缺项后果",
          c.get("all_fields_required") is True and "信息不足" in str(c.get("on_missing")),
          str(c.get("on_missing"))[:80])
    check("给出调用方式（方法与路径）与请求体形状",
          "/judge" in str(c.get("how_to_call")) and "data" in str(c.get("how_to_call")),
          str(c.get("how_to_call"))[:120])
    check("给出边界：允许用途 / 金额上限 / 不转售要求",
          c.get("allowed_purposes") == ["估值"] and c.get("max_amount") == 10**6 and c.get("no_resale_required") is True,
          json.dumps({k: c.get(k) for k in ("allowed_purposes", "max_amount", "no_resale_required")}, ensure_ascii=False))
    check("说明会给回哪些字段", "decision" in (c.get("you_will_receive") or []), str(c.get("you_will_receive")))
    check("说明计费（演示）：单价与币种", (c.get("billing") or {}).get("unit_price") == 200,
          json.dumps(c.get("billing"), ensure_ascii=False))
    # 只看真实字段，别拿整串 JSON 去搜关键词（"you_will_not_receive" 里本来就会列出这些名字）
    keys = set(c.keys()) | set((c.get("billing") or {}).keys())
    leaked = [k for k in ("industry_weights", "thresholds", "combination_rules", "framework",
                          "confidence_basis", "dynamic_threshold", "signals") if k in keys]
    check("调用说明里【不含】权重/阈值/组合规则/置信度理由（第七步）", not leaked, "泄露字段：" + str(leaked))

asyncio.run(main())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
