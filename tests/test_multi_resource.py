"""多资源类型场景自检（推演发现的第四个缺口）。

    ~/personal-ontology/.venv/bin/python tests/test_multi_resource.py

此前 confirm_scene 只处理 types[0]，场景提出的其余资源类型被静默丢弃
（推演中"文件"场景的"目录"就这样消失了）；且所有规则都挂在第一个资源类型上。
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work=tempfile.mkdtemp(prefix="multi-"); os.environ["PERSONAL_ONTOLOGY_DATA"]=work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
ANALYSIS={"title":"处理文件","facts":[],"required_inputs":[],"questions":[],"scope":{"mode":"global"},
 "resource_types":[{"name":"文件"},{"name":"目录"}],
 "actions":[{"name":"查看文件","risk":"low"},{"name":"删除文件","risk":"high"},{"name":"列出目录文件","risk":"low"}],
 "policies":[
   {"subject":"我（待选择主体）","resource":"文件","effect":"allow","actions":["查看文件"],"conditions":[{"field":"p","operator":"exists"}]},
   {"subject":"我（待选择主体）","resource":"文件","effect":"deny","actions":["删除文件"],"conditions":[{"field":"p","operator":"exists"}]},
   {"subject":"我（待选择主体）","resource":"目录","effect":"allow","actions":["列出目录文件"],"conditions":[{"field":"p","operator":"exists"}]}]}
async def main():
    st,pl=await call("POST","/v1/setup",body={"password":"Multi-Res-83!"}); token=pl["token"]
    st,pl=await call("POST","/v1/principals",body={"principal_type":"person","display_name_zh":"本人"},token=token); pid=pl["id"]
    await call("POST","/v1/scenario-slices",body={"original_text":"处理文件","status":"analyzed","analysis":ANALYSIS,"updated_at":"2026-01-01T00:00:00Z"},token=token)
    st,pl=await call("GET","/v1/scenario-slices",token=token); sid=pl["items"][0]["id"]
    st,pl=await call("POST","/v1/scenario-slices/confirm",body={"scenario_id":sid,"grantor_id":pid,"grantee_id":pid,
        "segmentation":{"mode":"global","dimensions":[],"global_preferences":[],"variants":[]}},token=token)
    check("确认成功", st==200, f"HTTP {st} {str(pl)[:150]}")
    st,rts=await call("GET","/v1/resource-types",token=token)
    names=sorted(r.get("display_name_zh") for r in rts["items"])
    check("两个资源类型都已落地（目录不再丢失）", "文件" in names and "目录" in names, str(names))
    st,pl=await call("GET",f"/v1/scenario-slices/{sid}",token=token)
    gen=(pl.get("analysis") or {}).get("generated") or {}
    check("generated 记录了两个资源类型 ID", len(gen.get("resource_type_ids") or [])==2, str(gen.get("resource_type_ids")))
    st,rules=await call("GET",f"/v1/scenario-slices/{sid}/policies",token=token)
    by_action={}
    for r in rules.get("rules") or []:
        by_action[tuple(r.get("actions") or [])]=r.get("resource_type_id")
    check("生成 3 条规则", len(by_action)==3, str(len(by_action)))
    ids=gen.get("resource_type_ids") or []
    check("「文件」上的规则挂在文件资源类型", ids and by_action.get(tuple([gen["action_ids"][0]]))==ids[0], str(by_action))
    check("「目录」上的规则挂在目录资源类型", len(ids)==2 and by_action.get(tuple([gen["action_ids"][2]]))==ids[1], str(by_action))
    p=sum(1 for ok,_ in RESULTS if ok); print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
    for ok,l in RESULTS:
        if not ok: print("  失败：",l)
asyncio.run(main()); shutil.rmtree(work,ignore_errors=True)
