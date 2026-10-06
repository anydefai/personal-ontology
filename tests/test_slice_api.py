"""切片层判定接口与迁移验收。

    ~/personal-ontology/.venv/bin/python tests/test_slice_api.py

要点：框架/边界/置信度/反馈都取自并写回**切片**；定义上的旧框架可一键搬到切片且幂等。
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

FW = {"framework_version": "SLICE-V2", "thresholds": {"base": 1.0, "adjustments": []},
      "signals": [{"name": "偏高", "when": {"市盈率": {"op": "gt", "value": 39}}}],
      "combination_rules": [{"all_of": ["偏高"], "conclusion": "估值偏高", "severity": "高"}]}
SLICE = {"id": "slice.ma.mine", "original_text": "我的收购评估", "status": "analyzed",
         "scenario_definition_id": "test.scenario", "scenario_profile": {"kind": "professional"},
         "analysis": {"title": "我的收购评估"}, "updated_at": "2026-10-06T00:00:00",
         "framework": FW, "insight": "同时看行业周期与监管", "owner_credentials": "执业 15 年",
         "valid_days": 3,
         "boundaries": {"max_amount": 1000000000, "allowed_scenarios": ["并购尽调"],
                        "default_tier": "professional"}}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "SliceApi-94!"})
    assert "token" in pl, f"setup 失败 {st} {pl}"
    token = pl["token"]
    # 测试自建场景（不依赖内置种子：内置场景已按用户要求删除）
    for _sid, _zh in (("test.scenario", "测试场景"), ("test.scenario2", "测试场景二")):
        await call("POST", "/v1/scenario-definitions", body={
            "id": _sid, "display_name_zh": _zh, "display_name_en": _zh,
            "domain_pack_ids": ["legal.cn"], "version": "1.0.0",
            "lifecycle_state": "active", "is_builtin": False}, token=token)

    # ① 判定取自切片
    st, r = await call("POST", "/v1/scenario-slices/slice.nope/evaluate", body={"data": {}}, token=token)
    check("切片不存在 → 404", st == 404, f"HTTP {st}")
    await call("POST", "/v1/scenario-slices", body=SLICE, token=token)
    st, pkg = await call("POST", "/v1/scenario-slices/slice.ma.mine/evaluate",
                         body={"data": {"市盈率": 45}, "tier": "audit"}, token=token)
    check("用切片框架判定成功", st == 200 and pkg.get("decision") == "估值偏高", f"HTTP {st} {str(pkg)[:80]}")
    check("回带 slice_id 与来源定义", pkg.get("slice_id") == "slice.ma.mine"
          and pkg.get("definition_id") == "test.scenario", f"{pkg.get('slice_id')}/{pkg.get('definition_id')}")
    st, prof = await call("POST", "/v1/scenario-slices/slice.ma.mine/evaluate",
                          body={"data": {"市盈率": 45}}, token=token)
    check("不指定层级时取切片的默认层级（professional）", prof.get("tier") == "professional", str(prof.get("tier")))
    check("专业层不含资历/审计号（分层口径正确）",
          "owner_credentials" not in prof and "audit_id" not in prof, str(sorted(prof)))
    check("交付身份信息来自切片（资历/审计号/有效期）",
          pkg.get("owner_credentials") == "执业 15 年" and str(pkg.get("audit_id", "")).startswith("AUDIT-")
          and pkg.get("valid_until"), f"{pkg.get('owner_credentials')} / {pkg.get('audit_id')}")

    # ② 边界取自切片：超上限 → 需确认
    st, a = await call("POST", "/v1/scenario-slices/slice.ma.mine/authorize",
                       body={"caller": "法智AI", "purpose": "并购尽调", "scenario": "并购尽调",
                             "amount": 500000000, "no_resale": True}, token=token)
    check("授权判定用切片边界 → 允许", st == 200 and a.get("result") == "allow", f"{st} {a.get('result')}")
    st, a = await call("POST", "/v1/scenario-slices/slice.ma.mine/authorize",
                       body={"caller": "法智AI", "purpose": "并购尽调", "scenario": "并购尽调",
                             "amount": 99000000000, "no_resale": True}, token=token)
    check("超上限 → 需确认（用切片边界）", a.get("result") == "confirm", str(a.get("result")))

    # ③ 回测把置信度写回切片
    cases = [{"case_id": "C1", "inputs": {"市盈率": 45}, "actual_result": "估值偏高"},
             {"case_id": "C2", "inputs": {"市盈率": 20}, "actual_result": "估值偏高"}]
    st, rep = await call("POST", "/v1/scenario-slices/slice.ma.mine/backtest",
                         body={"cases": cases, "persist": True}, token=token)
    check("回测成功", st == 200 and rep.get("accuracy") == 0.5, f"{st} {rep.get('accuracy')}")
    st, one = await call("GET", "/v1/scenario-slices/slice.ma.mine", token=token)
    check("置信度写回切片（0.5 / backtested）",
          abs(float(one.get("confidence") or 0) - 0.5) < 1e-9 and one.get("confidence_status") == "backtested",
          f"{one.get('confidence')}/{one.get('confidence_status')}")

    # ④ 反馈写回切片
    for _ in range(10):
        st, fb = await call("POST", "/v1/scenario-slices/slice.ma.mine/judgment-feedback",
                            body={"verdict": "accurate"}, token=token)
    check("10 次反馈 → 切片置信度升为 preliminary", fb.get("confidence_status") == "preliminary", str(fb))
    st, one = await call("GET", "/v1/scenario-slices/slice.ma.mine", token=token)
    check("反馈计数写回切片", one.get("feedback_total") == 10 and one.get("feedback_accurate") == 10,
          f"{one.get('feedback_total')}/{one.get('feedback_accurate')}")

    # ⑤ 草稿：描述过短 422
    st, r = await call("POST", "/v1/scenario-slices/slice.ma.mine/draft", body={"description": "短"}, token=token)
    check("切片草稿：描述过短 → 422", st == 422, f"HTTP {st}")

    # ⑦ 正式交付：写判定记录；预演不写
    st, d1 = await call("POST", "/v1/scenario-slices/slice.ma.mine/deliver",
                        body={"data": {"市盈率": 45}}, token=token)
    check("正式交付成功且标记已记录", st == 200 and d1.get("recorded") is True, f"{st} {d1.get('recorded')}")
    check("交付带审计号/有效期/内容指纹/签名状态",
          str(d1.get("audit_id", "")).startswith("AUDIT-") and d1.get("valid_until")
          and d1.get("content_fingerprint") and d1.get("signature_status") == "not_implemented",
          f"{d1.get('audit_id')} / {d1.get('signature_status')}")
    check("交付回带 decision_id", str(d1.get("decision_id", "")).startswith("decision.deliver."),
          str(d1.get("decision_id")))
    st, decs = await call("GET", "/v1/decisions", token=token)
    items = (decs.get("items") if isinstance(decs, dict) else decs) or []
    mine = [x for x in items if str(x.get("phase") or "") == "pre_execution"
            and (x.get("reason_key") or "") == "skill_delivery"]
    check("交付记录可通过 /v1/decisions 列出", st == 200 and len(mine) >= 1, f"{st} {len(mine)}")
    st, _ev = await call("POST", "/v1/scenario-slices/slice.ma.mine/evaluate",
                         body={"data": {"市盈率": 45}}, token=token)
    st2, decs2 = await call("GET", "/v1/decisions", token=token)
    items2 = (decs2.get("items") if isinstance(decs2, dict) else decs2) or []
    mine2 = [x for x in items2 if (x.get("reason_key") or "") == "skill_delivery"]
    check("预演不写记录（交付记录数不变）", len(mine2) == len(mine), f"{len(mine)} → {len(mine2)}")

    # ⑥ 迁移：定义上的框架搬到切片，且幂等
    await call("PATCH", "/v1/scenario-definitions/test.scenario2",
               body={"framework": dict(FW, framework_version="FROM-DEF"), "insight": "旧位置"}, token=token)
    st, mv = await call("POST", "/v1/scenario-slices/migrate-from-definitions", token=token)
    check("迁移创建了切片", st == 200 and mv.get("count") == 1, f"{st} {json.dumps(mv, ensure_ascii=False)[:120]}")
    new_slice = (mv.get("moved") or [{}])[0].get("slice_id")
    st, one = await call("GET", f"/v1/scenario-slices/{new_slice}", token=token)
    check("框架已搬到新切片", (one.get("framework") or {}).get("framework_version") == "FROM-DEF",
          str((one.get("framework") or {}).get("framework_version")))
    check("洞察也一并搬走", one.get("insight") == "旧位置", str(one.get("insight")))
    st, d = await call("GET", "/v1/scenario-definitions/test.scenario2", token=token)
    check("定义上的个人字段已清空（保持可共享的干净）", not d.get("framework") and not d.get("insight"),
          f"{bool(d.get('framework'))}/{d.get('insight')}")
    st, mv2 = await call("POST", "/v1/scenario-slices/migrate-from-definitions", token=token)
    check("迁移幂等（再调一次不再搬）", mv2.get("count") == 0, str(mv2.get("count")))

asyncio.run(main())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
