import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

SLOTS = {"premise", "conclusion", "exception", "basis"}
DAILY = {"title": "订酒店", "facts": [], "questions": [], "scope": {"mode": "global"},
         "resource_types": [{"name": "酒店"}], "actions": [{"name": "预订酒店"}],
         "required_inputs": [{"name": "budget_per_night", "label": "每晚预算", "type": "number",
                              "required": True, "role": "preference", "role_reason": "长期立场"}],
         "policies": []}

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Prof-Model-94!"}); token = pl["token"]

    # —— ① 内置领域包与场景骨架 ——
    st, packs = await call("GET", "/v1/domain-packs", token=token)
    ids = [i["id"] for i in packs["items"]]
    check("内置法律领域包 legal.cn 已播种", "legal.cn" in ids, str(ids))
    st, defs = await call("GET", "/v1/scenario-definitions", token=token)
    dids = sorted(i["id"] for i in defs["items"])
    check("内置 3 个法律场景骨架", dids == ["legal.acquisition", "legal.contract", "legal.labor"], str(dids))
    check("内置数据不重复（id 唯一）", len(dids) == len(set(dids)), str(dids))

    st, one = await call("GET", "/v1/scenario-definitions/legal.acquisition", token=token)
    check("双语显示名齐全", one.get("display_name_zh") == "收购评估" and one.get("display_name_en") == "Acquisition assessment",
          f"{one.get('display_name_zh')} / {one.get('display_name_en')}")
    check("多值关系回读为数组", one.get("domain_pack_ids") == ["legal.cn"], str(one.get("domain_pack_ids")))
    slots = one.get("entry_slots") or {}
    check("四槽结构完整", set(slots) == SLOTS, str(list(slots)))
    check("四槽标签中英双语", all(isinstance(v, dict) and "zh" in v and "en" in v for v in slots.values()), str(slots))
    # 内置场景骨架来自工程实现，**不得携带任何编造的专业前提要素**（2026-10-04 决定撤掉自造示例）
    check("内置场景不携带编造的前提要素", one.get("premise_fields") in (None, []),
          str(one.get("premise_fields"))[:80])

    # —— ② 存量兼容：不带 profile 的日常切片行为不变 ——
    st, _ = await call("POST", "/v1/scenario-slices",
                       body={"original_text": "订酒店", "status": "analyzed", "analysis": DAILY,
                             "updated_at": "2026-01-01T00:00:00Z"}, token=token)
    check("无 profile 的切片仍可创建（存量兼容）", st in (200, 201), f"HTTP {st}")
    st, lst = await call("GET", "/v1/scenario-slices", token=token)
    daily_id = lst["items"][0]["id"]
    st, d = await call("GET", f"/v1/scenario-slices/{daily_id}", token=token)
    check("存量切片读回不出现新增字段", not d.get("scenario_profile") and not d.get("scenario_definition_id"),
          f"profile={d.get('scenario_profile')!r} def={d.get('scenario_definition_id')!r}")
    check("存量切片原有字段完好", d.get("status") == "analyzed" and d.get("original_text") == "订酒店",
          f"status={d.get('status')}")

    # —— ③ 专业切片：挂到场景定义上 ——
    st, _ = await call("POST", "/v1/scenario-slices",
                       body={"original_text": "收购评估：判断是否需要经营者集中申报",
                             "status": "analyzed", "analysis": {"title": "收购评估"},
                             "scenario_definition_id": "legal.acquisition",
                             "scenario_profile": {"kind": "professional", "domain_pack_ids": ["legal.cn"]},
                             "updated_at": "2026-01-02T00:00:00Z"}, token=token)
    check("专业切片可创建并挂到场景定义", st in (200, 201), f"HTTP {st} {str(_)[:100]}")
    st, lst = await call("GET", "/v1/scenario-slices", token=token)
    pro = [i for i in lst["items"] if i.get("scenario_definition_id")]
    check("专业切片的关系已写入", len(pro) == 1 and pro[0]["scenario_definition_id"] == "legal.acquisition",
          str([i.get("scenario_definition_id") for i in lst["items"]]))
    pro_id = pro[0]["id"]
    st, pr = await call("GET", f"/v1/scenario-slices/{pro_id}", token=token)
    check("profile JSON 回读为对象", isinstance(pr.get("scenario_profile"), dict)
          and pr["scenario_profile"].get("kind") == "professional", str(pr.get("scenario_profile")))

    # —— ④ 判断条目 ——
    entries = [
        {"conclusion": "达到申报标准，应先申报后实施", "exception": "未取得控制权时不适用",
         "basis": "《反垄断法》第二十六条", "authority": "statute"},
        {"conclusion": "需核查目标公司章程中的优先购买权条款", "exception": "股东已放弃时除外",
         "basis": "公司法第七十一条", "authority": "statute"},
        {"conclusion": "建议在交割条件中加入监管审批先决条件", "exception": "",
         "basis": "既往交易经验", "authority": "experience"},
    ]
    for i, e in enumerate(entries):
        st, _ = await call("POST", "/v1/knowledge-entries",
                           body={"slice_id": pro_id, "premise": {"jurisdiction": "上海", "idx": i},
                                 "review_state": "draft", "version": "1", **e}, token=token)
        check(f"条目 {i+1} 创建", st in (200, 201), f"HTTP {st} {str(_)[:100]}")
    st, ents = await call("GET", "/v1/knowledge-entries", token=token)
    check("3 条判断条目已建立", len(ents["items"]) == 3, str(len(ents["items"])))
    eid = ents["items"][0]["id"]
    st, e1 = await call("GET", f"/v1/knowledge-entries/{eid}", token=token)
    check("条目关系指回切片", e1.get("slice_id") == pro_id, f"{e1.get('slice_id')} vs {pro_id}")
    check("条目前提 JSON 回读为对象", isinstance(e1.get("premise"), dict), str(e1.get("premise"))[:80])
    check("条目四槽字段齐全", all(k in e1 for k in ("premise", "conclusion", "exception", "basis")), str(sorted(e1)))
    check("条目状态默认可为 draft", e1.get("review_state") == "draft", str(e1.get("review_state")))

    # —— ⑤ 幂等：内置数据不因再次读取而增加 ——
    st, again = await call("GET", "/v1/scenario-definitions", token=token)
    check("内置场景骨架数量稳定（幂等）", len(again["items"]) == len(defs["items"]), f"{len(again['items'])} vs {len(defs['items'])}")

    p = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok, l in RESULTS:
        if not ok: print("  失败：", l)

asyncio.run(main()); shutil.rmtree(work, ignore_errors=True)
