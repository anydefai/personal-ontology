"""第一层授权判定验收（C2）。

    ~/personal-ontology/.venv/bin/python tests/test_authorization.py

口径来自设计原文：**超出金额上限不是拒绝，而是"需本人确认"**；
没有声明边界的场景**默认拒绝**（空白不等于默许）。
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
from backend.authorization import authorize

B = {"max_amount": 1000000000, "allowed_scenarios": ["并购尽调", "投资决策"], "confidentiality": "不得转售"}
REQ = {"caller": "法智AI", "purpose": "并购尽调", "scenario": "并购尽调", "amount": 500000000, "no_resale": True}

r = authorize(B, REQ)
check("范围内的调用 → 允许", r["result"] == "allow", json.dumps(r, ensure_ascii=False)[:160])
check("逐项检查都有明细", len(r["checks"]) >= 5 and all("check" in c for c in r["checks"]), str(len(r["checks"])))

r = authorize(B, dict(REQ, amount=1500000000))
check("超出金额上限 → 需本人确认（不是拒绝）", r["result"] == "confirm", r["result"])
check("确认态标明超限", r["over_limit"] is True and "本人确认" in r["note"], r["note"])

r = authorize(B, dict(REQ, scenario="劳动合规", purpose="劳动合规"))
check("用途不在允许范围 → 拒绝", r["result"] == "deny", r["result"])
r = authorize(B, dict(REQ, no_resale=False))
check("未承诺不得转售 → 拒绝", r["result"] == "deny", r["result"])
r = authorize(B, dict(REQ, caller=""))
check("缺调用方 → 拒绝", r["result"] == "deny", r["result"])
r = authorize(B, dict(REQ, amount=None))
check("缺金额 → 拒绝", r["result"] == "deny" and any(c["check"] == "金额可读" for c in r["checks"]), r["result"])
r = authorize(None, REQ)
check("没有声明边界 → 默认拒绝", r["result"] == "deny", r["result"])
r = authorize({"max_amount": 1000000000}, REQ)
check("未声明允许用途 → 拒绝", r["result"] == "deny", r["result"])
r = authorize({"max_amount": 1000000000, "allowed_scenarios": ["并购尽调"]}, dict(REQ, no_resale=False))
check("边界允许但调用方未承诺不转售 → 拒绝", r["result"] == "deny", r["result"])

async def api_part():
    st, pl = await call("POST", "/v1/setup", body={"password": "Auth-94!"}); token = pl["token"]
    st, _ = await call("POST", "/v1/scenario-definitions/legal.nope/authorize", body=REQ, token=token)
    check("定义不存在 → 404", st == 404, f"HTTP {st}")
    st, one = await call("POST", "/v1/scenario-definitions/legal.acquisition/authorize", body=REQ, token=token)
    check("未设边界的内置场景 → 拒绝（默认拒绝）", st == 200 and one.get("result") == "deny", f"HTTP {st} {one.get('result')}")
    await call("PATCH", "/v1/scenario-definitions/legal.acquisition", body={"boundaries": B}, token=token)
    st, one = await call("POST", "/v1/scenario-definitions/legal.acquisition/authorize", body=REQ, token=token)
    check("设好边界后 → 允许", st == 200 and one.get("result") == "allow", f"HTTP {st} {one.get('result')}")
    st, one = await call("POST", "/v1/scenario-definitions/legal.acquisition/authorize",
                         body=dict(REQ, amount=1500000000), token=token)
    check("经接口：超限 → 需确认", st == 200 and one.get("result") == "confirm", one.get("result"))
    check("回带 definition_id", one.get("definition_id") == "legal.acquisition", str(one.get("definition_id")))

asyncio.run(api_part())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
