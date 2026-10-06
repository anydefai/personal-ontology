"""② 规则层验收：启用 → 生成授权规则 → 停用 → 规则失效。

    ~/personal-ontology/.venv/bin/python tests/test_rule_layer.py

这条链路把"专业切片对外可用"写成一条真实的授权规则（与生活侧同一张 authorizations 表），
而不是一句提示。边界（金额/用途/不转售）仍由第一层 /authorize 逐次校验。
"""
import asyncio, json, os, pathlib, shutil, sys, tempfile
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS

async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "RuleLayer-94!"})
    assert "token" in pl, f"setup 失败 {st} {pl}"
    token = pl["token"]

    st, d = await call("GET", "/v1/resource-types", token=token)
    items = (d.get("items") if isinstance(d, dict) else d) or []
    check("内置里有「专业判断调用」资源类型（播种 ✓ 不走运行时校验）",
          any(x.get("id") == "skill" for x in items), str([x.get("id") for x in items]))
    st, d = await call("GET", "/v1/actions", token=token)
    items = (d.get("items") if isinstance(d, dict) else d) or []
    check("内置里有「调用专业判断」动作", any(x.get("id") == "skill.call" for x in items),
          str([x.get("id") for x in items]))

    st, g = await call("POST", "/v1/principals", body={"display_name_zh": "本人", "principal_type": "person"}, token=token)
    st, e = await call("POST", "/v1/principals", body={"display_name_zh": "法智AI", "principal_type": "person"}, token=token)
    check("主体只接受 principal_type=person（探明后固化）", bool(g.get("id")) and bool(e.get("id")), f"{st}")

    await call("POST", "/v1/scenario-slices", body={"id": "s.rule", "original_text": "规则层测试",
        "status": "analyzed", "scenario_definition_id": "test.scenario",
        "scenario_profile": {"kind": "professional"}, "analysis": {"title": "规则层测试"},
        "updated_at": "2026-10-06T00:00:00"}, token=token)

    st, delivery = await call("PATCH", "/v1/scenario-slices/s.rule",
                              body={"boundaries": {"max_amount": 1000000000,
                                                   "allowed_scenarios": ["并购尽调", "投资决策"],
                                                   "confidentiality": "调用方不得转售结论"}}, token=token)
    st, r = await call("POST", "/v1/scenario-slices/s.rule/enable",
                       body={"grantor_id": g["id"], "grantee_id": e["id"]}, token=token)
    check("启用成功并生成授权规则", st == 200 and r.get("authorization_id"),
          f"HTTP {st} {json.dumps(r, ensure_ascii=False)[:200]}")
    check("规则挂在 seed 的 skill 资源类型上", r.get("resource_type_id") == "skill" and r.get("action_id") == "skill.call",
          str(r.get("resource_type_id")))

    st, d = await call("GET", "/v1/authorizations", token=token)
    rules = (d.get("items") if isinstance(d, dict) else d) or []
    check("授权表里有 1 条规则（与生活侧同一张表）", len(rules) == 1, str(len(rules)))
    a = rules[0] if rules else {}
    check("source = skill-slice:<切片id>（与生活侧 scenario-slice:<id> 对称）",
          a.get("source") == "skill-slice:s.rule", str(a.get("source")))
    check("授权方=本人 被授权方=法智AI", a.get("grantor_id") == g["id"] and a.get("grantee_id") == e["id"], "ok")
    check("effect=allow · policy_status=active · 未撤回",
          a.get("effect") == "allow" and a.get("policy_status") == "active" and a.get("revoked") is False,
          str((a.get("effect"), a.get("policy_status"), a.get("revoked"))))
    st, s_after = await call("GET", "/v1/scenario-slices/s.rule", token=token)
    check("启用不会动切片的边界（金额/用途/不转售仍由第一层逐次校验）",
          (s_after.get("boundaries") or {}) == (delivery.get("boundaries") or {}),
          f"{s_after.get('boundaries')}")
    st, s2 = await call("GET", "/v1/scenario-slices/s.rule", token=token)
    check("切片状态 → confirmed（出现在场景实例）", s2.get("status") == "confirmed", str(s2.get("status")))

    st, r2 = await call("POST", "/v1/scenario-slices/s.rule/disable", token=token)
    check("停用成功", st == 200, str(st))
    st, d = await call("GET", "/v1/authorizations", token=token)
    rules = (d.get("items") if isinstance(d, dict) else d) or []
    check("停用后规则被撤回（revoked/suspended）",
          bool(rules) and rules[0].get("revoked") is True and rules[0].get("policy_status") == "suspended",
          str(rules[0].get("revoked") if rules else None))
    st, s3 = await call("GET", "/v1/scenario-slices/s.rule", token=token)
    check("停用后切片退回草稿", s3.get("status") == "analyzed", str(s3.get("status")))

    st, r3 = await call("POST", "/v1/scenario-slices/s.rule/enable", body={"grantor_id": "nobody"}, token=token)
    check("主体不存在 → 422（不伪造授权）", st == 422, str(st))
    st, r4 = await call("POST", "/v1/scenario-slices/s.rule/enable",
                        body={"grantor_id": g["id"], "grantee_id": "nobody"}, token=token)
    check("被授权方不存在 → 422", st == 422, str(st))

asyncio.run(main())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
