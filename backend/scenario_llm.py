"""OpenAI-compatible, opt-in provider for natural-language scenario analysis."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from .config import display_language
from .field_names import default_label, normalize_analysis
from .model_service import ModelServiceError, _read as read_model_service, endpoint as model_endpoint


class ScenarioProviderError(RuntimeError):
    pass


def generic_title(user_text: str, result: dict[str, Any]) -> str:
    """Replace a one-off request title with a reusable task name when needed."""
    title = str(result.get("title", "")).strip()[:80]
    facts = result.get("facts", []) if isinstance(result.get("facts"), list) else []
    specific_values = [str(x.get("value", "")).strip() for x in facts if isinstance(x, dict) and x.get("value") not in (None, "")]
    transient = re.search(r"今晚|今夜|今天|明天|后天|昨日|今晚|本周|下周|下个月|\d{1,2}月\d{1,2}[日号]?|\d{4}[-年]\d{1,2}", title)
    embeds_fact = any(len(value) >= 2 and value in title and value not in {str(x.get("name", "")) for x in (result.get("resource_types") or []) if isinstance(x, dict)} for value in specific_values)
    directional_detail = re.search(r"(?:前往|去|到).{1,12}(?:的|之).{1,8}(?:机票|酒店|火车票|房间)", title)
    if title and not transient and not embeds_fact and not directional_detail:
        return title

    text = user_text
    object_name = ""
    for pattern, canonical in ((r"机票|飞机票", "机票"), (r"酒店|宾馆|旅馆", "酒店"), (r"火车票|车票", "火车票"), (r"租车", "租车"), (r"餐厅|饭店", "餐厅")):
        if re.search(pattern, text):
            object_name = canonical
            break
    if not object_name:
        resources = result.get("resource_types", [])
        if isinstance(resources, list) and resources and isinstance(resources[0], dict):
            object_name = str(resources[0].get("name", "")).strip()
    actions = result.get("actions", [])
    action_text = " ".join(str(x.get("name", "")) for x in actions if isinstance(x, dict))
    combined = text + " " + action_text
    verb = next((v for v, pattern in (("预订", r"预订|预定|订购"), ("购买", r"购买|买"), ("查询", r"查询|搜索|查找")) if re.search(pattern, combined)), "处理")
    if object_name:
        return f"{verb}{object_name}"[:40]
    return (title or "通用场景")[:40]


def _hotel_fallback(text: str, result: dict[str, Any], previous: dict[str, Any] | None = None,
                    language: str | None = None) -> dict[str, Any]:
    """Recover explicit hotel-booking details when a provider returns empty arrays."""
    if not any(word in text for word in ("酒店", "旅馆", "宾馆")):
        return result
    facts = result.setdefault("facts", [])
    attributes = result.get("resource_types") or []
    actions = result.get("actions") or []
    policies = result.get("policies") or []
    questions = result.setdefault("questions", [])
    known = {str(item.get("name", "")) for item in facts if isinstance(item, dict)}

    def add_fact(name: str, label: str, value: Any, kind: str = "string") -> None:
        if name not in known:
            # 空标签交给字段命名契约按当前展示语言填充（中文/英文同名键对应同一字段）
            facts.append({"name": name, "label": label or default_label(name, language or display_language()), "value": value, "type": kind, "source": "user"})
            known.add(name)

    city = re.search(r"(?:去|到|前往|目的地(?:是|为)?)[\s：:]*([\u4e00-\u9fff]{2,8})(?:市|地区)?", text)
    if city and city.group(1) not in {"酒店", "预定", "预订", "入住", "需要", "要求"}:
        add_fact("destination_city", "", city.group(1) + ("市" if "天津" in city.group(1) or len(city.group(1)) > 2 else ""))
    district = re.search(r"([\u4e00-\u9fff]{2,8}区)", text)
    if district:
        add_fact("district", "", district.group(1))
    price = re.search(r"(?:价格|房价|预算)?\s*(?:在|为|是|约)?\s*[¥￥]?\s*(\d+(?:\.\d+)?)\s*(?:元)?\s*(?:-|－|—|~|～|到|至)\s*[¥￥]?\s*(\d+(?:\.\d+)?)\s*(?:元)?", text)
    if price:
        add_fact("price_min", "", float(price.group(1)) if "." in price.group(1) else int(price.group(1)), "number")
        add_fact("price_max", "", float(price.group(2)) if "." in price.group(2) else int(price.group(2)), "number")
    elif re.search(r"不超过\s*[¥￥]?\s*\d+", text):
        amount = re.search(r"不超过\s*[¥￥]?\s*(\d+)", text)
        add_fact("price_max", "", int(amount.group(1)), "number")
    if any(term in text for term in ("不吸烟", "无烟", "禁烟")):
        add_fact("smoking_policy", "吸烟要求", "不吸烟楼层 / 禁烟房")
    if any(term in text for term in ("安静", "不要吵", "不吵")):
        add_fact("noise_level", "环境要求", "安静")
    if "停车" in text:
        add_fact("parking", "停车场", "需要停车场" if any(term in text for term in ("要有", "需要", "有停车")) else "关注是否有停车场")
    days = re.search(r"入住\s*(\d+)\s*(天|晚)", text)
    if days:
        add_fact("stay_duration", "入住时长", int(days.group(1)), "number")
        add_fact("stay_unit", "时长单位", days.group(2))

    if not attributes:
        result["resource_types"] = [{"name": "酒店", "description": "酒店及其房型、位置、设施和入住条件", "attributes": ["目标城市", "区域", "房价", "吸烟政策", "噪音环境", "停车场", "入住时长"]}]
    if not actions:
        result["actions"] = [{"name": "搜索并比较酒店", "description": "按城市、区域、价格与住宿偏好查找和比较酒店", "risk": "low"}, {"name": "预定酒店", "description": "按用户确认的酒店与入住条件提交预订", "risk": "high"}]
    if not policies:
        conditions = []
        for fact in facts:
            if not isinstance(fact, dict) or fact.get("source") == "suggestion":
                continue
            name, value = fact.get("name"), fact.get("value")
            if name in {"price_max", "price_min"}:
                conditions.append({"field": "price", "operator": "lte" if name == "price_max" else "gte", "value": value, "label": "价格上限" if name == "price_max" else "价格下限"})
            elif name and not (name in {"destination_city", "district", "area"} and not any(term in text for term in ("不同城市", "按城市", "每个城市", "各城市", "不同地区", "按地区"))):
                conditions.append({"field": name, "operator": "equals", "value": value, "label": fact.get("label", name)})
        result["policies"] = [{"subject": "我（待选择主体）", "resource": "酒店", "actions": [x["name"] for x in result["actions"]], "effect": "ask", "conditions": conditions, "policy_status": "draft"}]
    # Suggestions are a single review round. Re-analysis should incorporate
    # the user's answers, not manufacture another set of optional questions.
    if not questions and not previous:
        result["questions"] = [
            {"question": "入住和退房的具体日期是什么？", "reason": "入住时长已知，但日期会影响可订房型和价格。", "importance": "重要", "suggested_answers": []},
            {"question": "需要我也筛选周边环境吗，例如临街噪音、夜间施工或交通便利性？", "reason": "这些因素会影响安静程度和出行体验。", "importance": "建议", "suggested_answers": []},
            {"question": "价格上限是否包含税费和服务费？是否需要可免费取消？", "reason": "总价和取消政策可能影响最终预订选择。", "importance": "建议", "suggested_answers": []},
        ]
    result.setdefault("title", "预定酒店")
    result.setdefault("intent", "根据目标城市、区域、预算和住宿偏好寻找并预定酒店；提交订单前需要你确认。")
    # These are the runtime fields a future booking request must supply. Their
    # definitions belong to the reusable scenario template; values are per run.
    result.setdefault("required_inputs", [
        {"name":"destination_city","label":"目的城市","type":"string","required":True,"help":"例如：武汉"},
        {"name":"check_in_date","label":"入住日期","type":"date","required":True,"help":"例如：2026-11-12"},
        {"name":"check_out_date","label":"退房日期","type":"date","required":True,"help":"例如：2026-11-15"},
        {"name":"guest_count","label":"入住人数","type":"number","required":True,"help":"例如：2"},
    ])
    scope = result.get("scope") if isinstance(result.get("scope"), dict) else {}
    by_dimension = any(term in text for term in ("不同城市", "按城市", "每个城市", "各城市", "不同地区", "按地区"))
    city_fact = next((str(x.get("value")) for x in facts if isinstance(x, dict) and x.get("name") == "destination_city" and x.get("value")), "")
    result["scope"] = {"mode":"by_dimension" if by_dimension else "global", "dimension":"destination_city", "label":"目的城市", "value":city_fact if by_dimension else ""}
    required_inputs = result.get("required_inputs") if isinstance(result.get("required_inputs"), list) else []
    by_name = {str(x.get("name")):x for x in required_inputs if isinstance(x, dict) and x.get("name")}
    core_inputs = [
        {"name":"destination_city","label":"目的城市","type":"string","required":True,"help":"例如：武汉"},
        {"name":"check_in_date","label":"入住日期","type":"date","required":True,"help":"例如：2026-11-12"},
        {"name":"check_out_date","label":"退房日期","type":"date","required":True,"help":"例如：2026-11-15"},
        {"name":"guest_count","label":"入住人数","type":"number","required":True,"help":"例如：2"},
    ]
    for item in core_inputs:
        old = by_name.get(item["name"], {})
        by_name[item["name"]] = {**item, **old, "required":True}
    result["required_inputs"] = list(by_name.values())[:80]
    return result


def configured() -> bool:
    try:
        cfg = read_model_service()
        return bool(cfg["base_url"] and cfg["model"])
    except ModelServiceError:
        return False


def analyze(user_text: str, previous: dict[str, Any] | None = None, answers: list[dict[str, str]] | None = None, catalog: dict[str, Any] | None = None, language: str | None = None) -> dict[str, Any]:
    try:
        config = read_model_service()
    except ModelServiceError as exc:
        raise ScenarioProviderError(str(exc)) from exc
    base, model = config["base_url"], config["model"]
    if not base or not model:
        raise ScenarioProviderError("尚未配置模型服务，请打开“模型服务”菜单进行设置。")
    endpoint = model_endpoint(config)
    system = """你是个人本体治理系统的场景分析器。必须认真抽取用户原话，不能因为输入简短、使用逗号或省略主语就输出空数组。只要用户提到酒店预订，就至少生成一个酒店资源类型、一个查找动作和一个需要确认的预订动作；逐项保留输入中明确的城市、区域、价格、吸烟、安静、停车和入住时长信息。用户数据中包含当前本体目录；资源类型或动作有合适现成项时优先引用其名称，并在输出对象增加 existing_id 字段，未命中则提出新项。title 必须是可复用的任务名称，只描述“做什么+处理什么对象”，例如“预订机票”“预订酒店”；不得包含本次请求中的时间、城市、日期、价格等临时信息。用户可以在界面修改该建议。
