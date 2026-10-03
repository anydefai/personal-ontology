from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config
from . import messages
from .origin_policy import origin_allowed
from .config import (BACKEND_PORT, COMMON_PASSWORDS_FILE, DATA_DIR, HOST, MODEL_CONFIG_FILE, MODEL_KEY_FILE, PORT,
                     MANAGER_PORT, SESSION_TOKEN_FILE, SETTINGS_FILE, SUPPORTED_LANGUAGES, TOKEN_FILE, WEB_DIR,
                     display_language, read_settings, stored_language)
from . import agent_access, agent_gateway
from .model import CLASSES, INPUT_ID_FIELDS
from .store import RDFStore, StoreError, StoreLocked, ValidationError, decode_constraint_value, parse_temporal
from .scenario_llm import ScenarioProviderError, analyze as analyze_scenario, configured as scenario_provider_configured, generic_title as generic_scenario_title
from .model_service import ModelServiceError, attach_store as attach_model_store, export_for_container as export_model_service_for_container, public_settings as public_model_settings, save_settings as save_model_settings, test_connection as test_model_connection
from .vault import ContainerCorrupt, VaultError, WrongPassword

async def language_dependency(request: Request) -> None:
    """把请求语言写进 contextvars。必须用**依赖**而不是中间件：

    Starlette 的 BaseHTTPMiddleware 在独立任务里执行端点，中间件里设的 contextvars
    传不到端点（实测：带 X-Display-Language: en 仍返回中文）。
    """
    messages.set_language(display_language(request.headers.get("x-display-language")))


app = FastAPI(    dependencies=[Depends(language_dependency)],
title="Personal Ontology Governance API", version="3.1.0", docs_url=None, redoc_url=None)
store = RDFStore()
attach_model_store(lambda: store)
# 启动时不存在任何会话：清掉上一次运行遗留的解锁期临时凭证，避免 MCP 读到失效令牌。
SESSION_TOKEN_FILE.unlink(missing_ok=True)
# 智能体走 Unix 套接字 + 进程身份 + 授权清单；令牌文件仅用于显式开启的跨机场景。
agent_gateway.start(BACKEND_PORT)
ID_PREFIXES = {"principals":"principal", "resource-types":"resource", "actions":"action", "authorizations":"authorization"}

# ---------------------------------------------------------------- 凭据与会话
# 设计见 docs/05 §4–§5：登录口令同时用于派生容器密钥；会话令牌只存在内存；
# 磁盘上不保留长期凭证，只在解锁期间写一个临时凭证供 MCP 子进程使用。
DEFAULT_SESSION_TTL_SECONDS = 30 * 60      # 默认空闲 30 分钟自动锁定；0 = 不自动锁定
MAX_BACKOFF_SECONDS = 30
_SESSIONS: dict[str, float] = {}
_FAILURES = {"count": 0, "until": 0.0}
EMPTY_TURTLE = b"@prefix po: <urn:personalontology:ontology#> .\n"

# 高频弱口令精简表 + 规则检测（docs/05 §4.3 规则 1）
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "p@ssw0rd", "123456", "1234567", "12345678",
    "123456789", "1234567890", "qwerty", "qwerty123", "qwertyuiop", "abc123", "111111", "000000",
    "letmein", "welcome", "welcome1", "admin", "admin123", "root", "toor", "iloveyou", "monkey",
    "dragon", "sunshine", "princess", "football", "baseball", "master", "shadow", "superman",
    "michael", "trustno1", "login", "starwars", "whatever", "zaq12wsx", "1qaz2wsx", "asdfghjkl",
    "qazwsx", "1q2w3e4r", "88888888", "666666", "asdf1234", "changeme", "secret", "test1234",
}

_common_cache: set[str] | None = None


def _common_passwords() -> set[str]:
    """高频口令集合：内置精简表 + assets/common-passwords.txt（1 万条，缺文件时自动降级）。"""
    global _common_cache
    if _common_cache is None:
        words = set(_COMMON_PASSWORDS)
        try:
            for line in COMMON_PASSWORDS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
                item = line.strip()
                if item and not item.startswith("#"): words.add(item.lower())
        except OSError:
            pass
        _common_cache = words
    return _common_cache


def _looks_common(password: str) -> bool:
    lowered = password.lower()
    words = _common_passwords()
    if lowered in words: return True
    letters = re.sub(r"[^a-z]", "", lowered)
    if letters and letters in words: return True
    trimmed = lowered.strip("0123456789!@#$%^&*()_+-=.")
    if trimmed and trimmed in words: return True
    if re.fullmatch(r"(.)\1+", password): return True                      # 全同字符
    if re.fullmatch(r"(?:0123|1234|4321|abcd|qwer|asdf|zxcv).*", lowered): return True
    if re.search(r"(password|qwerty|admin|letmein|welcome|iloveyou)", lowered): return True
    if re.fullmatch(r"(?:19|20)\d{2}\d{0,4}", password): return True        # 纯年份/年月日
    return False

