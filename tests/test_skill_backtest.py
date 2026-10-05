"""技能框架回测与置信度验收（R5'）。

    ~/personal-ontology/.venv/bin/python tests/test_skill_backtest.py

覆盖：
  · 回测算术（50 个案例、39 个一致 → 准确率 0.78，正是设计里的数字）
  · 无案例时置信度保持「未验证」
  · 案例格式错误要明确报错，不能静默跳过
  · 经接口 persist=true 后，场景定义带上 confidence / backtested / 依据
  · 置信度写回后，判定包里能读到它（闭环）
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
from backend.skill_backtest import run_backtest
from backend.skill_framework import judge

FRAMEWORK = {
  "framework_version": "BT-V1",
  "industry_map": {"新能源": "科技/互联网"},
  "thresholds": {"base": 1.3, "adjustments": [
    {"condition": {"行业周期位置": "上升期"}, "delta": 0.15, "reason": "上升期"}]},
  "signals": [
    {"name": "市盈率超阈值", "when": {"市盈率": {"op": "gt", "value": {"ref": "行业平均市盈率", "times": "threshold"}}}},
    {"name": "现金流危机", "when": {"现金流状况": "危机"}}],
  "combination_rules": [
    {"all_of": ["市盈率超阈值"], "conclusion": "估值偏高", "severity": "高"},
    {"all_of": ["现金流危机"], "conclusion": "风险极高", "severity": "极高"}],
  "exception_rules": [], "signal_priority": [{"signal": "现金流危机", "priority": 1}]}

def make_cases(n=50):
    raw = []
    for i in range(n):
        raw.append({"case_id": f"CASE-{i+1:03d}", "行业": "新能源", "行业平均市盈率": 30,
                    "行业周期位置": "上升期" if i % 2 == 0 else "平稳期",
                    "市盈率": 40 + (i % 12), "现金流状况": "危机" if i % 5 == 0 else "健康"})
    cases = []
    for i, data in enumerate(raw):
        decision = judge(FRAMEWORK, data)["decision"]
        # 故意让 11 个案例的"实际结果"与框架结论不同 → 一致 39/50 = 78%
        cases.append({"case_id": f"CASE-{i+1:03d}", "inputs": data,
                      "actual_result": decision if i >= 11 else ("估值合理" if decision != "估值合理" else "估值偏高")})
    return cases

CASES = make_cases(50)

# ── 纯逻辑 ──
rep = run_backtest(FRAMEWORK, CASES)
check("样本数 50", rep["total"] == 50, str(rep["total"]))
check("一致 39 个", rep["matched"] == 39, str(rep["matched"]))
check("准确率 0.78（与设计一致）", rep["accuracy"] == 0.78, str(rep["accuracy"]))
check("置信度状态 backtested", rep["confidence_status"] == "backtested", rep["confidence_status"])
check("不一致明细 11 条", rep["mismatched"] == 11, str(rep["mismatched"]))
check("对比口径已注明", "逐字相等" in rep["comparison_rule"], rep["comparison_rule"])
check("无案例 → 未验证且准确率为空",
      run_backtest(FRAMEWORK, [])["confidence_status"] == "unverified"
      and run_backtest(FRAMEWORK, [])["accuracy"] is None)
try:
    run_backtest(FRAMEWORK, [{"case_id": "X", "inputs": {}}])
    check("缺 actual_result 应报错", False, "没有报错")
except ValueError as exc:
    check("缺 actual_result 明确报错", "actual_result" in str(exc), str(exc))
try:
    run_backtest(FRAMEWORK, [{"case_id": "X", "inputs": "不是对象", "actual_result": "偏高"}])
    check("inputs 非对象应报错", False, "没有报错")
except ValueError as exc:
    check("inputs 非对象明确报错", "inputs" in str(exc), str(exc))

# ── 经接口 ──
async def api_part():
    st, pl = await call("POST", "/v1/setup", body={"password": "Backtest-94!"}); token = pl["token"]
    st, r = await call("POST", "/v1/scenario-definitions/legal.acquisition/backtest",
                       body={"cases": CASES}, token=token)
    check("未配置框架 → 409", st == 409, f"HTTP {st}")
    await call("PATCH", "/v1/scenario-definitions/legal.acquisition",
               body={"framework": FRAMEWORK}, token=token)
    st, r = await call("POST", "/v1/scenario-definitions/legal.acquisition/backtest",
                       body={"cases": "x"}, token=token)
    check("cases 非法 → 422", st == 422, f"HTTP {st}")
    st, r = await call("POST", "/v1/scenario-definitions/legal.acquisition/backtest",
                       body={"cases": [{"inputs": {}}]}, token=token)
    check("案例缺字段 → 422 并说明原因",
          st == 422 and "actual_result" in json.dumps(r, ensure_ascii=False), f"HTTP {st} {str(r)[:120]}")
    st, r = await call("POST", "/v1/scenario-definitions/legal.acquisition/backtest",
                       body={"cases": CASES, "persist": True}, token=token)
    check("回测成功并持久化", st == 200 and r.get("accuracy") == 0.78, f"HTTP {st} {str(r)[:120]}")
    st, one = await call("GET", "/v1/scenario-definitions/legal.acquisition", token=token)
    check("置信度已写回定义（0.78 / backtested）",
          abs(float(one.get("confidence") or 0) - 0.78) < 1e-9 and one.get("confidence_status") == "backtested",
          f"{one.get('confidence')}/{one.get('confidence_status')}")
    check("置信度依据含样本数与准确率",
          "50" in (one.get("confidence_basis") or "") and "78" in (one.get("confidence_basis") or ""),
          str(one.get("confidence_basis"))[:100])
    # 闭环：判定包里能读到置信度
    st, pkg = await call("POST", "/v1/scenario-definitions/legal.acquisition/evaluate",
                         body={"data": {"行业": "新能源", "市盈率": 45, "行业平均市盈率": 30,
                                        "行业周期位置": "上升期", "现金流状况": "健康"}}, token=token)
    check("判定包带出置信度（闭环）",
          abs(float(pkg.get("confidence") or 0) - 0.78) < 1e-9 and pkg.get("confidence_status") == "backtested",
          f"{pkg.get('confidence')}/{pkg.get('confidence_status')}")

asyncio.run(api_part())

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
