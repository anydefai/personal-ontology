"""判定包分层 / 交付身份信息 / 反馈闭环验收（①②③④）。

    ~/personal-ontology/.venv/bin/python tests/test_package_and_feedback.py
"""
import pathlib
import asyncio, json, os, sys, tempfile, shutil
work = tempfile.mkdtemp(); os.environ["PERSONAL_ONTOLOGY_DATA"] = work
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from test_api_auth import call, check, RESULTS
from backend.skill_backtest import confidence_from_feedback
from backend.skill_framework import TIERS, apply_tier, content_fingerprint

# ① 分层口径
check("四个分层齐备", set(TIERS) == {"basic", "standard", "professional", "audit"}, str(sorted(TIERS)))
pkg = {"decision": "估值偏高", "severity": "高", "evidence": [{"f": 1}], "reasoning_path": [{"step": 1}],
       "confidence": 0.78, "confidence_status": "backtested", "professional_insight": "洞察",
       "owner_credentials": "执业15年", "audit_id": "AUDIT-1", "valid_until": "T", "content_fingerprint": "abc"}
check("基础层只给结论", sorted(apply_tier(dict(pkg), "basic")) == ["decision", "severity", "tier"], str(sorted(apply_tier(dict(pkg), "basic"))))
check("标准层加证据", "evidence" in apply_tier(dict(pkg), "standard") and "reasoning_path" not in apply_tier(dict(pkg), "standard"))
check("专业层加推理路径", "reasoning_path" in apply_tier(dict(pkg), "professional") and "audit_id" not in apply_tier(dict(pkg), "professional"))
aud = apply_tier(dict(pkg), "audit")
check("审计层给完整包", all(k in aud for k in ("reasoning_path", "professional_insight", "owner_credentials", "audit_id", "valid_until", "content_fingerprint")), str(sorted(aud)))
check("未知分层按最低层给（宁少给不多给）", apply_tier(dict(pkg), "乱写")["tier"] == "basic")
check("指纹可复现", content_fingerprint(dict(pkg)) == content_fingerprint(dict(pkg)))

# ④ 反馈阶梯
check("9 次反馈 → 仍未验证", confidence_from_feedback(9, 8)["confidence_status"] == "unverified")
check("10 次反馈 → 初步", confidence_from_feedback(10, 8)["confidence_status"] == "preliminary")
check("100 次反馈 → 稳定", confidence_from_feedback(100, 78)["confidence_status"] == "stable")

# ②③④ 经接口
async def api_part():
    st, pl = await call("POST", "/v1/setup", body={"password": "Pkg-94-ok!"})
    assert "token" in pl, f"setup 失败：HTTP {st} {json.dumps(pl, ensure_ascii=False)[:200]}"
    token = pl["token"]
    # 测试自建场景（不依赖内置种子：内置场景已按用户要求删除）
    for _sid, _zh in (("test.scenario", "测试场景"), ("test.scenario2", "测试场景二")):
        await call("POST", "/v1/scenario-definitions", body={
            "id": _sid, "display_name_zh": _zh, "display_name_en": _zh,
            "domain_pack_ids": ["legal.cn"], "version": "1.0.0",
            "lifecycle_state": "active", "is_builtin": False}, token=token)
    import json as _j
    fw = {"framework_version": "T-V1", "thresholds": {"base": 1.0, "adjustments": []},
          "signals": [{"name": "偏高", "when": {"市盈率": {"op": "gt", "value": 39}}}],
          "combination_rules": [{"all_of": ["偏高"], "conclusion": "估值偏高", "severity": "高"}]}
    await call("PATCH", "/v1/scenario-definitions/test.scenario",
               body={"framework": fw, "insight": "普通判断只看市盈率，本判断还看周期与监管。",
                     "owner_credentials": "执业15年，主导过80+并购案", "valid_days": 2}, token=token)
    DATA = {"data": {"市盈率": 45}, "tier": "audit"}
    st, full = await call("POST", "/v1/scenario-definitions/test.scenario/evaluate", body=DATA, token=token)
    check("审计层交付成功", st == 200 and full.get("tier") == "audit", f"HTTP {st}")
    check("含专业洞察与资历", full.get("professional_insight", "").startswith("普通判断") and "执业" in full.get("owner_credentials", ""), str(full.get("professional_insight"))[:40])
    check("含审计号与有效期", str(full.get("audit_id", "")).startswith("AUDIT-") and full.get("valid_until"), f"{full.get('audit_id')} / {full.get('valid_until')}")
    check("含内容指纹且不算签名", full.get("content_fingerprint") and full.get("signature_status") == "not_implemented", str(full.get("signature_status")))
    st, basic = await call("POST", "/v1/scenario-definitions/test.scenario/evaluate",
                           body={"data": {"市盈率": 45}, "tier": "basic"}, token=token)
    check("基础层只回结论与严重度", st == 200 and "evidence" not in basic and "professional_insight" not in basic, str(sorted(basic)))
    st, r = await call("POST", "/v1/scenario-definitions/test.scenario/evaluate",
                       body={"data": {"市盈率": 45}, "tier": "乱写"}, token=token)
    check("非法分层 → 422", st == 422, f"HTTP {st}")
    st, r = await call("POST", "/v1/scenario-definitions/test.scenario/feedback", body={"verdict": "乱写"}, token=token)
    check("非法反馈 → 422", st == 422, f"HTTP {st}")
    for i in range(9):
        st, r = await call("POST", "/v1/scenario-definitions/test.scenario/feedback", body={"verdict": "accurate"}, token=token)
    check("9 次反馈 → 仍未验证", r.get("confidence_status") == "unverified", str(r))
    st, r = await call("POST", "/v1/scenario-definitions/test.scenario/feedback", body={"verdict": "inaccurate"}, token=token)
    check("第 10 次反馈 → 初步置信度", r.get("confidence_status") == "preliminary" and r.get("feedback_total") == 10, str(r))
    st, one = await call("GET", "/v1/scenario-definitions/test.scenario", token=token)
    check("置信度已写回定义（9/10 一致 = 0.9）",
          abs(float(one.get("confidence") or 0) - 0.9) < 1e-9 and one.get("confidence_status") == "preliminary",
          f"{one.get('confidence')}/{one.get('confidence_status')}")
    check("依据写明反馈量与一致率", "10" in (one.get("confidence_basis") or "") and "90" in (one.get("confidence_basis") or ""), str(one.get("confidence_basis"))[:80])

asyncio.run(api_part())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
shutil.rmtree(work, ignore_errors=True)
sys.exit(0 if p == len(RESULTS) else 1)