def validate_password(password: Any) -> str | None:
    """返回错误说明；None 表示通过。"""
    if not isinstance(password, str) or len(password) < 8:
        return "密码至少 8 个字符。"
    if len(password) > 1024:
        return "密码过长。"
    classes = sum(bool(re.search(pattern, password)) for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if classes < 3:
        return "密码需包含小写字母、大写字母、数字、符号中的至少三类。"
    if _looks_common(password):
        return "这个密码太常见，容易被离线爆破，请换一个。"
    return None

def _prune_sessions() -> None:
    now = time.monotonic()
    for token in [t for t, expiry in _SESSIONS.items() if expiry <= now]:
        _SESSIONS.pop(token, None)

def _settings() -> dict[str, Any]:
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _session_ttl() -> int:
    """空闲锁定时长（秒）。0 表示不自动锁定。"""
    try:
        minutes = int(_settings().get("session_timeout_minutes", DEFAULT_SESSION_TTL_SECONDS // 60))
    except (TypeError, ValueError):
        minutes = DEFAULT_SESSION_TTL_SECONDS // 60
    if minutes <= 0: return 0
    return min(minutes, 24 * 60) * 60


def _save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = _settings()
    current.update(patch)
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = SETTINGS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, SETTINGS_FILE)
    return current


def _session_valid(token: str) -> bool:
    if not token: return False
    expiry = _SESSIONS.get(token)
    if expiry is None or expiry <= time.monotonic():
        _SESSIONS.pop(token, None)
        return False
    ttl = _session_ttl()
    _SESSIONS[token] = float("inf") if ttl == 0 else time.monotonic() + ttl   # 滑动续期
    return True

def _remote_agents_allowed() -> bool:
    """是否允许跨机接入（默认否）。

    默认关闭时磁盘上**不存在**任何可用凭据：本机智能体靠 Unix 套接字 + 进程身份 +
    用户授权（见 agent_access），而令牌文件一旦存在，同机任何进程都能读它并直接调用
    API，绕过智能体授权。跨机（SSH 隧道）场景才需要它，因此必须显式开启。
    """
    return _settings().get("allow_remote_agents") is True


def _write_session_token(token: str) -> None:
    """跨机接入开启时，才写这份供远端经隧道读取的临时凭证；锁定后删除。"""
    if not _remote_agents_allowed():
        SESSION_TOKEN_FILE.unlink(missing_ok=True)
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = SESSION_TOKEN_FILE.with_suffix(".tmp")
    try:
        temp.write_text(token + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, SESSION_TOKEN_FILE)
    except OSError:
        temp.unlink(missing_ok=True)

def _issue_session() -> str:
    _prune_sessions()
    token = secrets.token_urlsafe(32)
    ttl = _session_ttl()
    _SESSIONS[token] = float("inf") if ttl == 0 else time.monotonic() + ttl
    _write_session_token(token)
    return token

def _drop_session(token: str) -> None:
    _SESSIONS.pop(token, None)
    if not _SESSIONS:
        SESSION_TOKEN_FILE.unlink(missing_ok=True)

def _drop_all_sessions(keep: str = "") -> None:
    """丢弃所有会话；keep 指定的令牌（通常来自当前请求）保留。"""
    kept = _SESSIONS.get(keep) if keep else None
    _SESSIONS.clear()
    if kept is not None:
        _SESSIONS[keep] = kept
    SESSION_TOKEN_FILE.unlink(missing_ok=True)

def _failure_wait() -> float:
    return max(0.0, _FAILURES["until"] - time.monotonic())

def _note_failure() -> None:
    _FAILURES["count"] += 1
    delay = min(MAX_BACKOFF_SECONDS, 2 ** (_FAILURES["count"] - 1))
    _FAILURES["until"] = time.monotonic() + delay

def _reset_failures() -> None:
    _FAILURES["count"] = 0
    _FAILURES["until"] = 0.0

def _uninitialized() -> HTTPException:
    return HTTPException(status_code=409, detail={"error": "ontology_uninitialized", "message": "尚未设置登录密码，请先创建。"})

def _login_required(message: str = "本体已锁定，请输入登录密码。") -> HTTPException:
    return HTTPException(status_code=401, detail={"error": "login_required", "message": message}, headers={"WWW-Authenticate": "Bearer"})

async def require_session(request: Request,
                           authorization: str | None = Header(default=None)) -> str:
    """访问认证：控制台会话令牌，或经由智能体网关转发的**进程身份断言**。

    智能体侧没有令牌可偷：网关在 Unix 套接字上由内核确认对端进程身份，按用户授予的
    范围放行，并用仅存在于本进程内存中的密钥签名断言。断言只对 MCP 实际使用的那几个
    端点有效（见 agent_access.scope_for_request），管理类接口一律要求会话。
    """
    if not store.initialized:
        raise _uninitialized()
    identity = verify_agent_assertion(request)
    if identity is not None:
        scope = agent_access.scope_for_request(request.method, request.url.path)
        if scope is None:
            raise HTTPException(status_code=403, detail={"error": "agent_endpoint_forbidden",
                                                         "message": "该接口不向智能体开放；请从控制台操作。"})
        allowed, message = agent_access.authorize(str(identity.get("key", "")), scope)
        if not allowed:
            raise HTTPException(status_code=403, detail={"error": "agent_not_authorized", "message": message})
        return f"agent:{identity.get('key','')}"
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not _session_valid(token):
        raise _login_required()
    return token

def _compile_condition(field: str, operator: str, value: Any) -> tuple[str, dict[str, Any]] | None:
    """把 (字段, 比较方式, 值) 编译成 (constraint_type, constraint_value)。

    数值走 numeric_*，时间点/日期走 temporal_*（判定时按时刻或日期比较），
    无法编译（例如字符串做大小比较且不是时间）返回 None，由调用方决定丢弃或跳过。
    """
    if operator == "exists": return "context_exists", {"key": field}
    if operator == "equals": return "context_equals", {"key": field, "value": value}
    if operator in {"lte", "gte"}:
        if isinstance(value, bool): return None
        if isinstance(value, (int, float)):
            return ("numeric_lte" if operator == "lte" else "numeric_gte"), {"key": field, "value": value}
        if parse_temporal(value) is not None:
            return ("temporal_lte" if operator == "lte" else "temporal_gte"), {"key": field, "value": value}
        return None
    return None


def _compile_rules(scenario_id: str, analysis: dict[str, Any], grantor_id: str, grantee_id: str) -> tuple[list[str], list[dict[str, Any]]]:
    """把 `analysis.policies` 编译成授权规则草稿。

    返回 (规则 ID 列表, 编译说明)。单条条件不合法时只丢弃该条件，不再整条策略作废——
    否则一条写错的比较就会让整条规则消失（用户看到的现象就是"给两条策略只生成一条"）。
    """
    suffix = scenario_id.removeprefix("scene_")
    generated = analysis.get("generated") if isinstance(analysis.get("generated"), dict) else {}
    resource_id = str(generated.get("resource_type_id") or "")
    action_ids = generated.get("action_ids") if isinstance(generated.get("action_ids"), list) else []
    if not resource_id or not action_ids: return [], []
    segmentation = analysis.get("segmentation") if isinstance(analysis.get("segmentation"), dict) else {"mode":"global"}
    if str(segmentation.get("mode", "global")) == "segmented": return [], []
    # 动作名 → 动作 ID：与 confirm 时同一套枚举顺序，便于策略按动作限定。
    resource_ids = generated.get("resource_type_ids")
    if not isinstance(resource_ids, list) or not resource_ids: resource_ids = [resource_id] if resource_id else []
    type_names = [str(x.get("name")) for x in (analysis.get("resource_types") or []) if isinstance(x, dict)]
    name_to_resource = {name: resource_ids[i] for i, name in enumerate(type_names) if i < len(resource_ids) and name}
    action_names = [str(x.get("name")) for x in (analysis.get("actions") or []) if isinstance(x, dict)]
    name_to_action = {name: action_ids[i] for i, name in enumerate(action_names) if i < len(action_ids) and name}
    runtime_names = _runtime_field_names(analysis.get("required_inputs"), segmentation)
    standing_fields = {str(x.get("field")) for x in (segmentation.get("global_preferences") or []) if isinstance(x, dict)}
    scope = analysis.get("scope") if isinstance(analysis.get("scope"), dict) else {"mode":"global"}
    geo_fields = {str(scope.get("dimension") or "destination_city"), "destination_city", "district", "area"}
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ids: list[str] = []
    notes: list[dict[str, Any]] = []
    for index, policy in enumerate((analysis.get("policies") or [])[:50]):
        if not isinstance(policy, dict): continue
        auth_id = f"scene_{suffix}_policy_{index+1}"
        if store.get("authorizations", auth_id):
            ids.append(auth_id)
            continue
        raw_conditions = policy.get("conditions", [])
        if not isinstance(raw_conditions, list): raw_conditions = [raw_conditions]
        valid: list[tuple[int, dict[str, Any], str, str, tuple[str, dict[str, Any]]]] = []
        dropped: list[str] = []
        for cindex, condition in enumerate(raw_conditions):
            if not isinstance(condition, dict):
                dropped.append(f"第 {cindex+1} 条不是有效条件"); continue
            operator = condition.get("operator")
            field = str(condition.get("field", ""))[:100]
            if scope.get("mode", "global") == "global" and field in geo_fields: continue
            if not field:
                dropped.append(f"第 {cindex+1} 条缺少字段名"); continue
            if operator not in {"equals","lte","gte","exists"}:
                dropped.append(f"{field}：不支持的比较方式 {operator!r}"); continue
            # 每次执行才确定的字段：默认只要求"提供"（不能固定成某次的值）。
            # 但如果它同时被声明为长期偏好（第三档"两者兼有"），立场条件必须保留。
            if field in runtime_names and field not in standing_fields and operator != "exists":
                operator = "exists"
            compiled_condition = _compile_condition(field, operator, condition.get("value"))
            if compiled_condition is None:
                dropped.append(f"{field}：{operator} 无法比较 {condition.get('value')!r}（既不是数值也不是时间）"); continue
            valid.append((cindex, condition, field, operator, compiled_condition))
        if raw_conditions and not valid:
            notes.append({"policy": index+1, "reason": "全部条件都无法编译，已跳过该规则", "dropped": dropped})
            continue
        # 一条"无条件的拒绝"会否决该场景的全部动作（deny 优先级最高）。场景里还有别的
        # 策略时，这几乎总是模型想表达"某个动作不允许"却写错了地方——跳过并明确报出。
        if str(policy.get("effect")) == "deny" and not valid and len(analysis.get("policies") or []) > 1:
            notes.append({"policy": index+1,
                          "reason": "无条件的拒绝会否决该场景的全部动作，已跳过；请为这条拒绝指定具体动作或条件",
                          "dropped": dropped})
            continue
        if dropped:
            notes.append({"policy": index+1, "reason": "部分条件无法编译，已忽略这些条件", "dropped": dropped})
        constraint_ids: list[str] = []
        for cindex, condition, field, operator, (constraint_type, value) in valid:
            constraint_id = f"scene_{suffix}_policy_{index+1}_condition_{cindex+1}"
            if not store.get("constraints", constraint_id):
                store.put("constraints", constraint_id, {"constraint_type":constraint_type,"constraint_value":value}, create_only=True)
            constraint_ids.append(constraint_id)
        # 策略可声明适用动作；未声明或名字对不上时回退到该场景的全部动作。
        policy_actions = policy.get("actions")
        if isinstance(policy_actions, str): policy_actions = [policy_actions]
        scoped_actions = action_ids
        if isinstance(policy_actions, list) and policy_actions:
            mapped = [name_to_action[str(n)] for n in policy_actions if str(n) in name_to_action]
            if mapped:
                scoped_actions = list(dict.fromkeys(mapped))
            else:
                notes.append({"policy": index+1, "reason": f"策略声明的动作 {policy_actions} 无法匹配该场景的动作，已按全部动作处理", "dropped": []})
        # 策略声明的 resource 决定这条规则挂在哪个资源类型上；缺失或对不上时用第一个。
        rule_resource = name_to_resource.get(str(policy.get("resource") or ""), resource_id)
        store.put("authorizations", auth_id, {
            "grantor_id":grantor_id, "grantee_id":grantee_id, "resource_type_id":rule_resource,
            "resource_pattern":"*", "pattern_type":"glob", "actions":scoped_actions,
            "effect":policy.get("effect") if policy.get("effect") in {"allow","deny","ask"} else "ask",
            "priority":0, "constraints":constraint_ids, "source":f"scenario-slice:{scenario_id}",
            "term":"permanent", "revoked":False, "created_at":created_at, "policy_status":"draft"}, create_only=True)
        ids.append(auth_id)
    return ids, notes


def _normalize_segmentation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"mode":"global", "dimensions":[], "global_preferences":[], "variants":[]}
    mode = raw.get("mode", "global")
    if mode not in {"global", "segmented"}:
        raise HTTPException(status_code=422, detail=messages.detail("pref_scope_invalid"))
    def preferences(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or len(value) > 100:
            raise HTTPException(status_code=422, detail=messages.detail("pref_list_invalid"))
        result = []
        for item in value:
            if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(item.get("field", ""))) or not str(item.get("label", "")).strip() or not isinstance(item.get("value"), (str, int, float, bool)):
                raise HTTPException(status_code=422, detail=messages.detail("pref_item_incomplete"))
            operator = item.get("operator", "equals")
            # 值不是数值时，大小比较没有意义：退化为等值比较，而不是拒绝整次确认。
            # （真实案例：布尔型偏好被带上 lte/gte，导致"确认并创建场景实例"整体失败。）
            if operator in {"lte", "gte"} and (isinstance(item["value"], bool) or not isinstance(item["value"], (int, float))):
                operator = "equals"
            if operator not in {"equals", "lte", "gte", "exists"}:
                raise HTTPException(status_code=422,
                    detail=messages.detail("pref_operator_invalid", field=item.get("field"), operator=operator))
            result.append({"field":item["field"],"label":str(item["label"]).strip()[:160],"type":item.get("type", "string"),"value":item["value"],"operator":operator,"strength":item.get("strength", "must")})
        return result
    if mode == "global":
        return {"mode":"global", "dimensions":[], "global_preferences":preferences(raw.get("global_preferences", [])), "variants":[]}
    dimensions = raw.get("dimensions")
    variants = raw.get("variants")
    if not isinstance(dimensions, list) or not dimensions or len(dimensions) > 10 or not isinstance(variants, list) or not variants or len(variants) > 100:
        raise HTTPException(status_code=422, detail=messages.detail("seg_needs_dimension"))
    clean_dimensions = []
    seen = set()
    for item in dimensions:
        if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(item.get("field", ""))) or not str(item.get("label", "")).strip():
            raise HTTPException(status_code=422, detail=messages.detail("dimension_needs_field"))
        if item["field"] in seen: raise HTTPException(status_code=422, detail=messages.detail("dimension_duplicate"))
        seen.add(item["field"])
        clean_dimensions.append({"field":item["field"],"label":str(item["label"]).strip()[:160],"type":item.get("type", "string")})
    clean_variants = []
    for index, item in enumerate(variants):
        if not isinstance(item, dict) or not isinstance(item.get("values"), dict):
            raise HTTPException(status_code=422, detail=messages.detail("variant_needs_values"))
        values = {dimension["field"]:item["values"].get(dimension["field"]) for dimension in clean_dimensions}
        if any(value in (None, "") or not isinstance(value, (str, int, float, bool)) for value in values.values()):
            raise HTTPException(status_code=422, detail=messages.detail("variant_needs_all_values"))
        clean_variants.append({"id":str(item.get("id") or f"variant_{index+1}")[:100],"values":values,"preferences":preferences(item.get("preferences", []))})
    return {"mode":"segmented", "dimensions":clean_dimensions,"global_preferences":preferences(raw.get("global_preferences", [])),"variants":clean_variants}

def _origin_allowed(origin: str, request: Any) -> bool:
    """兼容包装：真正的判定在 backend/origin_policy.py（管理器与后端共用）。"""
    return origin_allowed(origin, getattr(request, "headers", None), config.ALLOWED_ORIGINS)





