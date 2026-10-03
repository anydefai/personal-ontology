"""场景分析结果的契约校验（对应 docs/09 与 schemas/scenario-analysis.schema.json）。

设计取向与既有容错一致：**违规不阻断分析**，只记入 `contract_notes` 供界面提示。
目的是让"模型输出是否仍合规"变成可观测的，而不是只能靠人工推演发现。

每条说明的 `code` 是稳定标识（供界面/i18n 映射），`field` 指向具体位置，`level` 为
"warn"（后端已容错，不阻断）或 "error"（需要人看一眼）。
"""
from __future__ import annotations

import re
from typing import Any

ROLES = {"required", "preference", "both"}
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def validate_analysis(analysis: Any) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []

    def note(code: str, field: str, level: str = "warn", **params: Any) -> None:
        """记录一条契约说明。**消息键就是 code**；文本放消息目录（中英双语），
        避免在此处留下只有中文的用户可见文案。读取时按显示语言替换 message。"""
        from . import messages
        notes.append({"code": code, "field": field, "level": level,
                      "message_key": code, "params": params,
                      "message": messages.msg_for(code, "zh", **params)})

    if not isinstance(analysis, dict):
        from . import messages as _messages
        return [{"code": "not_an_object", "field": "", "level": "error",
                 "message_key": "not_an_object", "params": {},
                 "message": _messages.msg_for("not_an_object", "zh")}]

    def dicts(key: str) -> list[dict[str, Any]]:
        value = analysis.get(key)
        return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []

    resource_types = dicts("resource_types")
    actions = dicts("actions")
    required = dicts("required_inputs")
    facts = dicts("facts")
    policies = dicts("policies")
    action_names = [str(a.get("name") or "") for a in actions]

    if not str(analysis.get("title") or "").strip():
        note("missing_title", "title")
    if not resource_types:
        note("no_resource_types", "resource_types", "error")
    if not actions:
        note("no_actions", "actions", "error")

    for index, policy in enumerate(policies, 1):
        where = f"policies[{index}]"
        declared = policy.get("actions")
        if not (isinstance(declared, list) and declared):
            note("policy_missing_actions", where)
        else:
            unknown = [str(a) for a in declared if str(a) not in action_names]
            if unknown:
                note("policy_unknown_action", where, actions="、".join(unknown))
        if str(policy.get("effect")) == "deny" and not (policy.get("conditions") or []) and len(policies) > 1:
            note("policy_unconditional_deny", where, "error")

    for group, items in (("required_inputs", required), ("facts", facts)):
        names = [str(x.get("name") or "") for x in items]
        for name in {n for n in names if n and names.count(n) > 1}:
            note("duplicate_field", f"{group}.{name}", "error")
        for item in items:
            name = str(item.get("name") or "")
            if not NAME_RE.fullmatch(name):
                note("field_bad_name", f"{group}.{name or '(空)'}", "error")
            role = item.get("role")
            if role is None:
                note("field_missing_role", f"{group}.{name}")
            elif str(role) not in ROLES:
                note("field_bad_role", f"{group}.{name}", "error", role=role)

    required_names = {str(x.get("name") or "") for x in required}
    fact_names = {str(x.get("name") or "") for x in facts}
    roles: dict[str, str] = {}
    for item in required + facts:
        if item.get("role"):
            roles.setdefault(str(item.get("name") or ""), str(item["role"]))
    for name, role in roles.items():
        if role == "both" and not (name in required_names and name in fact_names):
            note("both_not_in_both_lists", name)
        elif role == "required" and name in fact_names and name not in required_names:
            note("required_in_facts_only", name)
        elif role == "preference" and name in required_names and name not in fact_names:
            note("preference_in_required_only", name)
    return notes
