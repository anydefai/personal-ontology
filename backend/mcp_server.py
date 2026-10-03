"""stdio MCP server for local governance lookups, checks, and confirmed scenario feedback."""
from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, MANAGER_URL, MANAGER_URL_EXPLICIT, SESSION_TOKEN_ENV, SESSION_TOKEN_FILE

# 本机默认走 Unix 套接字：由内核确认进程身份，磁盘上没有可偷的凭据。
AGENT_SOCKET = DATA_DIR / "agent.sock"

def _agent_denied_message(text: str) -> str:
    try:
        detail = json.loads(text).get("detail")
        message = detail.get("message") if isinstance(detail, dict) else None
        if message: return str(message)
    except (ValueError, AttributeError):
        pass
    return "本机治理服务拒绝了该智能体的访问；请在控制台「智能体授权」中批准。"


def http_client_error():
    import http.client
    return http.client.HTTPException


SERVER_INFO = {"name": "personal-ontology", "version": "1.0.0"}
TOOLS = [
    {"name": "get_governance_catalog", "description": "读取本机个人本体的资源类型、动作和已确认的场景实例（含范围、偏好、每次执行必填信息、最近演进记录，以及授权规则的启用状态）。执行场景时必须逐项检查必填输入和偏好；缺失或含糊时先向用户询问。只把明确表示今后也适用的偏好，在用户明确同意后写回实例。主体名称只有在管理员启用对应数据范围后才可读取。关于授权：authorization_state 为 draft/suspended 的规则不参与判定，check_authorization 会返回默认拒绝；只有 active 规则参与判定。policies 字段是分析阶段的草稿，判定实际使用的是 authorization_rules；需要判断能否放行时以 authorization_rules 的 policy_status 与 conditions 为准。first_request_summary 只是首次描述的摘要（可能含那一次的时间、地点、人数），不要把它当成场景定义或长期偏好；长期偏好看 preferences，每次执行必须向用户收集的字段看 required_inputs。authorization_rules 的 grantor_id / grantee_id 是主体 ID；只有在管理员允许提供主体目录时，才能通过 principals 把它们解析成名称，且名称如何显示由管理员的隐私设置决定（principal_display_mode：neutral 中性名 / full 真实名 / id_only 仅 ID）。", "inputSchema": {"type": "object", "properties": {"include_principals": {"type": "boolean", "description": "请求读取主体名称；需要管理员预先允许。"}}, "additionalProperties": False}, "annotations": {"title": "读取治理目录", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "check_authorization", "description": "调用本机授权引擎检查主体对资源执行动作是否允许；只返回判定并写入审计记录，不会执行该动作。", "inputSchema": {"type": "object", "properties": {"principal_id": {"type": "string"}, "action_id": {"type": "string"}, "resource_type_id": {"type": "string"}, "resource_id": {"type": "string"}, "context": {"type": "object"}, "phase": {"type": "string", "enum": ["pre_planning", "pre_execution"]}}, "required": ["principal_id", "action_id", "resource_type_id", "resource_id"], "additionalProperties": False}, "annotations": {"title": "检查授权", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}},
    {"name":"preview_scenario_instance","description":"预演某个已保存场景：提交本次用户输入和候选资源，返回缺失的必填信息及已有约束检查结果。发现缺项或重要约束未定义时，必须先向用户说明并询问；预演不执行真实动作、不修改实例。","inputSchema":{"type":"object","properties":{"scenario_id":{"type":"string"},"request_inputs":{"type":"object"},"candidate":{"type":"object"}},"required":["scenario_id"],"additionalProperties":False},"annotations":{"title":"预演场景实例","readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":False}},
    {"name":"record_scenario_feedback","description":"将场景执行中用户提供的信息写入可查记录。mode=run_input 仅作为本次执行输入留档，不改变长期偏好。mode=instance_preference 会更新可复用实例；分组场景必须提供 variant_id。只有在用户明确同意该偏好今后继续适用后才可调用；user_input 必须填写用户原话，user_confirmed 必须为 true。每次调用都会保留时间、执行 ID、前后值和实例版本。","inputSchema":{"type":"object","properties":{"scenario_id":{"type":"string"},"run_id":{"type":"string"},"mode":{"type":"string","enum":["run_input","instance_preference"]},"field":{"type":"string"},"label":{"type":"string"},"value":{"type":["string","number","boolean"]},"operator":{"type":"string","enum":["equals","lte","gte","exists"]},"scope":{"type":"string","enum":["global","by_dimension"]},"variant_id":{"type":"string"},"dimension_value":{"type":"string"},"user_input":{"type":"string"},"user_confirmed":{"type":"boolean"},"actor":{"type":"string"}},"required":["scenario_id","mode","field","label","value","user_input"],"additionalProperties":False},"annotations":{"title":"记录场景反馈","readOnlyHint":False,"destructiveHint":False,"idempotentHint":False,"openWorldHint":False}},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MCPServer:
    def __init__(self) -> None:
        self.session_id = uuid.uuid4().hex
        self.session_file = DATA_DIR / "agent-sessions" / f"{self.session_id}.json"
        self.client: dict[str, Any] = {"name": "MCP client", "version": ""}
        self.connected_at = _now()
        self.initialized = False

    @staticmethod
    def _session_token() -> str:
        """按调用读取解锁期凭证（docs/05 §5）：锁定后该文件不存在，明确报错而不是崩溃。

        跨机使用时令牌文件在原型机上，由环境变量 PERSONAL_ONTOLOGY_SESSION_TOKEN 提供
        （见 docs/06-remote-agent.md）；本机使用时仍读 data/session-token。
        """
        token = str(os.environ.get(SESSION_TOKEN_ENV) or "").strip()
        if not token:
            try:
                token = SESSION_TOKEN_FILE.read_text(encoding="utf-8").strip()
            except OSError:
                token = ""
        if not token:
            raise RuntimeError(
                "本体已锁定，或没有可用的会话令牌。请让用户先在那台运行控制台的机器上用登录密码解锁；"
                f"跨机使用时请把解锁后生成的令牌通过 {SESSION_TOKEN_ENV} 传给本进程。")
        return token

    def _write_session(self, tool_name: str | None = None) -> None:
        self.session_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = {"session_id": self.session_id, "pid": os.getpid(), "client": self.client, "connected_at": self.connected_at, "last_seen_at": _now(), "last_tool": tool_name}
        temp = self.session_file.with_suffix(".tmp")
        temp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.session_file)

    @staticmethod
    def _unix_connection():
        """HTTP over the agent Unix socket（内核确认我们是谁，无需令牌）。"""
        import http.client
        class _UnixConnection(http.client.HTTPConnection):
            def __init__(self, socket_path: str):
                super().__init__("localhost", timeout=30)
                self._socket_path = socket_path
            def connect(self) -> None:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect(self._socket_path)
        return _UnixConnection(str(AGENT_SOCKET))

    def _api(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        # 本机：Unix 套接字 + 进程身份。显式给出 MANAGER_URL 表示走 TCP（跨机经 SSH 隧道），
        # 那种情况下对端身份无法跨越隧道，只能凭令牌。
        if AGENT_SOCKET.exists() and not MANAGER_URL_EXPLICIT:
            payload = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
            headers = {"Content-Type": "application/json"} if payload is not None else {}
            connection = self._unix_connection()
            try:
                connection.request(method, path, body=payload, headers=headers)
                response = connection.getresponse()
                text = response.read(1_000_000).decode("utf-8", "replace")
                if response.status == 403:
                    raise RuntimeError(_agent_denied_message(text))
                if response.status in (401, 409):
                    raise RuntimeError("本体已锁定（或尚未初始化）。请让用户在那台运行控制台的机器上"
                                       "用登录密码解锁，然后再试。")
                if response.status >= 400:
                    raise RuntimeError(f"治理服务返回 HTTP {response.status}")
                return json.loads(text)
            except (OSError, http_client_error()) as exc:
                raise RuntimeError("无法通过本机套接字连接治理服务；请确认服务已启动。") from exc
            finally:
                connection.close()
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(f"{MANAGER_URL}{path}", data=data, method=method, headers={"Authorization": f"Bearer {self._session_token()}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read(1_000_000))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise RuntimeError(
                    "本体已锁定，或会话令牌已失效（本体重新解锁后令牌会更换）。"
                    "请让用户在那台运行控制台的机器上解锁；跨机使用时需要重启本 MCP 连接以取回新令牌。"
                ) from exc
            raise RuntimeError(f"治理服务返回 HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                f"无法连接治理服务（{MANAGER_URL}）。本机使用时请确认服务已启动；"
                "跨机使用时请确认 SSH 隧道仍在运行。"
            ) from exc

    AUTHORIZATION_STATE_NOTES = {
        "enabled": "该场景的规则已启用，判定引擎会读取它们。",
        "partial": "该场景只有部分规则已启用，其余仍是草稿或不参与判定。",
        "draft": "该场景的规则尚未启用，判定不会放行；需要用户在控制台的场景实例页启用。",
        "suspended": "该场景的规则已暂停，判定不会放行。",
        "none": "该场景还没有生成授权规则。",
        "unknown": "暂时无法读取该场景的规则状态。",
    }

    def _authorization_state(self, scenario_id: str) -> dict[str, Any]:
        """Real compiled rules of one scene, so an agent can tell draft from effective.

        `policies` in the catalog is the analysis-stage draft; this is what the decision
        engine actually reads. A failure here must not break the whole catalog.
        """
        empty = {"authorization_state": "unknown", "rules_total": 0, "rules_active": 0, "activatable": False, "authorization_rules": []}
        try:
            payload = self._api("GET", f"/v1/scenario-slices/{scenario_id}/policies")
        except RuntimeError:
            return {**empty, "authorization_state_note": self.AUTHORIZATION_STATE_NOTES["unknown"]}
        rules = payload.get("rules") if isinstance(payload.get("rules"), list) else []
        active = [rule for rule in rules if str(rule.get("policy_status")) == "active"]
        suspended = [rule for rule in rules if str(rule.get("policy_status")) == "suspended"]
        if not rules: state = "none"
        elif len(active) == len(rules): state = "enabled"
        elif active: state = "partial"
        elif suspended and len(suspended) == len(rules): state = "suspended"
        else: state = "draft"
        return {
            "authorization_state": state,
            "authorization_state_note": self.AUTHORIZATION_STATE_NOTES[state],
            "rules_total": len(rules),
            "rules_active": len(active),
            "activatable": str(payload.get("segmentation_mode", "global")) != "segmented",
            "authorization_rules": [{
                "authorization_id": rule.get("authorization_id"),
                "policy_status": rule.get("policy_status"),
                "effect": rule.get("effect"),
                "grantor_id": rule.get("grantor_id"),
                "grantee_id": rule.get("grantee_id"),
                "resource_type_id": rule.get("resource_type_id"),
                "resource_pattern": rule.get("resource_pattern"),
                "actions": rule.get("actions", []),
                "conditions": rule.get("conditions", []),
                "problems": rule.get("problems", []),
            } for rule in rules],
        }

    @staticmethod
    def _present_principal(principal: dict[str, Any], mode: str) -> dict[str, Any]:
        """按管理员设定的对外显示方式呈现主体（docs/05 §3.8）。

        neutral —— 统一中性名，本机保留真名而智能体看不到；
        full    —— 真实显示名；
        id_only —— 只给 ID 与类型。
        """
        item = {"id": principal.get("id"), "principal_id": principal.get("principal_id"),
                "principal_type": principal.get("principal_type")}
        if mode == "full":
            item["display_name_zh"] = principal.get("display_name_zh")
            item["display_name_en"] = principal.get("display_name_en")
        elif mode == "neutral":
            item["display_name_zh"] = "本人"
            item["display_name_en"] = "Me"
        return item

    def _call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "get_governance_catalog":
            resources = self._api("GET", "/v1/resource-types").get("items", [])
            actions = self._api("GET", "/v1/actions").get("items", [])
            scenes = self._api("GET", "/v1/scenario-slices").get("items", [])
            instances = []
            for scene in scenes:
                if scene.get("status") != "confirmed": continue
                analysis = scene.get("analysis") if isinstance(scene.get("analysis"), dict) else {}
                segmentation = analysis.get("segmentation") if isinstance(analysis.get("segmentation"), dict) else {"mode":"global","dimensions":[],"global_preferences":analysis.get("instance_preferences", analysis.get("facts", [])),"variants":[]}
                instances.append({"id":scene.get("id"),"name":analysis.get("title"),"first_request_summary":analysis.get("intent"),"first_request_summary_note":"仅是对首次自然语言描述的摘要，可能包含那一次的时间、地点和人数；场景的可复用名称是 name，长期偏好看 preferences，每次执行要收集的字段看 required_inputs。","scope":analysis.get("scope", {"mode":"global"}),"segmentation":segmentation,"revision":analysis.get("instance_revision", 1),"required_inputs":analysis.get("required_inputs", []),"preferences":analysis.get("instance_preferences", analysis.get("facts", [])),"evolution_log":(analysis.get("evolution_log", []) or [])[-20:],"resource_types":analysis.get("resource_types", []),"actions":analysis.get("actions", []),"policies":analysis.get("policies", []),**self._authorization_state(str(scene.get("id")))})
            result: dict[str, Any] = {"resource_types":resources, "actions":actions, "scenario_instances":instances}
            if args.get("include_principals"):
                settings_path = DATA_DIR / "mcp-settings.json"
                try:
                    settings = json.loads(settings_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError):
                    settings = {}
                if settings.get("include_principals") is not True:
                    raise RuntimeError("管理员尚未允许向智能体提供主体名称。可在本体控制台的智能体接入设置中启用。")
                mode = str(settings.get("principal_display_mode") or "neutral")
                principals = self._api("GET", "/v1/principals").get("items", [])
                result["principals"] = [self._present_principal(item, mode) for item in principals]
                result["principal_display_mode"] = mode
            self._write_session(name)
            return result
        if name == "check_authorization":
            allowed = {"principal_id", "action_id", "resource_type_id", "resource_id", "context", "phase"}
            if set(args) - allowed or any(not args.get(k) for k in ("principal_id", "action_id", "resource_type_id", "resource_id")):
                raise RuntimeError("检查授权需要主体、动作、资源类型和资源名称。")
            result = self._api("POST", "/v1/decisions/evaluate", {**args, "phase":args.get("phase", "pre_planning")})
            self._write_session(name)
            return result
        if name == "preview_scenario_instance":
            scenario_id = str(args.get("scenario_id", ""))
            if not scenario_id:
                raise RuntimeError("预演需要场景实例 ID。")
            result = self._api("POST", f"/v1/scenario-slices/{scenario_id}/preview", {"request_inputs":args.get("request_inputs", {}),"candidate":args.get("candidate", {})})
            self._write_session(name)
            return result
        if name == "record_scenario_feedback":
            allowed = {"scenario_id","run_id","mode","field","label","value","operator","scope","variant_id","dimension_value","user_input","user_confirmed","actor"}
            if set(args) - allowed or any(args.get(k) in (None, "") for k in ("scenario_id","mode","field","label","user_input")) or "value" not in args:
                raise RuntimeError("场景反馈缺少必要字段。")
            if args["mode"] == "instance_preference" and (args.get("user_confirmed") is not True or not str(args.get("user_input", "")).strip()):
                raise RuntimeError("长期偏好必须先取得用户明确同意，并提供确认原话。")
            result = self._api("POST", f"/v1/scenario-slices/{args['scenario_id']}/feedback", args)
            self._write_session(name)
            return result
        raise RuntimeError(f"未知 MCP 工具：{name}")

    @staticmethod
    def _response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = result
        return payload

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method, request_id, params = message.get("method"), message.get("id"), message.get("params") or {}
        if not isinstance(method, str) or not isinstance(params, dict):
            return self._response(request_id, error={"code": -32600, "message": "Invalid Request"})
        if method == "initialize":
            self.client = params.get("clientInfo") if isinstance(params.get("clientInfo"), dict) else self.client
            self.initialized = True
            self._write_session()
            version = params.get("protocolVersion") or "2025-03-26"
            return self._response(request_id, {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO})
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return self._response(request_id, {})
        if method == "tools/list":
            return self._response(request_id, {"tools": TOOLS})
        if method == "tools/call":
            name, args = params.get("name"), params.get("arguments") or {}
            if not isinstance(name, str) or not isinstance(args, dict):
                return self._response(request_id, error={"code": -32602, "message": "Invalid params"})
            try:
                result = self._call_tool(name, args)
                return self._response(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False})
            except Exception as exc:
                return self._response(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        if method in {"resources/list", "prompts/list"}:
            key = "resources" if method == "resources/list" else "prompts"
            return self._response(request_id, {key: []})
        if request_id is None:
            return None
        return self._response(request_id, error={"code": -32601, "message": "Method not found"})

    def run(self) -> None:
        try:
            for line in sys.stdin:
                try:
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError("JSON-RPC message must be an object")
                    result = self.handle(message)
                except Exception:
                    result = self._response(None, error={"code": -32700, "message": "Parse error"})
                if result is not None:
                    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
        finally:
            self.session_file.unlink(missing_ok=True)


def main() -> None:
    MCPServer().run()


if __name__ == "__main__":
    main()
