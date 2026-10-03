"""后端消息目录（中/英双语）—— 见 docs/00-first-principle-bilingual.md。

语言由中间件从 `X-Display-Language` 写入 contextvars，因此 `msg(key)` 不需要
在每个端点签名里加 request 参数。

新增消息一律：先在 MESSAGES 里加键（zh + en 都要有），再在代码里用 msg("键")。
缺英文时回落中文并在测试里被发现（tests/test_bilingual_coverage.py 统计缺口）。
"""
from __future__ import annotations

import contextvars
from typing import Any

_LANGUAGE: contextvars.ContextVar[str] = contextvars.ContextVar("display_language", default="zh")


def set_language(language: str | None) -> None:
    _LANGUAGE.set("en" if str(language or "").lower().startswith("en") else "zh")


def current_language() -> str:
    return _LANGUAGE.get()


MESSAGES: dict[str, dict[str, str]] = {
    # 登录与账户
    "login_password_required": {"zh": "请输入登录密码。", "en": "Enter the login password."},
    "current_password_required": {"zh": "请输入当前密码。", "en": "Enter the current password."},
    "too_many_attempts": {"zh": "尝试过于频繁，请 {seconds} 秒后再试。",
                          "en": "Too many attempts. Try again in {seconds} seconds."},
    # 场景偏好与分组校验
    "pref_scope_invalid": {"zh": "场景偏好范围设置无效。", "en": "Invalid scenario preference scope."},
    "pref_list_invalid": {"zh": "场景偏好列表格式无效。", "en": "Invalid scenario preference list format."},
    "pref_item_incomplete": {"zh": "每条偏好都需要固定字段名、显示名称和值。",
                             "en": "Each preference needs a fixed field name, a display name and a value."},
    "pref_operator_invalid": {
        "zh": "场景偏好的比较方式无效（字段 {field}，比较方式 {operator!r}）：只支持 equals / lte / gte / exists。",
        "en": "Invalid comparison for scenario preference (field {field}, operator {operator!r}): only equals / lte / gte / exists are supported."},
    "seg_needs_dimension": {"zh": "按维度区分时，至少需要一个维度和一个场景分组。",
                            "en": "Segmented mode needs at least one dimension and one scenario variant."},
    "dimension_needs_field": {"zh": "区分维度必须有字段名和显示名称。",
                              "en": "A distinguishing dimension needs a field name and a display name."},
    "dimension_duplicate": {"zh": "区分维度不能重复。", "en": "Distinguishing dimensions must be unique."},
    "variant_needs_values": {"zh": "每个场景分组都要填写维度取值。",
                             "en": "Every scenario variant must fill in its dimension values."},
    "variant_needs_all_values": {"zh": "每个场景分组都必须填写全部区分维度的值。",
                                 "en": "Every scenario variant must fill in all distinguishing dimension values."},
    "ontology_read_failed": {"zh": "读取现有本体数据失败：{exc}", "en": "Failed to read existing ontology data: {error}"},
    "container_create_failed": {"zh": "创建容器失败：{exc}", "en": "Failed to create the container: {error}"},
    "container_read_failed": {"zh": "容器无法读取：{exc}", "en": "The container cannot be read: {error}"},
    "password_unchanged": {"zh": "新密码与当前密码相同。", "en": "The new password is the same as the current one."},
    "password_change_failed": {"zh": "修改密码失败：{exc}", "en": "Failed to change the password: {error}"},
    "scopes_invalid": {"zh": "授权范围无效。", "en": "Invalid authorization scope."},
    "client_not_listed": {"zh": "该程序不在清单中。", "en": "That program is not in the list."},
    "language_invalid": {"zh": "语言只能是 zh、en 或 auto。", "en": "Language must be zh, en or auto."},
    "minutes_range": {"zh": "请提供 0–1440 之间的分钟数。", "en": "Provide a number of minutes between 0 and 1440."},
    "scene_text_required": {"zh": "请填写场景描述，最多 10000 个字符。", "en": "Enter a scenario description, up to 10000 characters."},
    "scene_id_invalid": {"zh": "场景草稿 ID 格式不正确。", "en": "Invalid scenario draft id."},
    "scene_missing": {"zh": "场景草稿不存在。", "en": "Scenario draft not found."},
    "answers_invalid": {"zh": "补充回答格式不正确。", "en": "Invalid follow-up answer format."},
    "answer_too_long": {"zh": "每条补充信息最多 2000 个字符。", "en": "Each follow-up answer may be at most 2000 characters."},
    "scene_exists": {"zh": "场景草稿已存在，请刷新后重试。", "en": "The scenario draft already exists; refresh and try again."},
    "scene_not_analyzed": {"zh": "找不到已分析的场景草稿。", "en": "No analysed scenario draft found."},
    "scene_title_too_long": {"zh": "请填写不超过 160 个字符的场景名称。", "en": "Enter a scenario name of at most 160 characters."},
    "scene_needs_resources": {"zh": "模型尚未识别出资源类型和动作，请补充描述后重新分析。", "en": "The model has not identified resource types and actions yet; add to the description and re-analyze."},
    "principal_invalid": {"zh": "请选择有效的授权主体。", "en": "Choose a valid authorization principal."},
    "confirm_before_compile": {"zh": "请先确认并保存该场景，再生成授权规则。", "en": "Confirm and save the scenario before generating authorization rules."},
    "scene_no_resources_actions": {"zh": "该场景还没有可用的资源类型或动作，请重新分析后再试。", "en": "This scenario has no usable resource types or actions; re-analyze and try again."},
    "no_policy_drafts": {"zh": "该场景没有可用于生成规则的策略草稿。", "en": "This scenario has no policy drafts to generate rules from."},
    "rule_grantee_required": {"zh": "请选择这条规则适用的主体。", "en": "Choose the principal this rule applies to."},
    "grantor_missing": {"zh": "所选主体不存在。", "en": "The selected principal does not exist."},
    "grantee_missing": {"zh": "所选被授权主体不存在。", "en": "The selected authorized principal does not exist."},
    "no_rules_to_create": {"zh": "该场景没有可生成的规则草稿。", "en": "This scenario has no rule drafts to create."},
    "instance_missing": {"zh": "场景实例不存在。", "en": "Scenario instance not found."},
    "scope_invalid": {"zh": "场景范围设置无效。", "en": "Invalid scenario scope."},
    "required_defs_invalid": {"zh": "必填信息定义格式无效。", "en": "Invalid required-field definition format."},
    "required_item_invalid": {"zh": "每个必填信息都需要有效字段名和用户可读名称。", "en": "Each required field needs a valid field name and a human-readable label."},
    "required_type_invalid": {"zh": "必填信息类型仅支持文本、数字、是/否和日期。", "en": "Required fields support only text, number, boolean and date."},
    "required_field_duplicate": {"zh": "必填信息字段名不能重复。", "en": "Required field names must be unique."},
    "instance_missing_or_unconfirmed": {"zh": "场景实例不存在或尚未确认。", "en": "Scenario instance not found or not confirmed yet."},
    "feedback_type_invalid": {"zh": "反馈类型必须是本次执行输入或长期实例偏好。", "en": "Feedback type must be a run input or a standing instance preference."},
    "feedback_item_invalid": {"zh": "请提供有效字段名、显示名称和文本/数字/是非值。", "en": "Provide a valid field name, label and text/number/boolean value."},
    "feedback_item_too_long": {"zh": "单项输入不能超过 2000 个字符。", "en": "A single input may be at most 2000 characters."},
    "preference_needs_confirmation": {"zh": "长期偏好只能在用户明确确认后写入，并需记录用户的确认原话。", "en": "A standing preference can only be written after the user explicitly confirms it, and the user's own words must be recorded."},
    "constraint_operator_invalid": {"zh": "约束操作符或对应值无效。", "en": "Invalid constraint operator or value."},
    "preference_variant_required": {"zh": "长期偏好更新需要指定匹配的场景分组。", "en": "A standing-preference update must name the matching scenario variant."},
    "preference_scope_mismatch": {"zh": "全局实例的长期偏好需按全局范围记录。", "en": "Standing preferences of a global instance must be recorded with global scope."},
    "confirm_before_manage_rules": {"zh": "请先确认并保存该场景，再管理它的授权规则。", "en": "Confirm and save the scenario before managing its authorization rules."},
    "scene_has_no_rules": {"zh": "该场景还没有生成授权规则。", "en": "This scenario has not generated any authorization rules yet."},
    "authorization_ids_array": {"zh": "authorization_ids 需要是数组。", "en": "authorization_ids must be an array."},
    "instance_not_confirmed": {"zh": "请先在场景切片中确认并保存该场景实例。", "en": "Confirm and save the scenario instance under scenario slices first."},
    "preview_input_invalid": {"zh": "预演输入格式无效。", "en": "Invalid rehearsal input format."},
    "preview_too_many": {"zh": "单次预演最多提供 100 项输入。", "en": "A rehearsal accepts at most 100 inputs."},
    "preview_value_invalid": {"zh": "预演值只能是文本、数字或是/否。", "en": "Rehearsal values may only be text, number or boolean."},
    "preview_item_too_long": {"zh": "单项预演输入不能超过 2000 个字符。", "en": "A single rehearsal input may be at most 2000 characters."},
    "backend_restarted": {"zh": "治理后端已重启。", "en": "The governance backend has restarted."},
    "segmented_enable_unsupported": {"zh": "分组场景的条件无法按分组表达，暂不支持启用；请先在场景实例中改为“所有情况共用一套偏好”。", "en": "Conditions of a segmented scenario cannot be expressed per variant, so enabling is not supported yet; first switch the scenario instance to share one set of preferences across all cases."},
    "rules_not_in_scene": {"zh": "这些规则不属于该场景：{names}", "en": "These rules do not belong to this scenario: {names}"},
    "rule_toggle_via_instance": {"zh": "授权规则的启用状态请在场景实例页用“启用/暂停规则”修改，以便先校验条件并写入审计。", "en": "Change whether an authorization rule is enabled on the scenario instance page, using enable/pause rules, so conditions are validated and an audit record is written first."},
    "backend_restarted_ok": {"zh": "治理后端已重启。", "en": "The governance backend has restarted."},
    "backend_restart_unhealthy": {"zh": "重启命令已发出，但后端在 20 秒内没有通过健康检查。请查看启动日志。", "en": "The restart command was sent, but the backend did not pass its health check within 20 seconds. Check the startup log."},
    "missing_title": {"zh": "缺少场景标题。", "en": "The scenario has no title."},
    "no_resource_types": {"zh": "没有资源类型，场景无法落地。", "en": "There are no resource types, so the scenario cannot be materialised."},
    "no_actions": {"zh": "没有动作，无法生成授权规则。", "en": "There are no actions, so no authorization rules can be generated."},
    "policy_missing_actions": {"zh": "策略未声明适用动作，已回退到该场景全部动作；不同动作立场不同时应拆成多条策略。", "en": "A policy did not declare its actions, so it falls back to all of the scenario's actions; split it into several policies when different actions have different stances."},
    "policy_unknown_action": {"zh": "策略声明的动作不在本场景动作里：{actions}。", "en": "A policy declares actions that are not in this scenario: {actions}."},
    "policy_unconditional_deny": {"zh": "无条件的拒绝会否决该场景的全部动作，已被跳过。", "en": "An unconditional denial would veto every action of the scenario, so it was skipped."},
    "duplicate_field": {"zh": "同一清单里出现重复字段名。", "en": "The same field name appears more than once in one list."},
    "field_bad_name": {"zh": "字段名必须是英文键（字母、数字、下划线），否则规则无法引用。", "en": "A field name must be an English key (letters, digits, underscore) or rules cannot reference it."},
    "field_missing_role": {"zh": "字段未给出分档，已补默认档位。", "en": "The field had no tier, so a default tier was filled in."},
    "field_bad_role": {"zh": "分档 {role} 无效，只支持 required/preference/both。", "en": "Invalid tier {role}; only required/preference/both are supported."},
    "both_not_in_both_lists": {"zh": "标为「两者兼有」，却只出现在两个清单中的一个。", "en": "Marked as both, yet it appears in only one of the two lists."},
    "required_in_facts_only": {"zh": "标为「每次必填」，却只出现在偏好清单。", "en": "Marked as required per run, yet it appears only in the preference list."},
    "preference_in_required_only": {"zh": "标为「每次必填」的反面：标为「长期偏好」，却只出现在必填清单。", "en": "Marked as a standing preference, yet it appears only in the required list."},
    "not_an_object": {"zh": "分析结果不是对象。", "en": "The analysis result is not an object."},
}


def msg_for(key: str, language: str | None, **kwargs: Any) -> str:
    """按**显式**语言取消息（异常处理器用；不依赖 contextvars）。"""
    entry = MESSAGES.get(key)
    if not entry: return key
    text = entry.get("en" if str(language or "").lower().startswith("en") else "zh") or entry.get("zh") or key
    try:
        return text.format(**kwargs) if kwargs else text
    except (KeyError, IndexError):
        return text


def msg(key: str, **kwargs: Any) -> str:
    """按当前请求语言取消息；缺英文时回落中文（缺口由覆盖率测试统计）。"""
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(current_language()) or entry.get("zh") or key
    try:
        return text.format(**kwargs) if kwargs else text
    except (KeyError, IndexError):
        return text


def detail(key: str, **kwargs: Any) -> dict[str, Any]:
    """把消息键交给异常处理器解析（而不是在此处解析语言）。

    业务代码里拿不到可靠的请求上下文（中间件与依赖的 contextvars 都传不到端点），
    而**异常处理器**能拿到 request，因此在那一层解析语言。
    """
    return {"message_key": key, "kwargs": kwargs}