@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """按请求语言解析消息键。

    语言必须在**这里**取，因为异常处理器能拿到 request；在中间件或依赖里设置
    contextvars 都传不到端点（实测无效）。
    """
    language = display_language(request.headers.get("x-display-language"))
    detail = exc.detail
    if isinstance(detail, dict) and "message_key" in detail:
        detail = {"error": detail.get("error"), "message": messages.msg_for(detail["message_key"], language, **detail.get("kwargs", {}))}
        if detail["error"] is None:
            detail = detail["message"]
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.middleware("http")
async def no_cache_and_local_origin(request: Request, call_next):
    messages.set_language(display_language(request.headers.get("x-display-language")))
    origin = request.headers.get("origin")
    if origin and not _origin_allowed(origin, request):
        return JSONResponse({"detail":"Origin not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response

@app.exception_handler(ValidationError)
async def validation_error_handler(_: Request, exc: ValidationError):
    return JSONResponse({"error":"shacl_validation_failed", "report":exc.report}, status_code=422)

@app.exception_handler(StoreLocked)
async def store_locked_handler(_: Request, exc: StoreLocked):
    return JSONResponse({"error":"login_required", "message":str(exc)}, status_code=401, headers={"WWW-Authenticate":"Bearer"})

@app.exception_handler(StoreError)
async def store_error_handler(_: Request, exc: StoreError):
    return JSONResponse({"error":"invalid_operation", "detail":str(exc)}, status_code=409)

@app.exception_handler(KeyError)
async def not_found_collection_handler(_: Request, exc: KeyError):
    return JSONResponse({"error":"unknown_collection", "collection":str(exc.args[0])}, status_code=404)

@app.get("/health")
async def health():
    return {"status":"ok", "service":"personal-ontology", "version":"3.1.0",
            "initialized": store.initialized, "locked": not store.unlocked,
            "display_language": stored_language()}

@app.post("/v1/setup")
async def setup(body: dict[str, Any]):
    """首次设置登录密码：创建容器（或在检测到明文图时迁移）。"""
    if store.initialized:
        raise HTTPException(status_code=409, detail={"error":"already_initialized","message":"本体容器已存在。"})
    password = body.get("password")
    problem = validate_password(password)
    if problem: raise HTTPException(status_code=422, detail=problem)

    migrated = False
    ontology = EMPTY_TURTLE
    if store.has_legacy_plaintext:
        try:
            ontology = store.legacy_file.read_bytes()
        except OSError as exc:
            raise HTTPException(status_code=500, detail=messages.detail("ontology_read_failed", error=str(exc))) from exc
        migrated = True
    model_service = export_model_service_for_container()

    try:
        store.initialize(str(password), ontology, model_service)
    except VaultError as exc:
        raise HTTPException(status_code=500, detail=messages.detail("container_create_failed", error=str(exc))) from exc

    report = {"token": _issue_session(), "migrated": migrated, "revision": store.revision}
    report["verification"] = _verify_and_cleanup_legacy(ontology if migrated else None)
    snapshots = await asyncio.to_thread(_local_snapshots)
    report["local_snapshots"] = snapshots
    if snapshots and migrated:
        report["verification"]["snapshot_warning"] = (
            f"检测到 {len(snapshots)} 个 APFS 本地快照，其中可能仍留有迁移前的明文副本。"
            "建议删除：sudo tmutil deletelocalsnapshots /")
    return report

@app.post("/v1/login")
async def login(body: dict[str, Any]):
    if not store.initialized: raise _uninitialized()
    waiting = _failure_wait()
    if waiting > 0:
        raise HTTPException(status_code=429, detail=messages.detail("too_many_attempts", seconds=int(waiting) + 1))
    password = body.get("password")
    if not isinstance(password, str) or not password:
        raise HTTPException(status_code=422, detail=messages.detail("login_password_required"))
    try:
        store.unlock(password)
    except WrongPassword:
        _note_failure()
        raise _login_required("密码不正确。")
    except (ContainerCorrupt, VaultError) as exc:
        raise HTTPException(status_code=500, detail=messages.detail("container_read_failed", error=str(exc))) from exc
    _reset_failures()
    return {"token": _issue_session(), "initialized": True, "locked": False}

@app.post("/v1/logout")
async def logout(token: str = Depends(require_session)):
    _drop_session(token)
    return {"ok": True, "locked": not store.unlocked}

@app.post("/v1/lock")
async def lock_everything(token: str = Depends(require_session)):
    """丢弃内存中的密钥与图，并结束所有会话。"""
    del token
    store.lock()
    _drop_all_sessions()
    return {"ok": True, "locked": True}

@app.put("/v1/account/password")
async def change_password(body: dict[str, Any], token: str = Depends(require_session)):
    del token
    current, new = body.get("current"), body.get("new")
    if not isinstance(current, str) or not current:
        raise HTTPException(status_code=422, detail=messages.detail("current_password_required"))
    problem = validate_password(new)
    if problem: raise HTTPException(status_code=422, detail=problem)
    if current == new:
        raise HTTPException(status_code=422, detail=messages.detail("password_unchanged"))
    try:
        store.change_password(current, str(new))
    except WrongPassword:
        _note_failure()
        raise _login_required("当前密码不正确。")
    except VaultError as exc:
        raise HTTPException(status_code=500, detail=messages.detail("password_change_failed", error=str(exc))) from exc
    _reset_failures()
    _drop_all_sessions()          # 所有会话（含其他设备与 MCP）失效
    return {"ok": True, "message": "密码已更新，请用新密码重新登录。"}

@app.get("/v1/account", dependencies=[Depends(require_session)])
async def account_status():
    info = store.status()
    info["sessions"] = len(_SESSIONS)
    info["session_ttl_seconds"] = _session_ttl()
    info["session_timeout_minutes"] = _session_ttl() // 60 if _session_ttl() else 0
    info["local_snapshots"] = await asyncio.to_thread(_local_snapshots)
    return info


def verify_agent_assertion(request: Request) -> dict[str, Any] | None:
    """校验智能体网关注入的签名断言；伪造的断言（直接打回环端口）一律无效。"""
    payload = request.headers.get(agent_gateway.ASSERTION_HEADER) or ""
    signature = request.headers.get(agent_gateway.SIGNATURE_HEADER) or ""
    return agent_gateway.verify_assertion(agent_gateway.ASSERTION_SECRET, payload, signature)


@app.get("/v1/settings/remote-agents", dependencies=[Depends(require_session)])
async def get_remote_agents():
    """跨机接入开关。开启后会在 data/ 写入可供远端经隧道读取的会话令牌。"""
    return {"allow_remote_agents": _remote_agents_allowed(), "token_present": SESSION_TOKEN_FILE.exists()}


@app.put("/v1/settings/remote-agents")
async def set_remote_agents(body: dict[str, Any], token: str = Depends(require_session)):
    allow = body.get("allow_remote_agents") is True
    _save_settings({"allow_remote_agents": allow})
    if allow:
        _write_session_token(token)
    else:
        SESSION_TOKEN_FILE.unlink(missing_ok=True)
        _drop_all_sessions(keep=token)   # 令牌文件已删；保留调用者会话，不让开关把人踢下线
    return {"ok": True, "allow_remote_agents": allow, "token_present": SESSION_TOKEN_FILE.exists()}


@app.get("/v1/agents", dependencies=[Depends(require_session)])
async def list_agents(request: Request):
    """本机程序的访问清单：等待批准、已批准（含范围）、已拒绝。"""
    return {**agent_access.clients(), "scopes": _scopes_for(display_language(request.headers.get("x-display-language"))),
            "default_scopes": list(agent_access.DEFAULT_SCOPES)}


@app.post("/v1/agents/{key}/approve", dependencies=[Depends(require_session)])
async def approve_agent(key: str, body: dict[str, Any]):
    scopes = body.get("scopes")
    if scopes is not None and (not isinstance(scopes, list) or any(s not in agent_access.SCOPES for s in scopes)):
        raise HTTPException(status_code=422, detail=messages.detail("scopes_invalid"))
    try:
        record = agent_access.approve(key, [str(s) for s in scopes] if scopes else None)
    except KeyError:
        raise HTTPException(status_code=404, detail=messages.detail("client_not_listed"))
    return {"ok": True, "client": record}


@app.post("/v1/agents/{key}/deny", dependencies=[Depends(require_session)])
async def deny_agent(key: str):
    try:
        record = agent_access.deny(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=messages.detail("client_not_listed"))
    return {"ok": True, "client": record}


@app.post("/v1/agents/{key}/revoke", dependencies=[Depends(require_session)])
async def revoke_agent(key: str):
    try:
        record = agent_access.revoke(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=messages.detail("client_not_listed"))
    return {"ok": True, "client": record}


@app.delete("/v1/agents/{key}", status_code=204, dependencies=[Depends(require_session)])
async def forget_agent(key: str):
    agent_access.forget(key)


@app.get("/v1/settings/language", dependencies=[Depends(require_session)])
async def get_language_setting(request: Request):
    stored = stored_language()
    return {"language": display_language(request.headers.get("x-display-language")),
            "configured": stored is not None, "stored": stored,
            "supported": list(SUPPORTED_LANGUAGES)}


@app.put("/v1/settings/language")
async def set_language_setting(body: dict[str, Any], token: str = Depends(require_session)):
    """展示与产出语言（zh / en）：影响模型产出的字段标签，以及界面取用的名称字段。"""
    del token
    language = str(body.get("language") or "").strip().lower()
    if language == "auto":
        # 清空显式设置，回到"跟随系统语言"
        _save_settings({"display_language": ""})
        return {"ok": True, "language": display_language(), "configured": False}
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=messages.detail("language_invalid"))
    _save_settings({"display_language": language})
    return {"ok": True, "language": language, "configured": True}


@app.put("/v1/account/session-timeout")
async def set_session_timeout(body: dict[str, Any], token: str = Depends(require_session)):
    """空闲多久自动锁定。0 表示不自动锁定（不推荐）。"""
    del token
    try:
        minutes = int(body.get("minutes"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=messages.detail("minutes_range"))
    if not 0 <= minutes <= 24 * 60:
        raise HTTPException(status_code=422, detail=messages.detail("minutes_range"))
    _save_settings({"session_timeout_minutes": minutes})
    ttl = _session_ttl()
    for key, expiry in list(_SESSIONS.items()):
        _SESSIONS[key] = float("inf") if ttl == 0 else min(expiry, time.monotonic() + ttl)
    return {"ok": True, "session_timeout_minutes": minutes, "session_ttl_seconds": ttl}


def _local_snapshots() -> list[str]:
    """列出 APFS 本地快照——迁移后旧明文可能仍留在其中（docs/05 §7.3）。"""
    if sys.platform != "darwin": return []
    try:
        result = subprocess.run(["tmutil", "listlocalsnapshots", "/"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    names = []
    for line in (result.stdout or "").splitlines():
        item = line.strip()
        if item.startswith("com.apple.TimeMachine"): names.append(item)
    return names[:50]

def _verify_and_cleanup_legacy(original: bytes | None) -> dict[str, Any]:
    """迁移验收并清理明文。

    有旧图时必须先确认"迁移前的每一条三元组都能在解密后的图中找到"（缺一条就整体放弃清理）；
    没有旧图时（全新安装）只清理已并入容器的模型配置与旧令牌。
    """
    from rdflib import Graph
    added_builtins = 0
    triple_count = 0
    if original is not None:
        expected = Graph()
        expected.parse(data=original.decode("utf-8"), format="turtle")
        actual = Graph()
        actual.parse(data=store.vault.get_section("ontology").decode("utf-8"), format="turtle")
        expected_set, actual_set = set(expected), set(actual)
        missing = expected_set - actual_set
        if missing:
            return {"ok": False, "expected_triples": len(expected_set), "actual_triples": len(actual_set),
                    "missing": len(missing), "message": "迁移校验失败：解密后的图缺少原有数据，已保留明文文件。"}
        triple_count = len(expected_set)
        added_builtins = len(actual_set) - len(expected_set)
    removed: list[str] = []
    for path in [store.legacy_file, TOKEN_FILE, MODEL_CONFIG_FILE, MODEL_KEY_FILE, DATA_DIR / "contact.key"]:
        try:
            if path.exists():
                path.unlink()
                removed.append(path.name)
        except OSError:
            pass
    for leftover in sorted(DATA_DIR.glob("ontology-*.ttl")):
        try:
            leftover.unlink()
            removed.append(leftover.name)
        except OSError:
            pass
    return {"ok": True, "triples": triple_count, "added_builtins": added_builtins, "removed_plaintext": removed,
            "message": "已迁移并清理明文文件。" if original is not None else "已清理旧配置与令牌。"}


@app.get("/")
async def home():
    """控制台只由服务管理器提供；从后端端口打开时跳到管理器。

    后端此前也返回 index.html，于是 8766 看起来和 8765 一样，但那边的「服务监控」「智能体接入」
    会 404——`/manager/*` 只存在于管理器。这里改为跳转，避免"看起来能用、其实半坏"的重复入口。
    """
    return RedirectResponse(f"http://127.0.0.1:{MANAGER_PORT}/", status_code=307)

@app.get("/v1/collections", dependencies=[Depends(require_session)])
async def collections():
    return {"collections":sorted(CLASSES)}

@app.get("/v1/settings/model-service", dependencies=[Depends(require_session)])
async def get_model_service_settings():
    try: return public_model_settings()
    except ModelServiceError as exc: raise HTTPException(status_code=500, detail=str(exc))

@app.put("/v1/settings/model-service", dependencies=[Depends(require_session)])
async def put_model_service_settings(body: dict[str, Any]):
    try:
        return save_model_settings(str(body.get("base_url", "")), str(body.get("model", "")), str(body.get("api_key", "")), bool(body.get("clear_api_key", False)))
    except ModelServiceError as exc: raise HTTPException(status_code=422, detail=str(exc))

@app.post("/v1/settings/model-service/test", dependencies=[Depends(require_session)])
async def test_model_service_settings():
    try: return test_model_connection()
    except ModelServiceError as exc: raise HTTPException(status_code=422, detail=str(exc))

@app.get("/v1/scenario-slices/provider", dependencies=[Depends(require_session)])
async def scenario_provider_status():
    return {"configured":scenario_provider_configured()}

@app.post("/v1/scenario-slices/analyze", dependencies=[Depends(require_session)])
async def analyze_scene(body: dict[str, Any], request: Request):
    text = str(body.get("text", "")).strip()
    if not text or len(text) > 10000:
        raise HTTPException(status_code=422, detail=messages.detail("scene_text_required"))
    scenario_id = str(body.get("scenario_id") or f"scene_{uuid4().hex[:12]}")
    if not re.fullmatch(r"scene_[A-Za-z0-9_-]{1,70}", scenario_id):
        raise HTTPException(status_code=422, detail=messages.detail("scene_id_invalid"))
    prior = store.get("scenario-slices", scenario_id)
    if body.get("scenario_id") and not prior:
        raise HTTPException(status_code=404, detail=messages.detail("scene_missing"))
    answers = body.get("answers", [])
    if not isinstance(answers, list) or len(answers) > 100 or any(not isinstance(a, dict) for a in answers):
        raise HTTPException(status_code=422, detail=messages.detail("answers_invalid"))
    if any(not isinstance(a.get("question", ""), str) or not isinstance(a.get("answer", ""), str) or len(a.get("question", "")) > 2000 or len(a.get("answer", "")) > 2000 for a in answers):
        raise HTTPException(status_code=422, detail=messages.detail("answer_too_long"))
    try:
        catalog = {
            "resource_types":[{"id":x["id"],"name":x.get("display_name_zh") or x["id"],"description":x.get("description_zh","")} for x in store.list("resource-types")[:200]],
            "actions":[{"id":x["id"],"name":x.get("display_name_zh") or x["id"],"resource_type_id":x.get("applies_to")} for x in store.list("actions")[:300]],
        }
        # 语言优先级：用户设置 → 浏览器/系统语言（请求头）→ 中文
        analysis = analyze_scenario(text, (prior or {}).get("analysis"), answers, catalog,
                                    display_language(request.headers.get("x-display-language")))
        title_override = body.get("title_override")
        previous_analysis = (prior or {}).get("analysis", {})
        if isinstance(title_override, str) and title_override.strip():
            analysis["title"] = title_override.strip()[:160]
            analysis["title_user_modified"] = True
        elif isinstance(previous_analysis, dict) and previous_analysis.get("title_user_modified"):
            analysis["title"] = str(previous_analysis.get("title", analysis.get("title", "场景实例")))[:160]
            analysis["title_user_modified"] = True
        previous_generated = ((prior or {}).get("analysis") or {}).get("generated") if isinstance((prior or {}).get("analysis"), dict) else None
        if isinstance(previous_generated, dict) and previous_generated and not isinstance(analysis.get("generated"), dict):
            # 重新分析不能丢掉上一版已创建对象的归属，否则它们会成为无法管理的孤儿。
            analysis["generated"] = previous_generated
        record = {"original_text":text, "status":"analyzed", "analysis":analysis, "updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        stored = store.put("scenario-slices", scenario_id, record, create_only=prior is None)
        return {"scenario":stored}
    except FileExistsError:
        raise HTTPException(status_code=409, detail=messages.detail("scene_exists"))
    except ScenarioProviderError as exc:
        raise HTTPException(status_code=503, detail={"error":"scenario_provider_unavailable", "message":str(exc)})

@app.post("/v1/scenario-slices/confirm", dependencies=[Depends(require_session)])
async def confirm_scene(body: dict[str, Any]):
    scenario_id = str(body.get("scenario_id", ""))
    scene = store.get("scenario-slices", scenario_id) if scenario_id else None
    if not scene or not isinstance(scene.get("analysis"), dict):
        raise HTTPException(status_code=404, detail=messages.detail("scene_not_analyzed"))
    analysis = scene["analysis"]
    requested_title = body.get("title")
    if requested_title is not None:
        if not isinstance(requested_title, str) or not requested_title.strip() or len(requested_title.strip()) > 160:
            raise HTTPException(status_code=422, detail=messages.detail("scene_title_too_long"))
        analysis["title"] = requested_title.strip()
        analysis["title_user_modified"] = True
    elif not analysis.get("title_user_modified"):
        analysis["title"] = generic_scenario_title(str(scene.get("original_text", "")), analysis)
    scope = analysis.get("scope") if isinstance(analysis.get("scope"), dict) else {"mode":"global", "dimension":"destination_city"}
    if not analysis.get("required_inputs") and any(word in scene.get("original_text", "") for word in ("酒店", "旅馆", "宾馆")):
        analysis["required_inputs"] = [
            {"name":"destination_city","label":"目的城市","type":"string","required":True,"help":"例如：武汉"},
            {"name":"check_in_date","label":"入住日期","type":"date","required":True,"help":"例如：2026-11-12"},
            {"name":"check_out_date","label":"退房日期","type":"date","required":True,"help":"例如：2026-11-15"},
            {"name":"guest_count","label":"入住人数","type":"number","required":True,"help":"例如：2"},
        ]
    geo_fields = {str(scope.get("dimension") or "destination_city"), "destination_city", "district", "area"}
    made = analysis.get("generated", {})
    if made.get("resource_type_id"):
        return {"scenario":scene, "generated":made, "already_confirmed":True}
    types = analysis.get("resource_types", [])
    actions = analysis.get("actions", [])
    if not types or not actions:
        raise HTTPException(status_code=422, detail=messages.detail("scene_needs_resources"))
    # Runtime inputs describe what an agent should collect on each execution.
    # They are optional metadata for the template and must not block creating it.
    required_inputs = analysis.get("required_inputs", [])
    if not isinstance(required_inputs, list):
        required_inputs = []
    required_inputs = [x for x in required_inputs if isinstance(x, dict) and str(x.get("name", "")).strip()]
    segmentation_input = body.get("segmentation")
    if segmentation_input is None:
        # Backward-compatible confirmation for existing clients: treat facts
        # from the user as reusable global preferences, excluding request context.
        legacy_preferences = []
        for fact in analysis.get("facts", []):
            if not isinstance(fact, dict) or not fact.get("name") or fact.get("source") == "suggestion": continue
            field = {"min_price":"price_min", "max_price":"price_max"}.get(str(fact["name"]), str(fact["name"]))
            if field in {"destination_city", "district", "area"}: continue
            legacy_preferences.append({"field":field,"label":str(fact.get("label") or field),"type":fact.get("type") or type(fact.get("value")).__name__,"value":fact.get("value"),"operator":"lte" if field.endswith(("_max", "_upper")) or field in {"max_price", "budget_max"} else "gte" if field.endswith(("_min", "_lower")) or field in {"min_price", "budget_min"} else "equals","strength":"must"})
        segmentation_input = {"mode":"global", "global_preferences":legacy_preferences}
    segmentation = _normalize_segmentation(segmentation_input)
    if segmentation["mode"] == "segmented":
        by_name = {x.get("name"):x for x in required_inputs}
        for dimension in segmentation["dimensions"]:
            if dimension["field"] not in by_name:
                required_inputs.append({"name":dimension["field"],"label":dimension["label"],"type":dimension.get("type", "string"),"required":True,"help":"用于匹配适用的场景偏好分组。"})
    analysis["required_inputs"] = required_inputs
    runtime_names = _runtime_field_names(required_inputs, segmentation)
    segmentation["global_preferences"] = _prune_preferences(segmentation.get("global_preferences"), runtime_names)
    for variant in segmentation.get("variants") or []:
        if isinstance(variant, dict): variant["preferences"] = _prune_preferences(variant.get("preferences"), runtime_names)
    analysis["segmentation"] = segmentation
    analysis["segmentation_schema_version"] = 1
    analysis["segmentation"] = segmentation
    analysis["scope"] = {"mode":"global"} if segmentation["mode"] == "global" else {"mode":"segmented"}
    principal_ids = (body.get("grantor_id"), body.get("grantee_id"))
    if any(not store.get("principals", str(pid)) for pid in principal_ids if pid):
        raise HTTPException(status_code=422, detail=messages.detail("principal_invalid"))
    suffix = scenario_id.removeprefix("scene_")
    # 一个场景可以处理多个资源类型（例如"文件"与"目录"）。此前只落地 types[0]，其余被静默
    # 丢弃——推演中发现"目录"就这样消失了。现在逐一落地，规则再按策略声明的资源类型各归其位。
    entries = [x for x in types if isinstance(x, dict)] or [{"name": "场景资源"}]
    resource_ids: list[str] = []
    created_resource_ids: list[str] = []
    for index, item in enumerate(entries[:10]):
        existing = str(item.get("existing_id") or "")
        rid = existing if existing and store.get("resource-types", existing) else (
            f"scene_{suffix}_resource" if index == 0 else f"scene_{suffix}_resource_{index+1}")
        if not store.get("resource-types", rid):
            resource_name = str(item.get("name") or f"场景资源 {index+1}")[:160]
            store.put("resource-types", rid, {"type_name":rid,"display_name_zh":resource_name,"display_name_en":resource_name,
                     "description_zh":str(item.get("description") or "由场景切片生成，后续可编辑"),
                     "matcher_id":"glob","default_priority":0,"is_builtin":False}, create_only=True)
            created_resource_ids.append(rid)
        resource_ids.append(rid)
    resource_id = resource_ids[0]
    created_resource_type = resource_id in created_resource_ids
    action_ids = []
    created_action_ids = []
    for index, item in enumerate(actions[:50]):
        existing_id = str(item.get("existing_id") or "")
        action_id = existing_id if existing_id and store.get("actions", existing_id) else f"scene_{suffix}_action_{index+1}"
        if not store.get("actions", action_id):
            name = str(item.get("name") or f"场景动作 {index+1}")[:160]
            risk = item.get("risk") if item.get("risk") in {"low","medium","high","critical"} else "medium"
            store.put("actions", action_id, {"action_id":action_id,"display_name_zh":name,"display_name_en":name,"applies_to":resource_id,"risk_level":risk,"description_zh":str(item.get("description") or "由场景切片生成")}, create_only=True)
            created_action_ids.append(action_id)
        action_ids.append(action_id)
    resource = store.get("resource-types", resource_id) or {}
    # Runtime inputs are definitions in the metamodel (ParamDefinition), while
    # values such as a city belong to each invocation of this reusable scene.
    params = []
    created_param_ids = []
    raw_inputs = analysis.get("required_inputs", [])
    if not isinstance(raw_inputs, list): raw_inputs = []
    for item in raw_inputs[:80]:
        if not isinstance(item, dict): continue
        name = re.sub(r"[^A-Za-z0-9_-]", "_", str(item.get("name", "")).strip())[:100]
        if not name: continue
        param_id = f"scene_{suffix}_{name}"
        if not store.get("params", param_id):
            label = str(item.get("label") or name)[:160]
            param_type = "bool" if item.get("type") == "boolean" else str(item.get("type") or "string")
            if param_type not in {"string", "number", "bool", "date"}: param_type = "string"
            store.put("params", param_id, {"param_id":param_id,"param_name":name,"param_type":param_type,"display_name_zh":label,"display_name_en":label,"required":bool(item.get("required", False))}, create_only=True)
            created_param_ids.append(param_id)
        params.append(param_id)
    resource["params"] = sorted(set([*(resource.get("params", []) if isinstance(resource.get("params"), list) else ([resource["params"]] if resource.get("params") else [])), *params]))
    resource["actions"] = sorted(set([*(resource.get("actions", []) if isinstance(resource.get("actions"), list) else ([resource["actions"]] if resource.get("actions") else [])), *action_ids]))
    store.put("resource-types", resource_id, {k:v for k,v in resource.items() if k not in {"id","type_name"}})
    made = {"resource_type_id":resource_id,"resource_type_ids":resource_ids,"action_ids":action_ids,
            "created_resource_type":created_resource_type,"created_resource_type_ids":created_resource_ids,
            "created_action_ids":created_action_ids,"created_param_ids":created_param_ids,"authorization_ids":[]}
    analysis["generated"] = made
    if body.get("grantor_id") and body.get("grantee_id") and segmentation["mode"] == "global":
        compiled, compile_notes = _compile_rules(scenario_id, analysis, str(body["grantor_id"]), str(body["grantee_id"]))
        made["authorization_ids"] = compiled
    analysis["instance_preferences"] = segmentation["global_preferences"] if segmentation["mode"] == "global" else []
    analysis["generated"] = made
    stored = store.put("scenario-slices", scenario_id, {"original_text":scene["original_text"],"status":"confirmed","analysis":analysis,"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")})
    return {"scenario":stored,"generated":made,"already_confirmed":False,"compile_report":compile_notes if body.get("grantor_id") and body.get("grantee_id") else []}

@app.post("/v1/scenario-slices/{scenario_id}/compile", dependencies=[Depends(require_session)])
async def compile_scenario_rules(scenario_id: str, body: dict[str, Any]):
    """为已确认但还没有授权规则的场景补生成规则（确认时未选主体的情况）。"""
    scene = store.get("scenario-slices", scenario_id)
    if not scene or scene.get("status") != "confirmed":
        raise HTTPException(status_code=404, detail=messages.detail("confirm_before_compile"))
    analysis = scene.get("analysis") if isinstance(scene.get("analysis"), dict) else {}
    generated = analysis.get("generated") if isinstance(analysis.get("generated"), dict) else {}
    if not generated.get("resource_type_id") or not generated.get("action_ids"):
        raise HTTPException(status_code=422, detail=messages.detail("scene_no_resources_actions"))
    if not (analysis.get("policies") or []):
        raise HTTPException(status_code=422, detail=messages.detail("no_policy_drafts"))
    grantor_id = str(body.get("grantor_id") or "")
    grantee_id = str(body.get("grantee_id") or grantor_id)
    if not grantor_id: raise HTTPException(status_code=422, detail=messages.detail("rule_grantee_required"))
    if not store.get("principals", grantor_id): raise HTTPException(status_code=422, detail=messages.detail("grantor_missing"))
    if not store.get("principals", grantee_id): raise HTTPException(status_code=422, detail=messages.detail("grantee_missing"))
    existing = [str(x) for x in (generated.get("authorization_ids") or []) if store.get("authorizations", str(x))]
    created, compile_notes = _compile_rules(scenario_id, analysis, grantor_id, grantee_id)
    merged = sorted(set(existing) | set(created))
    if not merged: raise HTTPException(status_code=422, detail=messages.detail("no_rules_to_create"))
    generated["authorization_ids"] = merged
    analysis["generated"] = generated
    scene["analysis"] = analysis
    scene["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    stored = store.put("scenario-slices", scenario_id, {k:v for k,v in scene.items() if k not in {"id", "scenario_id"}})
    return {"scenario": stored, "created": created, "authorization_ids": merged, "compile_report": compile_notes}


@app.delete("/v1/scenario-slices/{scenario_id}", status_code=204, dependencies=[Depends(require_session)])
async def delete_scenario_instance(scenario_id: str):
    scene = store.get("scenario-slices", scenario_id)
    if not scene: raise HTTPException(status_code=404, detail=messages.detail("instance_missing"))
    made = (scene.get("analysis") or {}).get("generated", {})
    # Remove only objects created by this scene. Shared/pre-existing catalog
    # entries are retained, and StoreError protects anything still referenced.
    # 除了记录里的 authorization_ids，还按 source 兜底——重新分析会丢失归属信息。
    targets = {str(x) for x in (made.get("authorization_ids") or [])}
    targets |= {str(a["id"]) for a in store.list("authorizations") if str(a.get("source")) == f"scenario-slice:{scenario_id}"}
    for auth_id in sorted(targets):
        auth = store.get("authorizations", auth_id)
        if auth:
            constraint_ids = auth.get("constraints", [])
            try: store.delete("authorizations", auth_id)
            except StoreError: continue
            for constraint_id in constraint_ids:
                try: store.delete("constraints", constraint_id)
                except StoreError: pass
    for param_id in made.get("created_param_ids", []):
        try: store.delete("params", param_id)
        except StoreError: pass
    for action_id in made.get("created_action_ids", []):
        try: store.delete("actions", action_id)
        except StoreError: pass
    for created_id in (made.get("created_resource_type_ids") or [made.get("resource_type_id")] if made.get("created_resource_type") else []):
        if created_id:
            try: store.delete("resource-types", created_id)
            except StoreError: pass
    try: store.delete("scenario-slices", scenario_id)
    except StoreError as exc: raise HTTPException(status_code=409, detail=str(exc))
    return Response(status_code=204)

@app.patch("/v1/scenario-slices/{scenario_id}/instance", dependencies=[Depends(require_session)])
async def update_scenario_instance(scenario_id: str, body: dict[str, Any]):
    scene = store.get("scenario-slices", scenario_id)
    if not scene: raise HTTPException(status_code=404, detail=messages.detail("instance_missing"))
    analysis = scene.get("analysis") if isinstance(scene.get("analysis"), dict) else {}
    title = str(body.get("title", analysis.get("title", "场景实例"))).strip()[:160]
    scope = body.get("scope", analysis.get("scope", {}))
    if not isinstance(scope, dict) or scope.get("mode", "global") not in {"global", "by_dimension", "segmented"}:
        raise HTTPException(status_code=422, detail=messages.detail("scope_invalid"))
    segmentation = _normalize_segmentation(body.get("segmentation", analysis.get("segmentation")))
    required_inputs = body.get("required_inputs", analysis.get("required_inputs", []))
    if not isinstance(required_inputs, list) or len(required_inputs) > 80:
        raise HTTPException(status_code=422, detail=messages.detail("required_defs_invalid"))
    if segmentation["mode"] == "segmented":
        required_names = {item.get("name") for item in required_inputs if isinstance(item, dict)}
        for dimension in segmentation["dimensions"]:
            if dimension["field"] not in required_names:
                required_inputs.append({"name":dimension["field"],"label":dimension["label"],"type":dimension.get("type", "string"),"required":True,"help":"用于匹配适用的场景偏好分组。"})
    names = set()
    for item in required_inputs:
        if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(item.get("name", ""))) or not str(item.get("label", "")).strip():
            raise HTTPException(status_code=422, detail=messages.detail("required_item_invalid"))
        if item.get("type", "string") not in {"string", "number", "bool", "boolean", "date"}:
            raise HTTPException(status_code=422, detail=messages.detail("required_type_invalid"))
        if item["name"] in names: raise HTTPException(status_code=422, detail=messages.detail("required_field_duplicate"))
        names.add(item["name"])
    preferences = body.get("preferences", analysis.get("instance_preferences", []))
    if not isinstance(preferences, list) or len(preferences) > 100 or any(not isinstance(x, dict) or not str(x.get("field", "")).strip() or not str(x.get("label", "")).strip() for x in preferences):
        raise HTTPException(status_code=422, detail=messages.detail("pref_list_invalid"))
    analysis["title"] = title or "场景实例"
    analysis["segmentation_schema_version"] = 1
    analysis["segmentation"] = segmentation
    analysis["scope"] = {"mode":"global"} if segmentation["mode"] == "global" else {"mode":"segmented"}
    analysis["required_inputs"] = required_inputs
    if "segmentation" in body:
        normalized_preferences = segmentation["global_preferences"] if segmentation["mode"] == "global" else []
    else:
        normalized_preferences = [{**item, "strength":item.get("strength", "must")} for item in preferences]
    runtime_names = _runtime_field_names(required_inputs, segmentation)
    normalized_preferences = _prune_preferences(normalized_preferences, runtime_names)
    for variant in segmentation.get("variants") or []:
        if isinstance(variant, dict): variant["preferences"] = _prune_preferences(variant.get("preferences"), runtime_names)
    segmentation["global_preferences"] = normalized_preferences
    analysis["segmentation"] = segmentation
    analysis["instance_preferences"] = normalized_preferences
    geo_fields = {dimension["field"] for dimension in segmentation["dimensions"]} | {"destination_city", "district", "area"}
    conditions = []
    for item in normalized_preferences:
        field = str(item["field"])
        if analysis["scope"]["mode"] == "global" and field in geo_fields: continue
        operator = item.get("operator")
        if operator not in {"equals", "lte", "gte", "exists"}:
            operator = "lte" if field.endswith(("_max", "_upper")) or field in {"max_price", "budget_max"} else "gte" if field.endswith(("_min", "_lower")) or field in {"min_price", "budget_min"} else "equals"
        condition = {"field":field,"operator":operator,"label":item["label"]}
        if operator != "exists": condition["value"] = item.get("value")
        conditions.append(condition)
    if segmentation["mode"] == "segmented":
        conditions = []
    if isinstance(analysis.get("policies"), list):
        for policy in analysis["policies"]:
            if isinstance(policy, dict): policy["conditions"] = conditions
    scene["analysis"] = analysis
    scene["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # Keep the generated resource's parameter links aligned with the instance editor.
    generated = analysis.get("generated", {})
    resource_id = generated.get("resource_type_id")
    if resource_id and store.get("resource-types", resource_id):
        resource = store.get("resource-types", resource_id)
        param_ids = []
        old_param_ids = generated.get("created_param_ids", [])
        if not isinstance(old_param_ids, list): old_param_ids = [old_param_ids] if old_param_ids else []
        prior_resource_params = resource.get("params", [])
        if not isinstance(prior_resource_params, list): prior_resource_params = [prior_resource_params] if prior_resource_params else []
        suffix = scenario_id.removeprefix("scene_")
        old_param_ids = list(set([*old_param_ids, *(str(x) for x in prior_resource_params if str(x).startswith(f"scene_{suffix}_"))]))
        for item in required_inputs:
            param_id = f"scene_{suffix}_{item['name']}"
            if not store.get("params", param_id):
                label = str(item["label"])[:160]
                param_type = "bool" if item.get("type") == "boolean" else str(item.get("type") or "string")
                if param_type not in {"string", "number", "bool", "date"}: param_type = "string"
                store.put("params", param_id, {"param_id":param_id,"param_name":item["name"],"param_type":param_type,"display_name_zh":label,"display_name_en":label,"required":bool(item.get("required", False))}, create_only=True)
            param_ids.append(param_id)
        existing_params = resource.get("params", [])
        if not isinstance(existing_params, list): existing_params = [existing_params] if existing_params else []
        resource["params"] = sorted(set([x for x in existing_params if not str(x).startswith(f"scene_{suffix}_")] + param_ids))
        store.put("resource-types", resource_id, {k:v for k,v in resource.items() if k not in {"id", "type_name"}})
        generated["created_param_ids"] = param_ids
        analysis["generated"] = generated
        for old_id in old_param_ids:
            if old_id not in param_ids:
                try: store.delete("params", old_id)
                except StoreError: pass
    old_constraints = set()
    reverted_rules = []
    dropped_conditions: list[str] = []
    for auth_index, auth_id in enumerate(generated.get("authorization_ids", [])):
        auth = store.get("authorizations", auth_id)
        if not auth: continue
        old_ids = auth.get("constraints", [])
        if not isinstance(old_ids, list): old_ids = [old_ids] if old_ids else []
        old_constraints.update(str(x) for x in old_ids)
        old_signature = _condition_signature([str(x) for x in old_ids])
        was_active = str(auth.get("policy_status", "active")) == "active"
        next_ids = []
        for condition_index, condition in enumerate(conditions):
            field = str(condition["field"])
            operator = condition["operator"]
            compiled_condition = _compile_condition(field, operator, condition.get("value"))
            if compiled_condition is None:
                dropped_conditions.append(f"{field}：{operator} 无法比较 {condition.get('value')!r}")
                continue
            constraint_id = f"scene_{scenario_id.removeprefix('scene_')}_instance_{auth_index+1}_{condition_index+1}"
            constraint_type, value = compiled_condition
            store.put("constraints", constraint_id, {"constraint_type":constraint_type,"constraint_value":value})
            next_ids.append(constraint_id)
        auth_record = {k:v for k,v in auth.items() if k not in {"id", "authorization_id"}}
        auth_record["constraints"] = next_ids
        if segmentation["mode"] == "segmented":
            auth_record["effect"] = "ask"
            auth_record["policy_status"] = "suspended"
        elif was_active and old_signature != _condition_signature(next_ids):
            # An effective rule whose conditions changed must fall back to draft: the
            # user consented to the previous content, not to the rewritten one.
            auth_record["policy_status"] = "draft"
            reverted_rules.append(auth_id)
        store.put("authorizations", auth_id, auth_record)
    for old_id in old_constraints:
        if not any(old_id in (store.get("authorizations", aid) or {}).get("constraints", []) for aid in generated.get("authorization_ids", [])):
            try: store.delete("constraints", old_id)
            except StoreError: pass
    if reverted_rules:
        log = analysis.get("evolution_log", [])
        if not isinstance(log, list): log = []
        log.append({"event_id":f"evo_{uuid4().hex[:12]}","timestamp":datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),"run_id":None,"mode":"system",
                    "field":"policy_status","label":"授权规则","value":"draft",
                    "user_input":("实例条件已变更，相关授权规则自动回到草稿，需重新启用。"
                                  + (f"另有 {len(dropped_conditions)} 个条件无法编译，已忽略：{'；'.join(dropped_conditions[:5])}" if dropped_conditions else "")),
                    "actor":"系统","persistence":"instance","reverted_authorization_ids":reverted_rules})
        analysis["evolution_log"] = log[-500:]
    evolution_event = body.get("_evolution_event")
    if isinstance(evolution_event, dict):
        log = analysis.get("evolution_log", [])
        if not isinstance(log, list): log = []
        analysis["instance_revision"] = int(analysis.get("instance_revision", 1)) + 1
        evolution_event = {**evolution_event, "revision":analysis["instance_revision"]}
        analysis["evolution_log"] = [*log[-499:], evolution_event]
    stored = store.put("scenario-slices", scenario_id, {k:v for k,v in scene.items() if k not in {"id", "scenario_id"}})
    return {"scenario":stored}

@app.post("/v1/scenario-slices/{scenario_id}/feedback", dependencies=[Depends(require_session)])
async def record_scenario_feedback(scenario_id: str, body: dict[str, Any]):
    """Record runtime inputs or apply a user-confirmed reusable preference."""
    scene = store.get("scenario-slices", scenario_id)
    if not scene or scene.get("status") != "confirmed":
        raise HTTPException(status_code=404, detail=messages.detail("instance_missing_or_unconfirmed"))
    analysis = scene.get("analysis") if isinstance(scene.get("analysis"), dict) else {}
    mode = body.get("mode")
    if mode not in {"run_input", "instance_preference"}:
        raise HTTPException(status_code=422, detail=messages.detail("feedback_type_invalid"))
    field = str(body.get("field", "")).strip()
    label = str(body.get("label", "")).strip()
    value = body.get("value")
    user_input = str(body.get("user_input", "")).strip()[:2000]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", field) or not label or not isinstance(value, (str, int, float, bool)) or isinstance(value, float) and not __import__("math").isfinite(value):
        raise HTTPException(status_code=422, detail=messages.detail("feedback_item_invalid"))
    if isinstance(value, str) and len(value) > 2000:
        raise HTTPException(status_code=422, detail=messages.detail("feedback_item_too_long"))
    run_id = str(body.get("run_id") or f"run_{uuid4().hex[:12]}")[:100]
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    preferences = analysis.get("instance_preferences", [])
    if not isinstance(preferences, list): preferences = []
    prior_revision = int(analysis.get("instance_revision", 1))
    event = {"event_id":f"evo_{uuid4().hex[:12]}","timestamp":now,"run_id":run_id,"mode":mode,"field":field,"label":label,"value":value,"user_input":user_input,"actor":str(body.get("actor") or "MCP 智能体")[:120],"from_revision":prior_revision}
    if mode == "run_input":
        event["persistence"] = "this_run"
        log = analysis.get("evolution_log", [])
        if not isinstance(log, list): log = []
        analysis["evolution_log"] = [*log[-499:], event]
        scene["analysis"] = analysis
        scene["updated_at"] = now
        stored = store.put("scenario-slices", scenario_id, {k:v for k,v in scene.items() if k not in {"id", "scenario_id"}})
        return {"scenario":stored,"event":event,"updated_instance":False}

    if body.get("user_confirmed") is not True or not user_input:
        raise HTTPException(status_code=422, detail=messages.detail("preference_needs_confirmation"))
    operator = body.get("operator", "equals")
    if operator not in {"equals", "lte", "gte", "exists"} or operator in {"lte", "gte"} and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise HTTPException(status_code=422, detail=messages.detail("constraint_operator_invalid"))
    segmentation = analysis.get("segmentation") if isinstance(analysis.get("segmentation"), dict) else {"mode":"global"}
    variant_id = str(body.get("variant_id", ""))
    if segmentation.get("mode") == "segmented":
        variants = segmentation.get("variants", [])
        variant_index = next((i for i, item in enumerate(variants) if isinstance(item, dict) and item.get("id") == variant_id), None)
        if variant_index is None: raise HTTPException(status_code=422, detail=messages.detail("preference_variant_required"))
        preferences = variants[variant_index].get("preferences", [])
        if not isinstance(preferences, list): preferences = []
    else:
        scope_mode = body.get("scope", "global")
        scope = analysis.get("scope") if isinstance(analysis.get("scope"), dict) else {"mode":"global"}
        if scope_mode != "global": raise HTTPException(status_code=422, detail=messages.detail("preference_scope_mismatch"))
        preferences = analysis.get("instance_preferences", [])
        if not isinstance(preferences, list): preferences = []
    index = next((i for i, item in enumerate(preferences) if isinstance(item, dict) and item.get("field") == field), None)
    previous_value = preferences[index].get("value") if index is not None else None
    updated = {"field":field,"label":label,"value":value,"operator":operator,"strength":"must"}
    if index is None: preferences.append(updated)
    else: preferences[index] = {**preferences[index], **updated}
    event.update({"persistence":"instance","scope":"variant" if segmentation.get("mode") == "segmented" else "global","variant_id":variant_id or None,"operator":operator,"previous_value":previous_value,"user_confirmed":True})
    if segmentation.get("mode") == "segmented":
        variants[variant_index] = {**variants[variant_index],"preferences":preferences}
        segmentation["variants"] = variants
        result = await update_scenario_instance(scenario_id, {"segmentation":segmentation,"_evolution_event":event})
    else:
        result = await update_scenario_instance(scenario_id, {"preferences":preferences,"_evolution_event":event})
    stored = result["scenario"]
    latest = (stored.get("analysis") or {}).get("evolution_log", [])[-1]
    return {"scenario":stored,"event":latest,"updated_instance":True}

EXECUTABLE_CONSTRAINT_TYPES = {"context_equals", "numeric_lte", "numeric_gte", "context_exists", "source_trust_min", "temporal_lte", "temporal_gte"}

_RELATIVE_ZH = (
    r"(?:今|明|后|昨|前)天|(?:今|明|后|昨)晚|大后天|"
    r"(?:本|这|下|上|下下)周(?:[一二三四五六日天])?|(?:本|这|下|上)周(?:末)?|"
    r"(?:星期|周)[一二三四五六日天]|"
    r"(?:本|这|下|上)(?:个)?月|"
    r"现在|马上|稍后|立刻|"
    r"\d+\s*(?:天|周|个月|年)(?:后|前|之后|以前)"
)
_RELATIVE_EN = (
    r"today|tomorrow|tonight|yesterday|now|asap|as soon as possible|day after tomorrow|"
    r"(?:this|next|last)\s+(?:week|month|year|weekend|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"in\s+\d+\s+(?:days?|weeks?|months?|years?)|"
    r"\d+\s+(?:days?|weeks?|months?|years?)\s+(?:later|from now|ago)"
)
RELATIVE_TIME_PATTERN = re.compile(rf"^(?:{_RELATIVE_ZH}|{_RELATIVE_EN})$", re.IGNORECASE)

def _runtime_field_names(required_inputs: Any, segmentation: Any = None) -> set[str]:
    """Field names the agent must supply on every execution: they hold no reusable value."""
    names: set[str] = set()
    for item in required_inputs if isinstance(required_inputs, list) else []:
        if isinstance(item, dict) and item.get("name"): names.add(str(item["name"]))
    dimensions = segmentation.get("dimensions") if isinstance(segmentation, dict) else None
    for dimension in dimensions if isinstance(dimensions, list) else []:
        if isinstance(dimension, dict) and dimension.get("field"): names.add(str(dimension["field"]))
    return names

def _prune_preferences(preferences: Any, runtime_names: set[str]) -> list[dict[str, Any]]:
    """Keep only preferences that are reusable across executions.

    A value collected for one execution must not become a standing preference:
    runtime fields (already declared in required_inputs) and relative time
    expressions ("今天" / "明天") are dropped here, before they can be compiled
    into authorization conditions.
    """
    kept: list[dict[str, Any]] = []
    for item in preferences if isinstance(preferences, list) else []:
        if not isinstance(item, dict): continue
        field = str(item.get("field") or "")
        # 注意：字段同时是"每次必填"与"长期偏好"是允许的（第三档"两者兼有"），
        # 因此不再因为它是运行时字段就丢弃——那会把立场条件一并抹掉。
        if not field: continue
        value = item.get("value")
        if isinstance(value, str) and RELATIVE_TIME_PATTERN.match(value.strip()): continue
        kept.append(item)
    return kept

def _policy_constraint_ids(authorization: dict[str, Any]) -> list[str]:
    ids = authorization.get("constraints", [])
    if not isinstance(ids, list): ids = [ids] if ids else []
    return [str(x) for x in ids]

def _policy_problems(authorization: dict[str, Any]) -> list[str]:
    """Reasons this rule cannot take effect yet. Empty list means it is executable."""
    problems: list[str] = []
    for constraint_id in _policy_constraint_ids(authorization):
        record = store.get("constraints", constraint_id)
        if not record:
            problems.append(f"条件 {constraint_id} 不存在")
            continue
        kind = str(record.get("constraint_type") or "")
        if kind not in EXECUTABLE_CONSTRAINT_TYPES:
            problems.append(f"条件 {constraint_id} 的操作符“{kind or '未指定'}”尚不可执行")
            continue
        value = decode_constraint_value(record.get("constraint_value"))
        if kind == "source_trust_min":
            if str(value) not in {"low", "medium", "high"}:
                problems.append(f"条件 {constraint_id} 的取值无法识别")
            continue
        if not isinstance(value, dict) or not value.get("key"):
            problems.append(f"条件 {constraint_id} 缺少字段名，无法执行")
            continue
        if kind in {"context_equals", "numeric_lte", "numeric_gte", "temporal_lte", "temporal_gte"} and value.get("value") is None:
            problems.append(f"条件 {constraint_id} 缺少比较值，无法执行")
    return problems

def _policy_summary(authorization_id: str, authorization: dict[str, Any]) -> dict[str, Any]:
    conditions = []
    for constraint_id in _policy_constraint_ids(authorization):
        record = store.get("constraints", constraint_id) or {}
        conditions.append({"constraint_id":constraint_id, "type":str(record.get("constraint_type") or ""), "value":decode_constraint_value(record.get("constraint_value"))})
    actions = authorization.get("actions", [])
    if not isinstance(actions, list): actions = [actions] if actions else []
    return {
        "authorization_id":authorization_id,
        "policy_status":str(authorization.get("policy_status", "active")),
        "effect":str(authorization.get("effect", "ask")),
        "grantor_id":str(authorization.get("grantor_id") or ""),
        "grantee_id":str(authorization.get("grantee_id") or ""),
        "resource_type_id":str(authorization.get("resource_type_id") or ""),
        "resource_pattern":str(authorization.get("resource_pattern") or "*"),
        "actions":[str(x) for x in actions],
        "conditions":conditions,
        "problems":_policy_problems(authorization),
    }

def _condition_signature(constraint_ids: list[str]) -> tuple:
    """Comparable fingerprint of a rule's conditions, used to detect real edits."""
    parts = []
    for constraint_id in constraint_ids:
        record = store.get("constraints", constraint_id) or {}
        parts.append((constraint_id, str(record.get("constraint_type") or ""), json.dumps(decode_constraint_value(record.get("constraint_value")), ensure_ascii=False, sort_keys=True, default=str)))
    return tuple(sorted(parts))

def _scenario_analysis(scene: dict[str, Any]) -> dict[str, Any]:
    return scene.get("analysis") if isinstance(scene.get("analysis"), dict) else {}

@app.get("/v1/scenario-slices/{scenario_id}/policies", dependencies=[Depends(require_session)])
async def list_scenario_policies(scenario_id: str):
    """Rules generated by one scene, with the information needed to review them."""
    scene = store.get("scenario-slices", scenario_id)
    if not scene: raise HTTPException(status_code=404, detail=messages.detail("instance_missing"))
    analysis = _scenario_analysis(scene)
    segmentation = analysis.get("segmentation") if isinstance(analysis.get("segmentation"), dict) else {"mode":"global"}
    generated = analysis.get("generated") if isinstance(analysis.get("generated"), dict) else {}
    ids = generated.get("authorization_ids") or []
    if not isinstance(ids, list): ids = [ids] if ids else []
    rules = [summary for summary in (_policy_summary(str(i), a) for i in ids for a in [store.get("authorizations", str(i))] if a)]
    return {"scenario_id":scenario_id, "segmentation_mode":str(segmentation.get("mode", "global")), "rules":rules}

async def _set_scenario_policy_status(scenario_id: str, body: dict[str, Any], status: str) -> dict[str, Any]:
    """Enable or suspend the rules a scene generated. Never executes the actions."""
    scene = store.get("scenario-slices", scenario_id)
    if not scene or scene.get("status") != "confirmed":
        raise HTTPException(status_code=404, detail=messages.detail("confirm_before_manage_rules"))
    analysis = _scenario_analysis(scene)
    segmentation = analysis.get("segmentation") if isinstance(analysis.get("segmentation"), dict) else {"mode":"global"}
    generated = analysis.get("generated") if isinstance(analysis.get("generated"), dict) else {}
    all_ids = [str(x) for x in (generated.get("authorization_ids") or [])]
    if not all_ids: raise HTTPException(status_code=422, detail=messages.detail("scene_has_no_rules"))
    if status == "active" and str(segmentation.get("mode", "global")) == "segmented":
        raise HTTPException(status_code=422, detail=messages.detail("segmented_enable_unsupported"))
    requested = body.get("authorization_ids")
    if requested in (None, [], "all"): target_ids = all_ids
    elif isinstance(requested, list): target_ids = [str(x) for x in requested]
    else: raise HTTPException(status_code=422, detail=messages.detail("authorization_ids_array"))
    unknown = [x for x in target_ids if x not in all_ids]
    if unknown: raise HTTPException(status_code=422, detail=messages.detail("rules_not_in_scene", names="、".join(unknown[:5])))
    changed, blocked = [], []
    for authorization_id in target_ids:
        authorization = store.get("authorizations", authorization_id)
        if not authorization: continue
        problems = _policy_problems(authorization) if status == "active" else []
        if problems:
            blocked.append({"authorization_id":authorization_id, "problems":problems})
            continue
        if str(authorization.get("policy_status", "active")) == status: continue
        record = {k:v for k,v in authorization.items() if k not in {"id", "authorization_id"}}
        record["policy_status"] = status
        store.put("authorizations", authorization_id, record)
        changed.append(authorization_id)
    if blocked and not changed:
        return JSONResponse({"error":"policy_not_executable", "detail":"规则条件不可执行，未启用任何规则。", "blocked":blocked}, status_code=422)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log = analysis.get("evolution_log", [])
    if not isinstance(log, list): log = []
    log.append({"event_id":f"evo_{uuid4().hex[:12]}","timestamp":now,"run_id":None,"mode":"system","field":"policy_status","label":"授权规则",
                "value":status,"user_input":("用户启用了该场景的授权规则。" if status == "active" else "用户暂停了该场景的授权规则。"),
                "actor":"用户","persistence":"instance","authorization_ids":changed,"blocked":blocked})
    analysis["evolution_log"] = log[-500:]
    scene["analysis"] = analysis
    scene["updated_at"] = now
    stored = store.put("scenario-slices", scenario_id, {k:v for k,v in scene.items() if k not in {"id", "scenario_id"}})
    return {"scenario":stored, "status":status, "changed":changed, "blocked":blocked}

@app.post("/v1/scenario-slices/{scenario_id}/activate", dependencies=[Depends(require_session)])
async def activate_scenario_policies(scenario_id: str, body: dict[str, Any]):
    """Make the scene's rules participate in authorization decisions (draft -> active)."""
    return await _set_scenario_policy_status(scenario_id, body, "active")

@app.post("/v1/scenario-slices/{scenario_id}/suspend", dependencies=[Depends(require_session)])
async def suspend_scenario_policies(scenario_id: str, body: dict[str, Any]):
    """Stop the scene's rules from participating in decisions (active -> suspended)."""
    return await _set_scenario_policy_status(scenario_id, body, "suspended")

@app.post("/v1/scenario-slices/{scenario_id}/preview", dependencies=[Depends(require_session)])
async def preview_scenario_instance(scenario_id: str, body: dict[str, Any]):
    """Dry-run a saved scene template. This endpoint never executes actions or writes decisions."""
    scene = store.get("scenario-slices", scenario_id)
    if not scene or scene.get("status") != "confirmed":
        raise HTTPException(status_code=404, detail=messages.detail("instance_not_confirmed"))
    analysis = scene.get("analysis") if isinstance(scene.get("analysis"), dict) else {}
    request_inputs = body.get("request_inputs", {})
    candidate = body.get("candidate", {})
    if not isinstance(request_inputs, dict) or not isinstance(candidate, dict):
        raise HTTPException(status_code=422, detail=messages.detail("preview_input_invalid"))
    if len(request_inputs) > 100 or len(candidate) > 100:
        raise HTTPException(status_code=422, detail=messages.detail("preview_too_many"))
    for source in (request_inputs, candidate):
        if any(not isinstance(k, str) or not isinstance(v, (str, int, float, bool, type(None))) for k, v in source.items()):
            raise HTTPException(status_code=422, detail=messages.detail("preview_value_invalid"))
        if any(isinstance(v, str) and len(v) > 2000 for v in source.values()):
            raise HTTPException(status_code=422, detail=messages.detail("preview_item_too_long"))

    required_inputs = analysis.get("required_inputs", [])
    if not isinstance(required_inputs, list): required_inputs = []
    missing = [{"name":str(item.get("name", "")), "label":str(item.get("label") or item.get("name") or "必填信息")} for item in required_inputs if isinstance(item, dict) and item.get("required", False) and (request_inputs.get(str(item.get("name", ""))) is None or request_inputs.get(str(item.get("name", ""))) == "")]
    scope = analysis.get("scope") if isinstance(analysis.get("scope"), dict) else {"mode":"global"}
    segmentation = analysis.get("segmentation") if isinstance(analysis.get("segmentation"), dict) else {"mode":"global","dimensions":[],"global_preferences":[],"variants":[]}
    scope_result = {"mode":scope.get("mode", "global"), "dimension":scope.get("dimension"), "expected":scope.get("value"), "actual":None, "status":"match"}
    selected_variant = None
    if segmentation.get("mode") == "segmented":
        dimensions = segmentation.get("dimensions", []) if isinstance(segmentation.get("dimensions"), list) else []
        actual_values = {str(d.get("field")):request_inputs.get(str(d.get("field"))) for d in dimensions if isinstance(d, dict)}
        missing_dims = [str(d.get("label") or d.get("field")) for d in dimensions if isinstance(d, dict) and actual_values.get(str(d.get("field"))) in (None, "")]
        if missing_dims:
            scope_result = {"mode":"segmented","dimensions":dimensions,"actual_values":actual_values,"status":"missing","missing_dimensions":missing_dims}
        else:
            variants = segmentation.get("variants", []) if isinstance(segmentation.get("variants"), list) else []
            selected_variant = next((v for v in variants if isinstance(v, dict) and all(str(v.get("values", {}).get(field, "")).strip().casefold() == str(value).strip().casefold() for field, value in actual_values.items())), None)
            scope_result = {"mode":"segmented","dimensions":dimensions,"actual_values":actual_values,"status":"match" if selected_variant else "not_applicable","variant_id":selected_variant.get("id") if selected_variant else None}
    elif scope.get("mode") == "by_dimension":
        dimension = str(scope.get("dimension") or "destination_city")
        actual_scope = request_inputs.get(dimension)
        scope_result["actual"] = actual_scope
        if actual_scope in (None, ""):
            scope_result["status"] = "missing"
        elif str(actual_scope).strip().casefold() != str(scope.get("value", "")).strip().casefold():
            scope_result["status"] = "not_applicable"

    preferences = analysis.get("instance_preferences", [])
    if not isinstance(preferences, list): preferences = []
    if segmentation.get("mode") == "segmented":
        preferences = [*(segmentation.get("global_preferences", []) if isinstance(segmentation.get("global_preferences"), list) else []), *((selected_variant or {}).get("preferences", []) if selected_variant else [])]
    if not preferences and segmentation.get("mode") != "segmented":
        geo = {str(scope.get("dimension") or "destination_city"), "destination_city", "district", "area"}
        preferences = [{"field":x.get("name"), "label":x.get("label") or x.get("name"), "value":x.get("value"), "strength":"must"} for x in analysis.get("facts", []) if isinstance(x, dict) and x.get("name") and x.get("source") != "suggestion" and (scope.get("mode") == "by_dimension" or x.get("name") not in geo)]
    actuals = {**request_inputs, **candidate}
    checks = []
    for item in preferences[:100]:
        if not isinstance(item, dict): continue
        field = str(item.get("field") or item.get("name") or "")
        if not field: continue
        input_key = "price" if field in {"min_price", "max_price", "price_min", "price_max", "budget_min", "budget_max"} else field
        operator = item.get("operator")
        if operator not in {"equals", "lte", "gte", "exists"}:
            operator = "lte" if field.endswith(("_max", "_upper")) or field in {"max_price", "budget_max"} else "gte" if field.endswith(("_min", "_lower")) or field in {"min_price", "budget_min"} else "equals"
        actual = actuals.get(input_key)
        expected = item.get("value")
        status = "missing"
        if operator == "exists":
            status = "pass" if actual not in (None, "") else "fail"
        elif actual not in (None, ""):
            if operator == "equals":
                def comparable(value: Any) -> Any:
                    if isinstance(value, str):
                        if value.casefold() in {"true", "false"}: return value.casefold() == "true"
                        return value.strip().casefold()
                    return value
                status = "pass" if comparable(actual) == comparable(expected) else "fail"
            else:
                try:
                    left, right = float(actual), float(expected)
                    status = "pass" if (left <= right if operator == "lte" else left >= right) else "fail"
                except (TypeError, ValueError): status = "invalid"
        checks.append({"field":field, "label":item.get("label") or field, "input_key":input_key, "operator":operator, "expected":expected, "actual":actual, "strength":item.get("strength", "must"), "status":status})

    hard_checks = [x for x in checks if x["strength"] != "prefer"]
    if missing:
        overall = "incomplete"
    elif scope_result["status"] == "not_applicable":
        overall = "not_applicable"
    elif scope_result["status"] == "missing":
        overall = "incomplete"
    elif any(x["status"] in {"fail", "invalid"} for x in hard_checks):
        overall = "fail"
    elif any(x["status"] == "missing" for x in hard_checks):
        overall = "needs_data"
    else:
        overall = "pass"
    return {"scenario_id":scenario_id, "scenario_title":analysis.get("title", "场景实例"), "preview":True, "side_effects":False, "status":overall, "missing_required":missing, "scope":scope_result, "selected_variant":selected_variant, "checks":checks, "summary":{"pass":sum(x["status"] == "pass" for x in checks),"fail":sum(x["status"] in {"fail", "invalid"} for x in checks),"missing":sum(x["status"] == "missing" for x in checks)}, "message":{"incomplete":"还有必填信息没有填写。","not_applicable":"找不到与当前维度组合匹配的场景分组，需询问用户或建立新分组。","fail":"模拟对象未满足一个或多个必须条件。","needs_data":"部分条件还没有足够信息进行检查。","pass":"模拟输入满足当前场景实例的必需条件。"}[overall]}

def _scopes_for(language: str) -> dict[str, str]:
    """范围标签是数据：按显示语言返回（英文界面下不显示中文范围名）。"""
    return agent_access.SCOPES_EN if language == "en" else agent_access.SCOPES


def _localize_items(items: Any) -> Any:
    """把一批 {name,label} 的标签按语言本地化（供偏好列表与字段列表共用）。"""
    if not isinstance(items, list): return items
    try:
        from .field_names import default_label
    except Exception:
        return items
    localized = []
    for item in items:
        if not isinstance(item, dict): localized.append(item); continue
        name = str(item.get("name") or item.get("field") or "")
        label = str(item.get("label") or "")
        try: canonical = default_label(name, "en") if name else ""
        except Exception: canonical = ""
        if name and canonical and canonical != name:
            item = {**item, "label": canonical}
        elif re.search(r"[\u4e00-\u9fff]", label):
            item = {**item, "label": name or label}
        localized.append(item)
    return localized


def _localize_scene_labels(record: Any, language: str) -> Any:
    """按显示语言重新取用字段标签。

    场景分析产出的标签会固定为**分析当时**的语言，因此切换界面语言后，
    旧场景的必填项/偏好标签仍是中文。这里在读取时重新取用：
      1. 已知字段（field_names 有规范标签）→ 用规范英文标签；
      2. 自定义字段且标签含中文 → 退回英文字段键，避免英文界面里混中文；
      3. 其余原样返回。
    只影响展示，不写回存储。
    """
    if language != "en" or not isinstance(record, dict): return record
    analysis = record.get("analysis")
    if not isinstance(analysis, dict): return record
    try:
        from .field_names import default_label
    except Exception:
        return record
    out = dict(record); out["analysis"] = dict(analysis)
    # 偏好行的标签来自 segmentation 里的偏好列表（而不是 facts），必须一并处理，
    # 否则预演页/实例页的偏好项仍是分析当时的中文标签。
    segmentation = analysis.get("segmentation")
    if isinstance(segmentation, dict):
        seg_out = dict(segmentation)
        for seg_key in ("global_preferences", "instance_preferences"):
            seg_out[seg_key] = _localize_items(segmentation.get(seg_key))
        variants = segmentation.get("variants")
        if isinstance(variants, list):
            seg_out["variants"] = [
                {**v, "preferences": _localize_items(v.get("preferences"))} if isinstance(v, dict) else v
                for v in variants
            ]
        out["analysis"]["segmentation"] = seg_out
    # 前端读的是顶层 analysis.instance_preferences（后端 _normalize_segmentation 会写在那里），
    # 而不是 segmentation 里的同名键 —— 两处都要处理。
    for top_key in ("instance_preferences", "global_preferences"):
        if isinstance(analysis.get(top_key), list):
            out["analysis"][top_key] = _localize_items(analysis.get(top_key))
    notes = analysis.get("contract_notes")
    if isinstance(notes, list):
        localized = []
        for item in notes:
            if isinstance(item, dict) and item.get("message_key"):
                from . import messages as _messages
                item = {**item, "message": _messages.msg_for(item["message_key"], language, **(item.get("params") or {}))}
            localized.append(item)
        out["analysis"]["contract_notes"] = localized
    for key in ("required_inputs", "facts"):
        items = analysis.get(key)
        if not isinstance(items, list): continue
        localized = []
        for item in items:
            if not isinstance(item, dict): localized.append(item); continue
            name, label = str(item.get("name") or ""), str(item.get("label") or "")
            try: canonical = default_label(name, language) if name else ""
            except Exception: canonical = ""
            if name and canonical and canonical != name:
                item = {**item, "label": canonical}
            elif re.search(r"[\u4e00-\u9fff]", label):
                item = {**item, "label": name or label}
            localized.append(item)
        out["analysis"][key] = localized
    return out


@app.get("/v1/{collection}", dependencies=[Depends(require_session)])
async def list_items(collection: str, request: Request):
    try:
        items = store.list(collection)
        if collection == "scenario-slices":
            language = display_language(request.headers.get("x-display-language"))
            items = [_localize_scene_labels(item, language) for item in items]
        return {"items": items}
    except KeyError: raise HTTPException(status_code=404, detail="Unknown collection")

@app.post("/v1/{collection}", status_code=201, dependencies=[Depends(require_session)])
async def create_item(collection: str, body: dict[str, Any]):
    try:
        id_field = INPUT_ID_FIELDS.get(collection)
        item_id = str(body.get("id") or (body.get(id_field) if id_field else "") or "")
        if not item_id:
            prefix = ID_PREFIXES.get(collection, collection.rstrip("s").replace("-", "_"))
            item_id = f"{prefix}_{uuid4().hex[:12]}"
        record = {k:v for k,v in body.items() if k != "id"}
        if collection == "resource-types":
            record.setdefault("type_name", item_id)
            record.setdefault("matcher_id", "glob")
            record.setdefault("default_priority", 0)
            record.setdefault("is_builtin", False)
            if not record.get("display_name_en"): record["display_name_en"] = record.get("display_name_zh", item_id)
        elif collection == "actions":
            if not record.get("display_name_en"): record["display_name_en"] = record.get("display_name_zh", item_id)
        elif collection == "authorizations":
            record.setdefault("priority", 0)
            record.setdefault("source", "user-interface")
            record.setdefault("term", "permanent")
            record.setdefault("revoked", False)
            record.setdefault("created_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        return store.put(collection, item_id, record, create_only=True)
    except FileExistsError: raise HTTPException(status_code=409, detail="Record already exists")
    except KeyError: raise HTTPException(status_code=404, detail="Unknown collection")

@app.get("/v1/{collection}/{item_id}", dependencies=[Depends(require_session)])
async def get_item(collection: str, item_id: str, request: Request):
    try: result = store.get(collection, item_id)
    except KeyError: raise HTTPException(status_code=404, detail="Unknown collection")
    if result is None: raise HTTPException(status_code=404, detail="Record not found")
    if collection == "scenario-slices":
        result = _localize_scene_labels(result, display_language(request.headers.get("x-display-language")))
    return result

@app.patch("/v1/{collection}/{item_id}", dependencies=[Depends(require_session)])
async def patch_item(collection: str, item_id: str, body: dict[str, Any]):
    try: current = store.get(collection, item_id)
    except KeyError: raise HTTPException(status_code=404, detail="Unknown collection")
    if current is None: raise HTTPException(status_code=404, detail="Record not found")
    if collection == "authorizations" and "policy_status" in body:
        # Activation is a guarded, audited operation: it must run the executability
        # checks and record why a rule became effective. A plain PATCH would bypass
        # both, so the lifecycle state is only writable through the scenario actions.
        if str(body.get("policy_status")) != str(current.get("policy_status", "active")):
            raise HTTPException(status_code=409, detail=messages.detail("rule_toggle_via_instance"))
    current.update({k:v for k,v in body.items() if k not in {"id"}})
    current.pop("id", None)
    id_field = INPUT_ID_FIELDS.get(collection)
    new_id = str(current.get(id_field, item_id)) if id_field else item_id
    if new_id != item_id:
        try: return store.rename(collection, item_id, new_id, current)
        except FileExistsError: raise HTTPException(status_code=409, detail="The new ID is already in use")
        except KeyError: raise HTTPException(status_code=404, detail="Record not found")
    return store.put(collection, item_id, current)

@app.delete("/v1/{collection}/{item_id}", status_code=204, dependencies=[Depends(require_session)])
async def delete_item(collection: str, item_id: str):
    try: deleted = store.delete(collection, item_id)
    except KeyError: raise HTTPException(status_code=404, detail="Unknown collection")
    if not deleted: raise HTTPException(status_code=404, detail="Record not found")
    return Response(status_code=204)

def _minimized_input(body: dict[str, Any], used_keys: Any) -> dict[str, Any]:
    """判定审计只保留判定实际读取过的上下文字段（docs/05 §10.1）。

    容器已整体加密，但审计仍按最小必要留存：执行时顺手带上的姓名、日期、金额等
    不属于判定依据的字段不入库，只记下"曾经提供过哪些键"。
    """
    minimized = {key: value for key, value in body.items() if key != "context"}
    context = body.get("context") if isinstance(body.get("context"), dict) else {}
    referenced = {str(key) for key in (used_keys or [])} or {"source_trust"}
    kept = {key: context[key] for key in referenced if key in context}
    omitted = sorted(set(context) - set(kept))
    minimized["context"] = kept
    if omitted: minimized["context_not_retained"] = omitted
    return minimized


@app.post("/v1/decisions/evaluate", dependencies=[Depends(require_session)])
async def evaluate(body: dict[str, Any]):
    result = store.evaluate(body)
    decision_id = str(uuid4())
    phase = body.get("phase", "pre_planning")
    if phase not in {"pre_planning", "pre_execution"}:
        raise HTTPException(status_code=422, detail="phase must be pre_planning or pre_execution")
    record = {
        "phase":phase, "result_id":result["result_id"], "reason_key":result["reason_key"],
        "reason_params":result.get("reason_params", {}), "input_params":_minimized_input(body, result.get("context_keys_used")),
        "cited_assertions":result.get("cited_assertions", []),
        "timestamp":datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try: stored = store.put("decisions", decision_id, record, create_only=True)
    except StoreError as exc:
        # A safe decision is still returned if audit persistence failed only as a diagnostic;
        # the operation must not proceed on an unrecorded allow.
        if result["result_id"] == "allow":
            result = {"result_id":"pause", "next_action":"pause", "reason_key":"decision.audit_write_failed", "reason_params":{}}
        return JSONResponse({**result, "audit_error":str(exc)}, status_code=503)
    return {"decision_id":decision_id, **result, "record":stored}

@app.get("/v1/openapi.json", dependencies=[Depends(require_session)])
async def openapi_schema():
    return app.openapi()

app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host=HOST, port=PORT, reload=False, access_log=False)
