"""Agent-facing gateway: a Unix socket in front of the local HTTP API.

Requests arriving here are **not** authenticated by a bearer token. The kernel
tells us which local process connected (uid, executable, command line); the grant
store decides whether it may do what it asked for. Approved requests are forwarded
to the loopback API with a short, per-process HMAC-signed identity assertion, so
the API can tell "an approved agent" from "someone who found the token file".

The listening socket lives in `data/` (0700) and is itself 0600.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import socketserver
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from . import agent_access
from .config import DATA_DIR
from .peercred import identify

SOCKET_FILE = DATA_DIR / "agent.sock"
ASSERTION_HEADER = "X-PO-Agent"
SIGNATURE_HEADER = "X-PO-Agent-Sig"
_HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "upgrade", "host", "content-length"}

# 每个后端进程一份，只存在于内存：本地进程无法伪造断言，除非能读进程内存。
ASSERTION_SECRET = secrets.token_bytes(32)


def sign_assertion(secret: bytes, payload: str) -> str:
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_assertion(secret: bytes, payload: str, signature: str) -> dict[str, Any] | None:
    if not payload or not signature:
        return None
    if not hmac.compare_digest(sign_assertion(secret, payload), signature):
        return None
    try:
        decoded = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


class _ThreadedUnixHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    address_family = socket.AF_UNIX

    def server_bind(self) -> None:  # 不要 getfqdn，也不要 TCP 相关设置
        self.socket.bind(self.server_address)
        self.server_name = "localhost"
        self.server_port = 0

    def get_request(self):  # type: ignore[override]
        request, _ = self.socket.accept()
        return request, ("localhost", 0)


class _GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "personal-ontology-agent-gateway"

    def log_message(self, *args: Any) -> None:  # 静默：日志由后端统一记录
        return

    # --- helpers ---------------------------------------------------------
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        return self.rfile.read(length) if length > 0 else b""

    def _proxy(self, method: str) -> None:
        target_port = getattr(self.server, "backend_port", 0)
        peer = identify(self.connection)
        if not peer.is_owner:
            self._json(403, {"error": "agent_not_owner",
                             "message": "只有本机同一用户下的程序可以访问本体。"})
            return
        identity = agent_access.identify(peer)
        agent_access.note_seen(identity)
        scope = agent_access.scope_for_request(method, self.path)
        if scope is None:
            self._json(403, {"error": "agent_endpoint_forbidden",
                             "message": "该接口不向智能体开放；请从控制台操作。"})
            return
        allowed, message = agent_access.authorize(identity["key"], scope)
        if not allowed:
            self._json(403, {"error": "agent_not_authorized", "message": message,
                             "client": {"key": identity["key"], "name": identity["name"],
                                        "scope": scope, "scope_label": agent_access.SCOPES.get(scope, scope)}})
            return

        body = self._body()
        payload = base64.urlsafe_b64encode(json.dumps(identity, ensure_ascii=False).encode("utf-8")).decode("ascii")
        headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP_BY_HOP}
        headers[ASSERTION_HEADER] = payload
        headers[SIGNATURE_HEADER] = sign_assertion(ASSERTION_SECRET, payload)
        request = urllib.request.Request(f"http://127.0.0.1:{target_port}{self.path}",
                                         data=body if body else None, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in _HOP_BY_HOP:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as exc:
            content = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (urllib.error.URLError, TimeoutError, OSError):
            self._json(503, {"error": "backend_unreachable",
                             "message": "治理后端未运行，无法完成智能体请求。"})

    def do_GET(self) -> None: self._proxy("GET")
    def do_POST(self) -> None: self._proxy("POST")
    def do_PUT(self) -> None: self._proxy("PUT")
    def do_PATCH(self) -> None: self._proxy("PATCH")
    def do_DELETE(self) -> None: self._proxy("DELETE")


def start(backend_port: int) -> threading.Thread:
    """Start the agent gateway in a background thread; returns that thread."""
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        SOCKET_FILE.unlink()
    except OSError:
        pass
    server = _ThreadedUnixHTTPServer(str(SOCKET_FILE), _GatewayHandler)
    server.backend_port = backend_port  # type: ignore[attr-defined]
    os.chmod(SOCKET_FILE, 0o600)
    thread = threading.Thread(target=server.serve_forever, name="agent-gateway", daemon=True)
    thread.start()
    return thread
