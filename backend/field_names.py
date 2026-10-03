"""Field naming contract: English machine key + Chinese display name.

The scene slicer is a language model and therefore not a reliable source of
machine identifiers. It may emit ``"每日预算"`` as a field *name*, while the rest
of the pipeline (param ids, authorization constraint keys, the decision context)
needs a stable ASCII key. Previously such a name travelled all the way to the
store, where ``re.sub(r"[^A-Za-z0-9_-]", "_", name)`` turned it into ``"____"`` —
several distinct Chinese names collapsed onto the same id, and the preference
save path rejected the row outright with an unlocatable message.

This module makes the contract deterministic instead of hopeful:

    name      ASCII snake_case — the only value ever persisted or compared
    label_zh  Chinese display name — display only

Every field definition carries both. Anything that violates the contract is
*converted* here (never silently dropped, never rejected as a whole request), and
the conversion is reported back so it can be surfaced to the user.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

FIELD_NAME_PATTERN = r"[a-z][a-z0-9_]{0,63}"
_FIELD_RE = re.compile(rf"^{FIELD_NAME_PATTERN}$")
_ASCII_SAFE_RE = re.compile(r"[^A-Za-z0-9_]+")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

MAX_FIELD_NAME = 64

# --------------------------------------------------------------------------
# Vocabulary: canonical machine key <- every alias ever seen for that concept.
# Chinese aliases and legacy English keys both live here, which is what lets the
# same concept declared twice ("无烟" and "smoking_policy") collapse into one.
# --------------------------------------------------------------------------
_CANONICAL: dict[str, tuple[str, ...]] = {
    # --- per-execution inputs -------------------------------------------------
    "destination_city": ("目的城市", "目标城市", "目的地城市", "到达城市", "所在城市", "城市", "目的地", "地点", "destination_city", "destination", "city", "target_city"),
    "departure_city": ("出发城市", "起飞城市", "始发城市", "出发地", "departure_city", "origin_city", "from_city"),
    "district": ("区域", "行政区", "所在区", "地段", "商圈", "区域偏好", "district", "area", "zone"),
    "check_in_date": ("入住日期", "入住时间", "到店日期", "入住日", "check_in_date", "checkin_date", "arrival_date"),
    "check_out_date": ("退房日期", "离开日期", "离店日期", "退房时间", "check_out_date", "checkout_date", "departure_date_hotel", "leaving_date"),
    "check_in_time_period": ("入住时段", "入住时间段", "到店时段", "check_in_time_period", "check_in_window"),
    "departure_date": ("出发日期", "起飞日期", "出发日", "departure_date", "flight_date", "travel_date"),
    "departure_time_period": ("出发时段", "出发时间段", "起飞时段", "departure_time_period", "departure_window"),
    "duration_nights": ("入住时长", "住宿时长", "入住天数", "住宿天数", "住几晚", "入住晚数", "duration_nights", "stay_duration", "nights", "stay_nights"),
    "duration_unit": ("时长单位", "住宿单位", "duration_unit", "stay_unit"),
    "guest_count": ("入住人数", "人数", "住客人数", "客人数", "成人人数", "人数合计", "guest_count", "guests", "guest_num", "guests_count", "num_guests", "number_of_guests", "adult_count"),
    "room_count": ("房间数", "房间数量", "几间房", "房量", "客房数", "room_count", "rooms", "room_num", "rooms_count", "num_rooms", "number_of_rooms", "room_quantity"),
    "guest_name": ("入住人姓名", "入住人", "住客姓名", "预订人姓名", "预订人", "联系人", "guest_name", "booker_name", "contact_name"),
    "guest_contact_phone": ("入住人联系电话", "入住人手机号", "联系电话", "联系人电话", "手机号", "手机号码", "guest_contact_phone", "contact_phone", "phone", "mobile"),
    "passenger_info": ("乘机人信息", "乘机人", "旅客信息", "乘客信息", "passenger_info", "passenger", "traveller_info"),
    "check_in_time": ("入住时间要求", "入住时间点", "到店时间", "入住时刻", "check_in_time", "arrival_time"),
    "invoice_title": ("发票抬头", "开票抬头", "抬头", "发票抬头信息", "invoice_title", "invoice_header"),
    "hotel_name": ("酒店名称", "指定酒店", "酒店偏好名称", "hotel_name"),
    "star_rating": ("星级", "酒店星级", "星级要求", "star_rating", "hotel_stars"),
    # --- reusable preferences -------------------------------------------------
    "budget_per_night": ("每日预算", "每天预算", "每晚预算", "单晚预算", "日预算", "预算上限", "房价上限", "房价不超过", "budget_per_night", "nightly_budget", "daily_budget"),
    "budget_total": ("总预算", "预算总额", "合计预算", "整体预算", "预算", "budget_total", "total_budget", "budget"),
    "price_min": ("最低价格", "价格下限", "最低房价", "价低", "min_price", "price_min", "budget_min", "price_lower"),
    "price_max": ("最高价格", "价格上限", "最高房价", "价格不高于", "max_price", "price_max", "budget_max", "price_upper"),
    "price": ("价格", "房价", "价钱", "单晚价格", "price", "room_price"),
    "non_smoking_room": ("无烟", "无烟房", "禁烟房", "禁烟", "不吸烟", "不吸烟楼层", "吸烟政策", "吸烟要求", "无烟楼层", "无烟房要求", "non_smoking_room", "non_smoking", "no_smoking", "non_smoking_required", "smoking_policy", "smoke_free"),
    "parking_required": ("停车位", "停车", "停车场", "停车需求", "有停车位", "需要停车位", "需要停车场", "酒店有停车位", "车位", "parking_required", "parking", "need_parking", "hotel_parking", "hotel_parking_required", "parking_needed", "requires_parking", "parking_space", "car_park"),
    "quiet_environment": ("安静", "环境安静", "安静房间", "安静楼层", "周边安静", "周围安静", "环境要安静", "噪音环境", "环境要求", "不吵", "隔音", "quiet_environment", "quiet", "quiet_required", "quiet_surroundings", "quiet_surroundings_required", "noise_level", "noise_free"),
    "room_type": ("房型", "房型偏好", "床型", "房间类型", "room_type", "bed_type"),
    "breakfast_included": ("早餐", "含早", "是否含早", "早餐是否包含", "早餐要求", "breakfast_included", "breakfast"),
    "invoice_available": ("发票", "能否开票", "发票要求", "需要发票", "需要开发票", "可开发票", "invoice_available", "invoice", "need_invoice", "invoice_needed", "invoice_required", "requires_invoice"),
    "cancellation_policy": ("取消政策", "是否可取消", "退改政策", "免费取消", "cancellation_policy", "cancellation"),
    "booker_relation": ("预订人与入住人关系", "预订关系", "入住关系", "booker_relation"),
    "contact_info_default": ("联系方式", "默认联系方式", "联系信息", "contact_info_default", "contact_info"),
    # --- flight ---------------------------------------------------------------
    "cabin_class": ("舱位", "舱位等级", "舱位要求", "cabin_class", "cabin", "seat_class"),
    "flight_number": ("航班号", "航班", "flight_number", "flight_no"),
    "airline": ("航空公司", "航司", "airline", "carrier"),
    "fare_max": ("票价上限", "最高票价", "票价不高于", "fare_max", "max_fare"),
    "stops": ("是否中转", "中转", "经停", "stops", "transit"),
    "baggage_allowance": ("行李额", "行李额度", "免费行李", "baggage_allowance", "baggage"),
    # --- generic --------------------------------------------------------------
    "note": ("备注", "说明", "补充说明", "note", "remark"),
    "quantity": ("数量", "quantity", "count"),
    "amount": ("金额", "总额", "amount"),
    "date": ("日期", "date"),
    "time": ("时间", "time"),
}

# Canonical key -> type, so a value carrying "1晚" can still be compared
# numerically and "需要停车场" can still be compared as a boolean.
_TYPES: dict[str, str] = {
    "destination_city": "string", "departure_city": "string", "district": "string",
    "check_in_date": "date", "check_out_date": "date", "check_in_time_period": "string",
    "departure_date": "date", "departure_time_period": "string",
    "duration_nights": "number", "duration_unit": "string",
    "guest_count": "number", "room_count": "number", "guest_name": "string",
    "guest_contact_phone": "string", "passenger_info": "string",
    "check_in_time": "string", "invoice_title": "string",
    "hotel_name": "string", "star_rating": "number",
    "budget_per_night": "number", "budget_total": "number",
    "price_min": "number", "price_max": "number", "price": "number",
    "non_smoking_room": "bool", "parking_required": "bool", "quiet_environment": "bool",
    "room_type": "string", "breakfast_included": "bool", "invoice_available": "bool",
    "cancellation_policy": "string", "booker_relation": "string", "contact_info_default": "string",
    "cabin_class": "string", "flight_number": "string", "airline": "string",
    "fare_max": "number", "stops": "number", "baggage_allowance": "number",
    "note": "string", "quantity": "number", "amount": "number", "date": "date", "time": "string",
}

# Chinese display name per canonical key, used when the model supplied none.
_LABELS: dict[str, str] = {
    "destination_city": "目的城市", "departure_city": "出发城市", "district": "区域",
    "check_in_date": "入住日期", "check_out_date": "退房日期",
    "check_in_time_period": "入住时段", "departure_date": "出发日期",
    "departure_time_period": "出发时段", "duration_nights": "入住时长",
    "duration_unit": "时长单位", "guest_count": "入住人数", "room_count": "房间数",
    "guest_name": "入住人姓名", "guest_contact_phone": "入住人联系电话",
    "passenger_info": "乘机人信息", "check_in_time": "入住时间要求",
    "invoice_title": "发票抬头", "hotel_name": "酒店名称", "star_rating": "酒店星级",
    "budget_per_night": "每日预算", "budget_total": "总预算",
    "price_min": "最低价格", "price_max": "最高价格", "price": "价格",
    "non_smoking_room": "无烟房", "parking_required": "需要停车位",
    "quiet_environment": "环境安静", "room_type": "房型",
    "breakfast_included": "含早餐", "invoice_available": "可开发票",
    "cancellation_policy": "取消政策", "booker_relation": "预订关系",
    "contact_info_default": "联系方式", "cabin_class": "舱位",
    "flight_number": "航班号", "airline": "航空公司", "fare_max": "票价上限",
    "stops": "中转次数", "baggage_allowance": "行李额",
    "note": "备注", "quantity": "数量", "amount": "金额", "date": "日期", "time": "时间",
}

# English display names for the same canonical keys (label language follows the
# display-language setting; the machine key is always ASCII either way).
_LABELS_EN: dict[str, str] = {
    "destination_city": "Destination city",
    "departure_city": "Departure city",
    "district": "District",
    "check_in_date": "Check-in date",
    "check_out_date": "Check-out date",
    "check_in_time_period": "Check-in window",
    "departure_date": "Departure date",
    "departure_time_period": "Departure window",
    "duration_nights": "Nights",
    "duration_unit": "Duration unit",
    "guest_count": "Number of guests",
    "room_count": "Number of rooms",
    "guest_name": "Guest name",
    "guest_contact_phone": "Guest phone",
    "passenger_info": "Passenger details",
    "check_in_time": "Check-in time",
    "invoice_title": "Invoice title",
    "hotel_name": "Hotel name",
    "star_rating": "Star rating",
    "budget_per_night": "Budget per night",
    "budget_total": "Total budget",
    "price_min": "Minimum price",
    "price_max": "Maximum price",
    "price": "Price",
    "non_smoking_room": "Non-smoking room",
    "parking_required": "Parking required",
    "quiet_environment": "Quiet environment",
    "room_type": "Room type",
    "breakfast_included": "Breakfast included",
    "invoice_available": "Invoice available",
    "cancellation_policy": "Cancellation policy",
    "booker_relation": "Booker relationship",
    "contact_info_default": "Contact details",
    "cabin_class": "Cabin class",
    "flight_number": "Flight number",
    "airline": "Airline",
    "fare_max": "Maximum fare",
    "stops": "Stops",
    "baggage_allowance": "Baggage allowance",
    "note": "Note",
    "quantity": "Quantity",
    "amount": "Amount",
    "date": "Date",
    "time": "Time",
}


# Values that only ever describe one execution. They must be collected every run
# (required_inputs) and must never become standing preferences.
ALWAYS_RUNTIME: frozenset[str] = frozenset({
    "destination_city", "departure_city", "district", "check_in_date", "check_out_date",
    "check_in_time", "check_in_time_period", "departure_date", "departure_time_period",
    "duration_nights", "duration_unit", "guest_count", "room_count", "guest_name",
    "guest_contact_phone", "passenger_info", "flight_number",
})

# Standing requirements. They belong to preferences; keeping them in
# required_inputs used to (a) ask the agent for them on every execution and
# (b) silently drop them from preferences via _prune_preferences.
NEVER_RUNTIME: frozenset[str] = frozenset({
    "budget_per_night", "budget_total", "price_min", "price_max", "price",
    "non_smoking_room", "parking_required", "quiet_environment", "room_type",
    "breakfast_included", "invoice_available", "cancellation_policy",
    "booker_relation", "contact_info_default", "cabin_class", "airline",
    "fare_max", "stops", "baggage_allowance", "hotel_name", "star_rating",
})

_TIME_ONLY = {"今天", "今日", "明天", "明日", "后天", "大后天", "昨天", "前天", "今晚", "明晚"}

# Longest alias first, so "每日预算" wins over "预算".
_ALIAS_INDEX: list[tuple[str, str]] = sorted(
    ((alias.casefold(), canonical) for canonical, aliases in _CANONICAL.items() for alias in (canonical, *aliases)),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

_NEGATIVE_MARKERS = ("不需要", "不用", "无需", "不要", "不要求", "无要求", "没有", "否", "不含", "no")
_POSITIVE_MARKERS = ("需要", "要有", "有", "是", "要求", "无烟", "禁烟", "不吸烟", "安静", "含", "可以", "yes")


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def field_type(name: str) -> str:
    return _TYPES.get(name, "string")


def default_label(name: str, language: str = "zh") -> str:
    """Canonical key -> display name in the requested language (key itself if unknown)."""
    table = _LABELS_EN if str(language).lower().startswith("en") else _LABELS
    return table.get(name) or name


def _fallback_name(text: str) -> str:
    """Stable, unique, ASCII — used when no vocabulary entry matches.

    A content hash keeps two *different* unknown Chinese names apart. The old
    ``re.sub`` approach mapped every 4-character name to the same "____" id.
    """
    slug = _ASCII_SAFE_RE.sub("_", text.strip().lower()).strip("_")
    slug = re.sub(r"_{2,}", "_", slug)
    if slug and _FIELD_RE.match(slug):
        return slug[:MAX_FIELD_NAME]
    if slug:
        slug = slug.lstrip("0123456789_")
        if slug and _FIELD_RE.match(slug):
            return slug[:MAX_FIELD_NAME]
    digest = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:10]
    return f"field_{digest}"


# A model that invents its own ASCII key tends to decorate it
# ("need_parking", "number_of_guests", "quiet_surroundings_required"). Stripping
# the decoration and looking the stem up again is what collapses those onto the
# same canonical key instead of leaving two fields for one concept.
_ASCII_PREFIXES: tuple[str, ...] = (
    "number_of_", "number_", "count_of_", "total_", "num_", "amount_",
    "needs_", "need_", "requires_", "require_", "required_", "wants_", "want_",
    "prefers_", "prefer_", "preferred_", "has_", "have_", "is_", "are_",
    "with_", "without_", "no_", "non_", "using_", "use_", "enable_", "enabled_",
)
_ASCII_SUFFIXES: tuple[str, ...] = (
    "_required", "_requirement", "_needed", "_needs", "_needed_flag", "_flag",
    "_status", "_available", "_enabled", "_allowed", "_preference",
    "_preferences", "_pref", "_setting", "_option", "_count", "_num",
)


def _ascii_alias(text: str) -> str | None:
    """Map a model-invented ASCII key onto a canonical key, or return None."""
    folded = text.strip().casefold().replace("-", "_")
    if has_cjk(folded) or not _FIELD_RE.match(folded):
        return None
    hit = _ALIAS_INDEX_MAP.get(folded)
    if hit:
        return hit
    stem = folded
    for _ in range(2):  # "number_of_guests_required" needs two strips
        stripped = stem
        for prefix in _ASCII_PREFIXES:
            if stripped.startswith(prefix) and len(stripped) > len(prefix):
                stripped = stripped[len(prefix):]
                break
        for suffix in _ASCII_SUFFIXES:
            if stripped.endswith(suffix) and len(stripped) > len(suffix):
                stripped = stripped[: -len(suffix)]
                break
        if stripped == stem:
            return None
        hit = _ALIAS_INDEX_MAP.get(stripped)
        if hit:
            return hit
        stem = stripped
    return None


def canonical_field_name(raw: Any, label: Any = "") -> str:
    """Return the ASCII machine key for a field, or "" when there is nothing to key on.

    Resolution order: exact alias on the raw value -> exact alias on the Chinese
    label -> an unrecognised but well-formed ASCII key is kept -> partial match ->
    deterministic hashed fallback.

    The label outranks "raw already looks like a key" on purpose. A model key such
    as ``number_of_guests`` is well-formed ASCII yet not the canonical key for
    入住人数, and letting it through left one concept occupying two fields — so the
    agent asked for it twice and the preference pool carried both spellings.
    """
    raw_text = str(raw or "").strip()
    label_text = str(label or "").strip()
    for text in (raw_text, label_text):
        if not text:
            continue
        hit = _ALIAS_INDEX_MAP.get(text.casefold())
        if hit:
            return hit
        hit = _ascii_alias(text)
        if hit:
            return hit
    if raw_text:
        folded = raw_text.casefold().replace("-", "_")
        if _FIELD_RE.match(folded):
            return folded[:MAX_FIELD_NAME]
    for text in (raw_text, label_text):
        folded = text.casefold()
        if not folded:
            continue
        for alias, canonical in _ALIAS_INDEX:
            if len(alias) >= 2 and alias in folded:
                return canonical
    for text in (raw_text, label_text):
        if text:
            return _fallback_name(text)
    return ""


_ALIAS_INDEX_MAP: dict[str, str] = {alias: canonical for alias, canonical in _ALIAS_INDEX}


def display_label(raw: Any, label: Any, canonical: str, language: str = "zh") -> str:
    """Display name in the requested language, preferring what the model wrote, then our table."""
    for candidate in (label, raw):
        text = str(candidate or "").strip()
        if text and not _FIELD_RE.match(text.casefold().replace("-", "_")):
            return text
    return default_label(canonical, language)


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if not text:
        return None
    if text in {"true", "1", "y", "yes"}:
        return True
    if text in {"false", "0", "n", "no"}:
        return False
    if any(marker in text for marker in _NEGATIVE_MARKERS):
        return False
    if any(marker in text for marker in _POSITIVE_MARKERS):
        return True
    return None


def _coerce_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    match = _NUMBER_RE.search(str(value or ""))
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else number


def coerce_value(canonical: str, value: Any) -> Any:
    """Turn free text into a value the constraint engine can compare."""
    expected = field_type(canonical)
    if expected == "bool":
        coerced = _coerce_bool(value)
        return coerced if coerced is not None else value
    if expected == "number":
        coerced = _coerce_number(value)
        return coerced if coerced is not None else value
    return value


def _value_score(expected: str, value: Any) -> int:
    if value in (None, "") or isinstance(value, list) or isinstance(value, dict):
        return 0
    if expected == "bool":
        return 3 if isinstance(value, bool) else 1
    if expected == "number":
        return 3 if isinstance(value, (int, float)) and not isinstance(value, bool) else 1
    if expected in {"string", "date"}:
        return 2 if isinstance(value, str) else 1
    return 1


def normalize_facts(facts: Iterable[Any], changes: list[dict[str, Any]], language: str = "zh") -> list[dict[str, Any]]:
    """Canonicalise fact names and merge duplicates onto a single key."""
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in facts:
        if not isinstance(item, dict):
            continue
        raw_name = str(item.get("name") or "").strip()
        raw_label = str(item.get("label") or "").strip()
        if not raw_name and not raw_label:
            continue
        canonical = canonical_field_name(raw_name, raw_label)
        expected = field_type(canonical)
        value = coerce_value(canonical, item.get("value"))
        candidate = {
            "name": canonical,
            "label": display_label(raw_name, raw_label, canonical, language),
            "value": value,
            "type": expected,
            "source": str(item.get("source") or "user"),
        }
        if canonical not in grouped:
            grouped[canonical] = candidate
            order.append(canonical)
            if raw_name and raw_name != canonical:
                changes.append({"scope": "facts", "from": raw_name, "to": canonical, "label": candidate["label"]})
            continue
        existing = grouped[canonical]
        existing_rank = (existing.get("source") == "user", _value_score(expected, existing.get("value")))
        candidate_rank = (candidate.get("source") == "user", _value_score(expected, candidate.get("value")))
        if candidate_rank > existing_rank:
            grouped[canonical] = {**existing, **candidate}
        if raw_name and raw_name != canonical:
            changes.append({"scope": "facts", "from": raw_name, "to": canonical, "label": existing["label"]})
    return [grouped[name] for name in order]


def normalize_required_inputs(items: Any, changes: list[dict[str, Any]], language: str = "zh") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (per-execution inputs, fields demoted to preferences).

    A field that expresses a standing requirement is removed from the runtime
    list. Keeping it there is what made the agent ask for it on every execution
    *and* made the preference silently disappear from the instance.
    """
    if not isinstance(items, list):
        return [], []
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_name = str(item.get("name") or "").strip()
        raw_label = str(item.get("label") or "").strip()
        if not raw_name and not raw_label:
            continue
        canonical = canonical_field_name(raw_name, raw_label)
        if canonical not in merged:
            merged[canonical] = {
                "name": canonical,
                "label": display_label(raw_name, raw_label, canonical, language),
                "type": field_type(canonical),
                "required": bool(item.get("required", True)),
                "help": str(item.get("help") or "").strip(),
                "role": str(item.get("role") or "").strip(),
            }
            order.append(canonical)
            if raw_name and raw_name != canonical:
                changes.append({"scope": "required_inputs", "from": raw_name, "to": canonical, "label": merged[canonical]["label"]})
            continue
        existing = merged[canonical]
        existing["required"] = existing["required"] or bool(item.get("required", True))
        existing["help"] = existing["help"] or str(item.get("help") or "").strip()
        if raw_name and raw_name != canonical:
            changes.append({"scope": "required_inputs", "from": raw_name, "to": canonical, "label": existing["label"]})
    runtime: list[dict[str, Any]] = []
    demoted: list[dict[str, Any]] = []
    for name in order:
        item = merged[name]
        # 模型明确说这是"两者兼有"（既有长期立场、值又每次不同）时，不能被降级出必填清单。
        if name in NEVER_RUNTIME and item.get("role") != "both":
            demoted.append(item)
        elif name in ALWAYS_RUNTIME or item["required"]:
            runtime.append(item)
        else:
            demoted.append(item)
    return runtime[:80], demoted