输出严格 JSON 对象，不要 markdown。字段：title(中文), intent(中文), facts(数组，每项 {name,label,value,type,source}，type 为 string/number/boolean/date), resource_types(数组，每项 {name,description,attributes:[字段名]}), actions(数组，每项 {name,description,risk}), policies(数组，每项 {subject,resource,actions,effect,conditions}，effect 仅 allow/deny/ask；conditions 为数组，每项 {field,operator,value,label}，operator 只可 equals/lte/gte/exists；只有可明确表达为这些操作符的条件才生成结构化项), questions(数组，每项 {question,reason,importance,suggested_answers}), required_inputs(数组，每项 {name,label,type,required,help}，type 只能 string/number/bool/date；表示每次执行该通用场景时调用方必须提供的字段定义，而不是本次描述必须填入的值), scope({mode:"global"或"by_dimension",dimension,label})。
抽取明确提到的条件到 facts/conditions，未知值不要编造。区分场景模板范围：用户只描述一次目的城市/地点时，默认 scope.mode="global"，地点是每次调用要提供的 required_input，不要将本次城市写成永久条件；只有用户明确要求为不同地点维护不同偏好时，才用 by_dimension。主动考虑场景经常遗漏的重要因素并作为 questions 建议；明确标记建议性质，不要把建议当成用户偏好或授权条件。required_inputs 至少包含完成该任务必需的运行时字段（如酒店预订的目的城市、入住退房日期、人数），这些字段仅定义必填清单，不阻止本次模板保存。信息不足时询问可执行动作、对象或范围。涉及“我”时 subject 写“我（待选择主体）”。授权 effect 默认 ask，除非用户明确表达授权意图；即使明确允许也仅为待审草稿。
字段命名契约（强制，违反会被系统改写）：facts、resource_types.attributes、required_inputs、policies.conditions 里凡是表示字段的地方，name/field 必须是英文小写 snake_case 机器键（只含 a-z0-9_，以字母开头，例如 destination_city、budget_per_night、non_smoking_room），label 必须是{LANG_LABEL}显示名。禁止用中文当 name；禁止用拼音或缩写。既有目录里已有同义字段时，必须复用它的英文键。
同一语义只允许出现一次：不要既写「无烟」又写 smoking_policy，只保留一条，name 用英文键、label 用{LANG_LABEL}。
必须分清两类字段：
（1）每次执行要重新收集的字段（值每次都不同：城市、区域、日期、时段、人数、房间数、入住人姓名等）放进 required_inputs，required=true；它们不属于长期偏好，也不要写进 facts 当作偏好。
（2）长期偏好（一贯要求：预算上限、无烟、停车位、安静、含早等）写进 facts 并带上值，不要放进 required_inputs；它们会成为场景实例的长期约束。
示例——正确：{"name":"non_smoking_room","label":"{LANG_EXAMPLE_1}","value":true,"type":"boolean"}；{"name":"budget_per_night","label":"{LANG_EXAMPLE_2}","value":400,"type":"number"}。
示例——错误：{"name":"无烟","label":"无烟"}（中文当 name）、{"name":"smoking_policy","label":"吸烟要求"}（与「无烟」重复，应合并为 non_smoking_room）、把「每日预算」写进 required_inputs（它是长期偏好，不是每次收集项）。
授权策略必须声明适用动作：每条 policy 增加 actions 字段，取值必须是本场景 actions 里出现过的动作名称（可多条）。同一个资源类型下不同动作有不同立场时，必须拆成多条策略，不要在一条策略里混合。例如"允许查看和编辑、禁止删除"要写成两条：{"effect":"allow","actions":["查看文件","编辑文件"],"conditions":[...]} 与 {"effect":"deny","actions":["删除文件"],"conditions":[...]}。
字段分三档，逐个判断并在对象里写明 role 与 role_reason（一句话，说明为什么这样判断）：
（1）role="required" 每次执行必须收集：值每次都不同，且不提供就无法执行（城市、日期、人数、目标主机、文件路径）。放进 required_inputs。
（2）role="preference" 长期立场：一贯要求，与本次无关（无烟房、预算上限、禁止外发）。放进 facts。
（3）role="both" 两者兼有：既有长期立场，值又每次不同（例如"只订未来 30 天内的" + 具体日期；"预算按我设的上限" + 本次金额）。这样的字段要同时出现在 required_inputs 与 facts 里，两处的 role 都写 "both"。
不要为了省事把模糊的字段一律塞进 required_inputs：只有"不提供就无法执行"的才进必填。宁可选 preference，也不要滥加必填。
禁止写无条件的拒绝：effect 为 deny 的策略必须有 conditions 且限定 actions，否则会否决该场景的全部动作。只有在你确实要否决全部动作时才省略 conditions。
不要跨领域扩张：场景的资源类型与动作必须限定在用户这次描述直接处理的对象上。补充回答中提到其他领域（例如网络、发票）时，把它们作为偏好或必填信息记录，不要新增那个领域的资源类型或动作。"""
    user = {"user_input": user_text, "previous_analysis": previous or {}, "answers_to_questions": answers or [], "existing_ontology_catalog": catalog or {}}
    language = display_language(language)
    system = (system.replace("{LANG_LABEL}", "英文" if language == "en" else "中文")
                    .replace("{LANG_EXAMPLE_1}", "Non-smoking room" if language == "en" else "无烟房")
                    .replace("{LANG_EXAMPLE_2}", "Budget per night" if language == "en" else "每日预算"))
    payload = json.dumps({"model": model, "temperature": 0.2, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]}, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    key = config["api_key"]
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read(2_000_001))
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise ScenarioProviderError("模型服务认证失败，请到“模型服务”菜单检查 API Key。") from exc
        if exc.code == 404:
            raise ScenarioProviderError("模型接口或模型名称未找到，请到“模型服务”菜单检查配置。") from exc
        raise ScenarioProviderError(f"模型服务请求失败（HTTP {exc.code}）；请确认该模型支持 JSON 格式输出。") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ScenarioProviderError("场景分析服务暂时无法连接，请检查模型地址和网络。") from exc
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ScenarioProviderError("场景分析服务返回格式无效，请检查模型是否支持 JSON 输出。") from exc
    if not isinstance(result, dict):
        raise ScenarioProviderError("场景分析服务返回的数据不是 JSON 对象。")
    if isinstance(result.get("analysis"), dict):
        result = result["analysis"]
    aliases = {"scenario_facts":"facts", "resources":"resource_types", "operations":"actions", "authorization_policies":"policies", "follow_up_questions":"questions"}
    for source, target in aliases.items():
        if target not in result and isinstance(result.get(source), list):
            result[target] = result[source]
    result = _hotel_fallback(user_text, result, previous, language)
    result["title"] = generic_title(user_text, result)
    if previous:
        result["questions"] = []
        result["supplement_completed"] = True
    else:
        result["supplement_completed"] = False
    # Bound untrusted provider output before storing or displaying it.
    for key_name, max_count in (("facts", 80), ("resource_types", 30), ("actions", 50), ("policies", 50), ("questions", 50)):
        value = result.get(key_name, [])
        if not isinstance(value, list) or len(value) > max_count or any(not isinstance(item, dict) for item in value):
            raise ScenarioProviderError(f"场景分析字段 {key_name} 的格式不正确。")
    if len(json.dumps(result, ensure_ascii=False)) > 250_000:
        raise ScenarioProviderError("场景分析结果过大，请缩短输入后重试。")
    for policy in result.get("policies", []):
        if policy.get("effect") not in {"allow", "deny", "ask"}:
            policy["effect"] = "ask"
        policy["policy_status"] = "draft"
    # Enforce the naming contract last, so it also covers provider output that
    # slipped through and the deterministic hotel fallback above. The model is
    # asked to emit English keys; this guarantees it.
    # 兜底路径（以及任何未给出分档的输出）补一个默认档位，避免界面显示"未标注"。
    for item in result.get("required_inputs") or []:
        if isinstance(item, dict) and not item.get("role"):
            item["role"] = "required"
            item.setdefault("role_reason", "由系统补全：完成该场景必须提供")
    for item in result.get("facts") or []:
        if isinstance(item, dict) and not item.get("role"):
            item["role"] = "preference"
            item.setdefault("role_reason", "由系统补全的长期立场")
    normalize_analysis(result, language)
    # 契约校验（docs/09）：违规不阻断，只记录到 contract_notes，供界面提示。
    try:
        from .analysis_contract import validate_analysis
        result["contract_notes"] = validate_analysis(result)
    except Exception:
        result["contract_notes"] = []
    return result
