"""Always-on local control plane for the separately managed governance API."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .origin_policy import origin_allowed
from . import messages
from .config import (ALLOWED_ORIGINS, APP_DIR, BACKEND_PORT, CONTAINER_FILE, DATA_DIR, GRAPH_FILE, HOST, MANAGER_PORT,
                     MODEL_CONFIG_FILE, PROPERTIES_FILE, SHAPES_FILE, WEB_DIR)

APP_LABEL = "personalontology.personal-ontology"
BACKEND_LABEL = APP_LABEL + ".backend"
BACKEND_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{BACKEND_LABEL}.plist"
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
app = FastAPI(title="Personal Ontology Local Manager", version="3.1.0", docs_url=None, redoc_url=None)


def _session_valid(token: str) -> bool:
    """把令牌交给治理后端校验（后端是会话的唯一权威）。"""
    if not token: return False
    request = urllib.request.Request(BACKEND_URL + "/v1/account", headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


# 后端不可达时只放行"把它救回来"所需的端点；日志、状态、改设置一律仍要凭据。
RECOVERY_ENDPOINTS = ("/manager/health", "/manager/start", "/manager/restart")


def _recovery_path(path: str) -> bool:
    return any(path == endpoint or path.startswith(endpoint + "/") for endpoint in RECOVERY_ENDPOINTS)


async def require_token(request: Request, authorization: str | None = Header(default=None)) -> None:
    """统一凭据：校验治理后端的会话令牌。

    后端不可达时进入**本机恢复模式**——否则后端一旦挂掉，"启动/重启后端"这个入口
    就永远无法通过鉴权。恢复模式仍受回环监听与 Origin 白名单限制。
    """
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if await asyncio.to_thread(_session_valid, token):
        return
    if not await asyncio.to_thread(_backend_health) and _recovery_path(request.url.path):
        return
    raise HTTPException(status_code=401, detail={"error": "login_required", "message": "请先在控制台登录。"},
                        headers={"WWW-Authenticate": "Bearer"})


@app.middleware("http")
async def local_security(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and not origin_allowed(origin, request.headers, ALLOWED_ORIGINS):
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response


def _backend_health() -> bool:
    try:
        with urllib.request.urlopen(BACKEND_URL + "/health", timeout=1.2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _backend_health_payload() -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(BACKEND_URL + "/health", timeout=2) as response:
            return json.loads(response.read(4096))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True, timeout=12, check=False)


def _start_backend() -> tuple[bool, str]:
    if _backend_health():
        return True, "治理后端已经在运行。"
    domain = f"gui/{os.getuid()}"
    label = f"{domain}/{BACKEND_LABEL}"
    loaded = _launchctl("print", label).returncode == 0
    if loaded:
        result = _launchctl("kickstart", "-k", label)
    else:
        if not BACKEND_PLIST.exists():
            return False, "后端服务配置文件不存在，请重新运行 install.sh。"
        result = _launchctl("bootstrap", domain, str(BACKEND_PLIST))
        if result.returncode == 0:
            result = _launchctl("kickstart", label)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "launchctl 启动失败").strip().splitlines()[-1]
        return False, f"无法启动治理后端：{message[:300]}"
    for _ in range(40):
        if _backend_health():
            return True, "治理后端已启动。"
        time.sleep(0.5)
    return False, "启动命令已发出，但后端在 20 秒内没有通过健康检查。请查看启动日志。"


def _redact(line: str) -> str:
    line = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1[已隐藏]", line)
    line = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,\"']+", r"\1[已隐藏]", line)
    line = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[已隐藏密钥]", line)
    return line


def _logs(limit: int = 200, service: str = "backend") -> dict[str, Any]:
    filename = "manager.log" if service == "manager" else "server.log"
    path = DATA_DIR / filename
    if not path.exists():
        return {"lines": [], "updated_at": None, "message": "还没有启动日志。"}
    try:
        stat = path.stat()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        return {"lines": [_redact(line) for line in lines], "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), "message": None}
    except OSError:
        return {"lines": [], "updated_at": None, "message": "无法读取启动日志。"}


def _agent_sessions() -> list[dict[str, Any]]:
    directory = DATA_DIR / "agent-sessions"
    if not directory.exists():
        return []
    sessions: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            pid = int(record.get("pid", 0))
            os.kill(pid, 0)
            sessions.append({**record, "status": "connected"})
        except ProcessLookupError:
            path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return sorted(sessions, key=lambda x: str(x.get("last_seen_at", "")), reverse=True)[:50]


PRINCIPAL_DISPLAY_MODES = ("neutral", "full", "id_only")


def _mcp_settings() -> dict[str, Any]:
    path = DATA_DIR / "mcp-settings.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError, TypeError):
        value = {}
    mode = str(value.get("principal_display_mode") or "neutral")
    return {"include_principals": value.get("include_principals") is True,
            "principal_display_mode": mode if mode in PRINCIPAL_DISPLAY_MODES else "neutral"}


def _agent_configs() -> dict[str, Any]:
    python = str(APP_DIR / ".venv" / "bin" / "python")
    args = ["-m", "backend.mcp_server"]
    env = {"PYTHONPATH": str(APP_DIR), "PERSONAL_ONTOLOGY_MANAGER_PORT": str(MANAGER_PORT)}
    return {
        "workbuddy": {"mcpServers": {"personal-ontology": {"command": python, "args": args, "env": env}}},
        "muse_code": {"mcp_servers": {"personal-ontology": {"transport": "stdio", "command": python, "args": args, "env": env, "enabled": True, "mode": "optional"}}},
    }


@app.get("/")
async def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/manager/health")
async def manager_health():
    return {"status": "ok", "service": "personal-ontology-manager", "version": "3.1.0"}


def _backend_model_settings(authorization: str | None) -> dict[str, Any]:
    """模型配置存放在加密容器里，只有解锁的后端能读。

    管理器没有（也不该有）登录口令，因此不能自己解密：转发调用方的会话令牌向后端要。
    读不到时返回 configured=None（"未知"），不要谎报成"未配置"。
    """
    if not authorization:
        return {"configured": None, "error": "需要登录后才能读取模型配置"}
    request = urllib.request.Request(BACKEND_URL + "/v1/settings/model-service",
                                     headers={"Authorization": authorization})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read(8192))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 409):
            return {"configured": None, "error": "本体已锁定，先解锁才能读取模型配置"}
        return {"configured": None, "error": f"后端返回 {exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return {"configured": None, "error": "治理后端未运行，无法读取模型配置"}


@app.get("/manager/status", dependencies=[Depends(require_token)])
async def manager_status(request: Request):
    backend_online = await asyncio.to_thread(_backend_health)
    model = await asyncio.to_thread(_backend_model_settings, request.headers.get("authorization"))
    files = {
        "frontend": all((WEB_DIR / name).is_file() for name in ("index.html", "app.js", "app.css")),
        "ontology": PROPERTIES_FILE.is_file() and os.access(PROPERTIES_FILE, os.R_OK),
        "shacl": SHAPES_FILE.is_file() and os.access(SHAPES_FILE, os.R_OK),
        "rdf_store": CONTAINER_FILE.is_file() and os.access(CONTAINER_FILE, os.R_OK | os.W_OK),
    }
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "manager": True, "backend": backend_online, "decision_engine": backend_online, "files": files, "model_service": model, "agent_sessions": await asyncio.to_thread(_agent_sessions), "mcp_settings": await asyncio.to_thread(_mcp_settings)}


@app.get("/manager/agent-configs", dependencies=[Depends(require_token)])
async def agent_configs():
    return _agent_configs()


@app.put("/manager/agent-settings", dependencies=[Depends(require_token)])
async def save_agent_settings(body: dict[str, Any]):
    current = _mcp_settings()
    mode = str(body.get("principal_display_mode") or current["principal_display_mode"])
    if mode not in PRINCIPAL_DISPLAY_MODES: mode = "neutral"
    value = {"include_principals": body.get("include_principals") is True, "principal_display_mode": mode}
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = DATA_DIR / "mcp-settings.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value), encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)
    return value


@app.get("/manager/logs", dependencies=[Depends(require_token)])
async def manager_logs(service: str = "backend"):
    return await asyncio.to_thread(_logs, 200, service)


@app.post("/manager/start", dependencies=[Depends(require_token)])
async def start_backend():
    ok, message = await asyncio.to_thread(_start_backend)
    return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 503)


@app.post("/manager/restart", dependencies=[Depends(require_token)])
async def restart_backend(request: Request):
    domain_label = f"gui/{os.getuid()}/{BACKEND_LABEL}"
    loaded = _launchctl("print", domain_label).returncode == 0
    if not loaded:
        ok, message = await asyncio.to_thread(_start_backend)
        return JSONResponse({"ok": ok, "message": "后端原本未运行；" + message}, status_code=200 if ok else 503)
    result = await asyncio.to_thread(_launchctl, "kickstart", "-k", domain_label)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "重启失败").strip().splitlines()[-1]
        return JSONResponse({"ok": False, "message": message[:300]}, status_code=503)
    ok = False
    for _ in range(40):
        if await asyncio.to_thread(_backend_health):
            ok = True
            break
        await asyncio.sleep(0.5)
    _lang = display_language(request.headers.get("x-display-language"))
    message = messages.msg_for("backend_restarted_ok" if ok else "backend_restart_unhealthy", _lang)
    return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 503)


async def _proxy_backend(request: Request, path: str = "") -> Response:
    target = BACKEND_URL + ("/" + path if path else "")
    if request.url.query:
        target += "?" + request.url.query
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() in {"authorization", "content-type", "accept"}}
    req = urllib.request.Request(target, data=body if body else None, headers=headers, method=request.method)

    def send() -> tuple[int, bytes, str]:
        try:
            response = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(5_000_000), exc.headers.get("Content-Type", "application/json")
        with response:
            return response.status, response.read(5_000_000), response.headers.get("Content-Type", "application/json")

    try:
        status, content, content_type = await asyncio.to_thread(send)
        return Response(content=content, status_code=status, headers={"Content-Type": content_type, "Cache-Control": "no-store"})
    except (urllib.error.URLError, TimeoutError, OSError):
        return JSONResponse({"detail": "治理后端未运行或暂时无法连接。请到“服务监控”启动后端。"}, status_code=503)


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_v1(path: str, request: Request):
    return await _proxy_backend(request, "v1/" + path)


@app.get("/health")
async def backend_health():
    """透传治理后端的真实健康状态（含 initialized / locked），供控制台与 status.sh 使用。"""
    payload = await asyncio.to_thread(_backend_health_payload)
    if payload is None:
        return JSONResponse({"status": "degraded", "service": "personal-ontology", "detail": "治理后端未运行"}, status_code=503)
    return payload


app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.manager:app", host=HOST, port=MANAGER_PORT, reload=False, access_log=False)