def _carry_role(source: Any, normalized: Any, changes: list[dict[str, Any]]) -> None:
    """把模型给出的分档（role）与理由（role_reason）搬到重建后的对象上。

    规范化可能改名（budget_max → price_max），因此用 changes 里的改动记录建别名表。
    """
    if not isinstance(source, list) or not isinstance(normalized, list): return
    by_name: dict[str, dict[str, Any]] = {}
    for item in source:
        if isinstance(item, dict) and item.get("name"):
            by_name[str(item["name"])] = item
    alias = {str(c["from"]): str(c["to"]) for c in changes
             if isinstance(c, dict) and c.get("from") and c.get("to")}
    for item in normalized:
        if not isinstance(item, dict): continue
        name = str(item.get("name") or "")
        src = by_name.get(name)
        if src is None:
            for raw, canonical in alias.items():
                if canonical == name and raw in by_name:
                    src = by_name[raw]; break
        if not src: continue
        for key in ("role", "role_reason"):
            if src.get(key) and not item.get(key): item[key] = src[key]


def normalize_analysis(result: dict[str, Any], language: str = "zh") -> dict[str, Any]:
    """Apply the naming contract to a whole slicer result, in place.

    Covers facts, required_inputs, resource type attributes and authorization
    conditions, so every identifier that reaches the store or the decision engine
    is already ASCII. The conversions are reported under ``field_normalization``.
    """
    changes: list[dict[str, Any]] = []
    # normalize_* 会重建对象（只带固定字段），分档与理由需要单独搬运回来。
    raw_facts = result.get("facts")
    raw_inputs = result.get("required_inputs")
    facts = result.get("facts")
    if isinstance(facts, list):
        result["facts"] = normalize_facts(facts, changes, language)

    runtime, demoted = normalize_required_inputs(result.get("required_inputs"), changes, language)
    if runtime or demoted:
        result["required_inputs"] = runtime
        if demoted:
            result["demoted_fields"] = [{"name": x["name"], "label": x["label"], "role": x.get("role")} for x in demoted]
    _carry_role(raw_facts, result.get("facts"), changes)
    _carry_role(raw_inputs, result.get("required_inputs"), changes)

    resource_types = result.get("resource_types")
    if isinstance(resource_types, list):
        for entry in resource_types:
            if not isinstance(entry, dict):
                continue
            attributes = entry.get("attributes")
            if not isinstance(attributes, list):
                continue
            seen: list[str] = []
            for attribute in attributes:
                canonical = canonical_field_name(attribute, attribute)
                if canonical not in seen:
                    seen.append(canonical)
            entry["attributes"] = seen

    policies = result.get("policies")
    if isinstance(policies, list):
        for policy in policies:
            if not isinstance(policy, dict):
                continue
            conditions = policy.get("conditions")
            if not isinstance(conditions, list):
                continue
            cleaned = []
            for condition in conditions:
                if not isinstance(condition, dict):
                    continue
                raw_field = str(condition.get("field") or "").strip()
                label = str(condition.get("label") or "").strip()
                if not raw_field and not label:
                    continue
                canonical = canonical_field_name(raw_field, label)
                if raw_field and raw_field != canonical:
                    changes.append({"scope": "policy_conditions", "from": raw_field, "to": canonical, "label": label or canonical})
                cleaned.append({**condition, "field": canonical, "label": label or default_label(canonical)})
            policy["conditions"] = cleaned

    if changes:
        deduped: list[dict[str, Any]] = []
        for change in changes:
            if change not in deduped:
                deduped.append(change)
        result["field_normalization"] = deduped[:100]
    return result


def is_relative_time(value: Any) -> bool:
    return isinstance(value, str) and value.strip() in _TIME_ONLY
