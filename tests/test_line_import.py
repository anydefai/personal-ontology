"""逐行导入接口验收（含"导入即可判定"的闭环）。

    ~/personal-ontology/.venv/bin/python tests/test_line_import.py
"""
import pathlib, asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

TEXTS = {
 "inputs": "市盈率 ｜ 数字\n行业平均市盈率 ｜ 数字\n客户集中度 ｜ 数字\n核心团队流失风险 ｜ 选项 ｜ 高、中、低\n行业周期位置 ｜ 选项 ｜ 上升期、平稳期、下行期\n行业 ｜ 文字",
 "thresholds": "基准 1.3\n行业周期位置=上升期 → +0.15",
 "signals": "市盈率超阈值 = 市盈率 大于 行业平均市盈率 × 基准线\n客户集中度>50 = 客户集中度 大于 50\n团队流失高 = 核心团队流失风险 等于 高",
 "rules": "市盈率超阈值 且 客户集中度>50 且 团队流失高 → 估值偏高（高）",
 "exceptions": "监管环境=收紧 且 行业=金融 → 直接判 估值偏高",
 "priority": "团队流失高 > 市盈率超阈值",
}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "LineImp-94!"})
    assert "token" in pl, f"setup 失败 {st} {pl}"
    token = pl["token"]
    await call("POST", "/v1/scenario-slices", body={"id": "s.line", "original_text": "逐行测试",
        "status": "analyzed", "scenario_definition_id": "test.scenario",
        "scenario_profile": {"kind": "professional"}, "analysis": {"title": "逐行测试"},
        "updated_at": "2026-10-06T00:00:00"}, token=token)

    st, r = await call("POST", "/v1/scenario-slices/s.line/import-lines",
                       body={"texts": TEXTS, "save": True}, token=token)
    check("逐行导入成功", st == 200 and r.get("saved") is True, f"HTTP {st} {str(r)[:120]}")
    check("无错误行", r.get("error_count") == 0, json.dumps(r.get("report"), ensure_ascii=False)[:160])
    fw = r.get("framework") or {}
    check("阈值 1.3 + 1 条调整", fw.get("thresholds", {}).get("base") == 1.3
          and len(fw["thresholds"]["adjustments"]) == 1, str(fw.get("thresholds")))
    check("信号 3 条且含阈值引用",
          len(fw.get("signals") or []) == 3
          and fw["signals"][0]["when"]["市盈率"]["value"].get("times") == "threshold", str(fw.get("signals"))[:120])
    check("原样输入已存进 framework.source", isinstance(fw.get("source"), dict) and "inputs" in fw["source"])

    # 写坏一行：只报那一行，其余照常导入
    st, r2 = await call("POST", "/v1/scenario-slices/s.line/import-lines",
                        body={"texts": {"inputs": "市盈率 ｜ 数字\n坏行 ｜ 瞎写的类型"}, "save": False}, token=token)
    check("坏行只影响那一行并报出行号",
          r2.get("error_count") == 1 and r2["report"]["inputs"]["errors"][0]["line"] == 2,
          json.dumps(r2.get("report"), ensure_ascii=False)[:160])
    check("同一份输入里好行仍被导入", len(r2["framework"]["inputs"]) == 1, str(r2["framework"]["inputs"]))
    check("未 save 时不写回切片",
          (await call("GET", "/v1/scenario-slices/s.line", token=token))[1].get("framework", {}).get("thresholds", {}).get("base") == 1.3)

    # 闭环：导入后直接判定
    st, pkg = await call("POST", "/v1/scenario-slices/s.line/evaluate",
                         body={"data": {"行业": "新能源", "市盈率": 45, "行业平均市盈率": 30,
                                        "客户集中度": 65, "核心团队流失风险": "高",
                                        "行业周期位置": "上升期"}, "tier": "audit"}, token=token)
    check("导入即可判定：结论 估值偏高", st == 200 and pkg.get("decision") == "估值偏高",
          f"HTTP {st} {str(pkg.get('decision'))}")
    check("闭环：动态阈值 1.45", abs(float(pkg.get("threshold") or 0) - 1.45) < 1e-9, str(pkg.get("threshold")))

asyncio.run(main())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
