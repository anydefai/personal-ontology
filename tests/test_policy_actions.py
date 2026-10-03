"""策略按动作限定 + 拒绝无条件 deny 的自检。

    ~/personal-ontology/.venv/bin/python tests/test_policy_actions.py

来自三轮场景切片推演的发现：policies 原先没有 actions 字段，编译时把场景全部动作
塞给每条规则，于是"允许查看/编辑、禁止删除"被模型退化成一条无条件 deny，
而 deny 优先级最高 → 会否决该场景的全部动作。
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work=tempfile.mkdtemp(prefix="pol-"); os.environ["PERSONAL_ONTOLOGY_DATA"]=work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
# 复刻推演的发现：文件场景 4 个动作，策略想表达"允许查看/编辑、禁止删除"
ANALYSIS={"title":"处理文件","facts":[],"required_inputs":[],"questions":[],
 "scope":{"mode":"global"},
 "resource_types":[{"name":"文件"}],
 "actions":[{"name":"查看文件","risk":"low"},{"name":"编辑文件","risk":"medium"},
            {"name":"删除文件","risk":"high"},{"name":"列出目录文件","risk":"low"}],
 "policies":[
   {"subject":"我（待选择主体）","resource":"文件","effect":"allow","actions":["查看文件","编辑文件"],
    "conditions":[{"field":"directory_path","operator":"exists"}]},
   {"subject":"我（待选择主体）","resource":"文件","effect":"deny","actions":["删除文件"],
    "conditions":[{"field":"directory_path","operator":"exists"}]},
   {"subject":"我（待选择主体）","resource":"文件","effect":"deny","conditions":[]}]}   # ← 无条件拒绝，应被跳过并报出
async def main():
    st,pl=await call("POST","/v1/setup",body={"password":"Policy-Split-71!"}); token=pl["token"]
    st,pl=await call("POST","/v1/principals",body={"principal_type":"person","display_name_zh":"本人"},token=token); pid=pl["id"]
    await call("POST","/v1/scenario-slices",body={"original_text":"处理文件","status":"analyzed","analysis":ANALYSIS,"updated_at":"2026-01-01T00:00:00Z"},token=token)
    st,pl=await call("GET","/v1/scenario-slices",token=token); sid=pl["items"][0]["id"]
    st,pl=await call("POST","/v1/scenario-slices/confirm",body={"scenario_id":sid,"grantor_id":pid,"grantee_id":pid,
        "segmentation":{"mode":"global","dimensions":[],"global_preferences":[],"variants":[]}},token=token)
    check("确认成功", st==200, f"HTTP {st}")
    notes=pl.get("compile_report") or []
    print("  编译说明:", json.dumps(notes, ensure_ascii=False)[:220])
    check("无条件拒绝被跳过并报出", any("无条件的拒绝" in str(n.get("reason")) for n in notes), str(notes)[:120])
    st,pl=await call("GET","/v1/scenario-slices/"+sid+"/policies",token=token)
    rules=pl.get("rules") or []
    check("生成 2 条规则（第 3 条被跳过）", len(rules)==2, f"实际 {len(rules)}")
    by_effect={r["effect"]: r for r in rules}
    check("有 allow 与 deny 各一条", set(by_effect)=={"allow","deny"}, str(list(by_effect)))
    # 动作必须不同——这是本次修复的核心
    allow_actions=set(by_effect.get("allow",{}).get("actions") or [])
    deny_actions=set(by_effect.get("deny",{}).get("actions") or [])
    print("  allow 动作:", sorted(allow_actions))
    print("  deny  动作:", sorted(deny_actions))
    check("allow 只覆盖查看/编辑", allow_actions=={"scene_"+sid.removeprefix("scene_")+"_action_1","scene_"+sid.removeprefix("scene_")+"_action_2"}, str(sorted(allow_actions)))
    check("deny 只覆盖删除", len(deny_actions)==1, str(sorted(deny_actions)))
    check("两者动作不重叠", not (allow_actions & deny_actions), str(sorted(allow_actions & deny_actions)))
    p=sum(1 for ok,_ in RESULTS if ok); print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok,l in RESULTS:
        if not ok: print("  失败：",l)
asyncio.run(main()); shutil.rmtree(work,ignore_errors=True)
