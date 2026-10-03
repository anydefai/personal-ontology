"""时间/日期约束的端到端自检（temporal_lte / temporal_gte）。

    ~/personal-ontology/.venv/bin/python tests/test_temporal.py

覆盖：时间点（15:00 / 15:30:00 / 下午4点）、日期（ISO / 斜杠 / 中文）、日期与日期时间混比、
无法解析时保守不命中、数值比较不受影响。判定必须在补齐必填项后进行，否则会被
"required_context_missing" 提前拦下，测不到规则匹配。
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work=tempfile.mkdtemp(prefix="t9-"); os.environ["PERSONAL_ONTOLOGY_DATA"]=work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
from backend.store import parse_temporal
from backend.api import RELATIVE_TIME_PATTERN


def check_parsers():
    """中英文必须同等支持：解析器只认中文就是缺陷。"""
    print("=== 0. 时间解析（中英双语）===")
    for value, expected in [("15:00", "time"), ("15:00:30", "time"), ("15点30分", "time"), ("下午3点", "time"),
                            ("上午10点", "time"), ("3 PM", "time"), ("3pm", "time"), ("3:30 PM", "time"),
                            ("11:59 p.m.", "time"), ("12:00 am", "time"),
                            ("2026-10-10", "date"), ("2026/10/10", "date"), ("2026.10.10", "date"),
                            ("2026年10月10日", "date"), ("Oct 10, 2026", "date"), ("10 October 2026", "date"),
                            ("10th Oct, 2026", "date"), ("2026-10-10T15:00:00", "datetime")]:
        parsed = parse_temporal(value)
        check(f"解析 {value!r} → {expected}", bool(parsed) and parsed[0] == expected, str(parsed))
    for value in ["05/10/2026", "15/13/2026", "400", "今天", "next week", "", "不是时间"]:
        check(f"拒绝解析 {value!r}", parse_temporal(value) is None, str(parse_temporal(value)))
    for value in ["下周三", "本周五", "3天后", "明天", "next week", "in 3 days", "this Friday", "asap"]:
        check(f"识别相对时间 {value!r}", bool(RELATIVE_TIME_PATTERN.match(value)))
    for value in ["15:00", "2026-10-10", "北京", "无烟房"]:
        check(f"不误判为相对时间 {value!r}", not RELATIVE_TIME_PATTERN.match(value))

ANALYSIS={"title":"预订酒店","facts":[],"required_inputs":[],"resource_types":[{"name":"酒店"}],
 "actions":[{"name":"预订酒店","risk":"medium"}],"questions":[],
 "policies":[{"subject":"我（待选择主体）","resource":"酒店","effect":"ask","conditions":[
    {"field":"check_in_after_time","operator":"gte","value":"15:00"},
    {"field":"travel_start_date","operator":"gte","value":"2026-10-10"},
    {"field":"budget_per_night","operator":"lte","value":400}]}]}
async def main():
    check_parsers()
    st,pl=await call("POST","/v1/setup",body={"password":"Temporal-Test-93!"});token=pl["token"]
    st,pl=await call("POST","/v1/principals",body={"principal_type":"person","display_name_zh":"本人"},token=token);pid=pl["id"]
    await call("POST","/v1/scenario-slices",body={"original_text":"订酒店","status":"analyzed","analysis":ANALYSIS,"updated_at":"2026-01-01T00:00:00Z"},token=token)
    st,pl=await call("GET","/v1/scenario-slices",token=token);sid=pl["items"][0]["id"]
    await call("POST","/v1/scenario-slices/confirm",body={"scenario_id":sid,"grantor_id":pid,"grantee_id":pid,"segmentation":{"mode":"global","dimensions":[],"global_preferences":[],"variants":[]}},token=token)
    st,pl=await call("POST",f"/v1/scenario-slices/{sid}/activate",body={},token=token)
    check("规则已启用", st==200, str(pl)[:60])
    st,s=await call("GET",f"/v1/scenario-slices/{sid}",token=token)
    a=s["analysis"]; g=a["generated"]; rid=g["resource_type_id"]; aid=g["action_ids"][0]
    # 补齐必填项，否则判定会在规则匹配之前被拦下
    req={}
    for item in a.get("required_inputs") or []:
        n=item["name"]
        req[n]={"destination_city":"北京","check_in_date":"2026-11-01","check_out_date":"2026-11-03",
                "guest_count":1,"room_count":1,"guest_name":"某人"}.get(n,"x")
    print("  必填项:", list(req))
    async def decide(extra):
        st,r=await call("POST","/v1/decisions/evaluate",body={"principal_id":pid,"action_id":aid,"resource_type_id":rid,"resource_id":"/x",
            "context":{"source_trust":"high",**req,**extra},"phase":"pre_planning"},token=token)
        return r
    base={"budget_per_night":300,"travel_start_date":"2026-11-01","check_in_after_time":"16:00"}
    def matched(r): return r.get("result_id")=="ask" and r.get("reason_key")!="decision.required_context_missing"
    def unmatched(r): return r.get("result_id")=="deny"
    r=await decide(base); check("全部满足 → 规则命中", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"check_in_after_time":"14:00"}); check("早于 15:00 → 不命中", unmatched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"check_in_after_time":"15:00"}); check("恰好 15:00 → 命中（含等号）", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"travel_start_date":"2026-10-01"}); check("日期早于阈值 → 不命中", unmatched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"travel_start_date":"2026-10-10"}); check("恰好阈值日期 → 命中", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"check_in_after_time":"下午4点"}); check("中文时间 → 命中", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"check_in_after_time":"不是时间"}); check("无法解析 → 不命中（保守）", unmatched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"budget_per_night":500}); check("超预算 → 不命中", unmatched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"travel_start_date":"2026-10-10T20:00:00"}); check("日期 vs 日期时间 → 命中", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"check_in_after_time":"15:30:00"}); check("带秒时间 → 命中", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"travel_start_date":"2026/10/11"}); check("斜杠日期 → 命中", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    r=await decide({**base,"travel_start_date":"2026年10月11日"}); check("中文日期 → 命中", matched(r), f"{r.get('result_id')}/{r.get('reason_key')}")
    p=sum(1 for ok,_ in RESULTS if ok); print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok,l in RESULTS:
        if not ok: print("  失败：",l)
asyncio.run(main()); shutil.rmtree(work,ignore_errors=True)
