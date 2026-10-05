"""技能框架判定接口验收（R3'.1）。

    ~/personal-ontology/.venv/bin/python tests/test_skill_evaluate_api.py

链路：把框架写进场景定义（PATCH）→ 调判定接口 → 拿到判定包。
同时验证：没有框架时明确报错、定义不存在时报 404、输入非法报 422；
以及**内置记录升级不得抹掉用户后加的框架**（这是刚修掉的数据丢失隐患）。
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

FRAMEWORK = {
  "skill_id": "SKILL-MA-VALUATION-001", "framework_version": "JUDGMENT-FRAMEWORK-V2",
  "industry_map": {"新能源": "科技/互联网"},
  "industry_weights": {"科技/互联网": {"tech": 0.35, "team": 0.25, "financial": 0.20, "market": 0.20}},
  "thresholds": {"base": 1.3, "adjustments": [
    {"condition": {"行业周期位置": "上升期"}, "delta": 0.15, "reason": "上升期可容忍更高溢价"}]},
  "signals": [
    {"name": "市盈率超阈值", "when": {"市盈率": {"op": "gt", "value": {"ref": "行业平均市盈率", "times": "threshold"}}}},
    {"name": "客户集中度 > 50%", "when": {"客户集中度": {"op": "gt", "value": 50}}},
    {"name": "团队流失风险 = 高", "when": {"核心团队流失风险": "高"}}],
  "combination_rules": [
    {"all_of": ["市盈率超阈值", "客户集中度 > 50%", "团队流失风险 = 高"], "conclusion": "估值偏高", "severity": "高"}],
  "exception_rules": [], "signal_priority": [{"signal": "团队流失风险 = 高", "priority": 3}]}
CASE = {"行业": "新能源", "市盈率": 45, "行业平均市盈率": 30, "客户集中度": 65,
        "核心团队流失风险": "高", "行业周期位置": "上升期"}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Skill-Api-94!"}); token = pl["token"]

    # ① 没有框架时要明确报错（不能静默给结论）
    # 同时验证：错误文案会按 X-Display-Language 解析成对应语言（不是抛原始消息键）
    st, r = await call("POST", "/v1/scenario-definitions/legal.acquisition/evaluate",
                       body={"data": CASE}, token=token, headers={"X-Display-Language": "en"})
    check("未配置框架 → 409 明确报错", st == 409, f"HTTP {st} {str(r)[:100]}")
    check("报错文案按显示语言英文化", "skill framework" in json.dumps(r, ensure_ascii=False), str(r)[:140])

    # ② 不存在的定义 → 404
    st, r = await call("POST", "/v1/scenario-definitions/legal.nope/evaluate", body={"data": CASE}, token=token)
    check("定义不存在 → 404", st == 404, f"HTTP {st}")

    # ③ 写入框架（走通用 PATCH，无需专属端点）
    st, r = await call("PATCH", "/v1/scenario-definitions/legal.acquisition",
                       body={"framework": FRAMEWORK, "confidence": 0.78,
                             "confidence_status": "backtested",
                             "confidence_basis": "基于50个历史案例回测，准确率78%"}, token=token)
    check("框架可经通用 PATCH 写入", st in (200, 201), f"HTTP {st} {str(r)[:100]}")
    st, one = await call("GET", "/v1/scenario-definitions/legal.acquisition", token=token)
    check("框架读回为对象", isinstance(one.get("framework"), dict)
          and one["framework"].get("framework_version") == "JUDGMENT-FRAMEWORK-V2", str(one.get("framework"))[:80])

    # ④ 判定
    st, pkg = await call("POST", "/v1/scenario-definitions/legal.acquisition/evaluate",
                         body={"data": CASE}, token=token)
    check("判定成功（200）", st == 200, f"HTTP {st} {str(pkg)[:120]}")
    check("结论 估值偏高", pkg.get("decision") == "估值偏高", str(pkg.get("decision")))
    check("严重度 高", pkg.get("severity") == "高", str(pkg.get("severity")))
    check("动态阈值 1.45", abs(float(pkg.get("threshold") or 0) - 1.45) < 1e-9, str(pkg.get("threshold")))
    check("推理路径 6 步", len(pkg.get("reasoning_path") or []) == 6, str(len(pkg.get("reasoning_path") or [])))
    check("证据含动态阈值 43.5",
          any(e.get("dynamic_threshold") == "43.5" for e in pkg.get("evidence") or []), str(pkg.get("evidence"))[:120])
    check("置信度透传（0.78 / backtested）",
          abs(float(pkg.get("confidence") or 0) - 0.78) < 1e-9 and pkg.get("confidence_status") == "backtested",
          f"{pkg.get('confidence')}/{pkg.get('confidence_status')}")
    check("回带 definition_id", pkg.get("definition_id") == "legal.acquisition", str(pkg.get("definition_id")))

    # ⑤ 非法输入 → 422
    st, r = await call("POST", "/v1/scenario-definitions/legal.acquisition/evaluate", body={"data": "x"}, token=token)
    check("非法输入 → 422", st == 422, f"HTTP {st}")

    # ⑥ 内置记录升级不得抹掉用户后加的 framework（刚修的数据丢失隐患）
    from backend import api as api_module
    api_module.store._ensure_builtins()
    st, again = await call("GET", "/v1/scenario-definitions/legal.acquisition", token=token)
    check("再次播种后框架仍在（用户字段不被覆盖）",
          isinstance(again.get("framework"), dict) and abs(float(again.get("confidence") or 0) - 0.78) < 1e-9,
          f"framework={'有' if again.get('framework') else '无'} confidence={again.get('confidence')}")

    p = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok, l in RESULTS:
        if not ok: print("  失败：", l)

asyncio.run(main()); shutil.rmtree(work, ignore_errors=True)
