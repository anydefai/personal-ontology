"""本机智能体访问控制自检（T1+T2+T3）。

    ~/personal-ontology/.venv/bin/python tests/test_agent_access.py

覆盖：未经批准一律拒绝、批准后按范围放行、未授予的范围拒绝、管理接口不对智能体开放、
撤销后立即失效、伪造断言无效。
"""
from __future__ import annotations

import http.client as http_client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PORT = 8899
PASSWORD = "Agent-Access-58!"
RESULTS: list[tuple[bool, str]] = []


def error_code(payload: dict) -> str:
    """网关自产的错误在顶层；经后端转发的被 FastAPI 包在 detail 下。"""
    if isinstance(payload.get("error"), str): return payload["error"]
    detail = payload.get("detail")
    return detail.get("error", "") if isinstance(detail, dict) else ""


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((bool(condition), label))
    print(f"  {'✔' if condition else '✗'} {label}" + (f" — {detail}" if detail else ""))


def http(method: str, path: str, body: dict | None = None, token: str | None = None, headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    head = {"Content-Type": "application/json"} if body is not None else {}
    if token: head["Authorization"] = "Bearer " + token
    head.update(headers or {})
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers=head)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try: return exc.code, json.loads(exc.read() or b"{}")
        except ValueError: return exc.code, {}


class UnixHTTPConnection(http_client.HTTPConnection):
    def __init__(self, socket_path: str):
        super().__init__("localhost", timeout=15)
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def agent_call(socket_path: str, method: str, path: str, body: dict | None = None, extra: dict | None = None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    headers.update(extra or {})
    connection = UnixHTTPConnection(socket_path)
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        try: parsed = json.loads(raw or b"{}")
        except ValueError: parsed = {}
        return response.status, parsed
    finally:
        connection.close()


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="agent-access-"))
    server = None
    try:
        env = {**os.environ, "PERSONAL_ONTOLOGY_DATA": str(work), "PYTHONPATH": str(ROOT),
               "PERSONAL_ONTOLOGY_BACKEND_PORT": str(PORT), "PERSONAL_ONTOLOGY_PORT": str(PORT),
               "PERSONAL_ONTOLOGY_MANAGER_PORT": str(PORT)}
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1",
                                   "--port", str(PORT), "--no-access-log"], cwd=str(ROOT), env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                if http("GET", "/health")[0] == 200: break
            except Exception: pass
            time.sleep(0.2)
        else:
            check("后端启动", False, "10 秒内未就绪"); return 1
        status, payload = http("POST", "/v1/setup", {"password": PASSWORD})
        token = payload.get("token", "")
        check("初始化成功", status == 200 and bool(token))

        sock = work / "agent.sock"
        check("智能体套接字已创建", sock.exists(), str(sock))
        check("套接字权限 0600", oct(sock.stat().st_mode)[-3:] == "600", oct(sock.stat().st_mode)[-3:])

        print("\n=== 1. 未批准的客户端：一律拒绝 ===")
        status, payload = agent_call(str(sock), "GET", "/v1/resource-types")
        check("未批准 → 403", status == 403, f"HTTP {status}")
        check("错误码为 agent_not_authorized",
              error_code(payload) == "agent_not_authorized", str(payload)[:120])
        check("提示指向控制台授权", "智能体授权" in str(payload), str(payload)[:120])

        print("\n=== 2. 控制台能看到这条待批准请求 ===")
        status, payload = http("GET", "/v1/agents", token=token)
        pending = payload.get("pending") or []
        check("待批准清单出现该程序", len(pending) == 1, json.dumps(pending, ensure_ascii=False)[:160])
        key = pending[0]["key"] if pending else ""
        check("记录了可执行文件与命令行", bool(pending and pending[0].get("executable") and pending[0].get("command")),
              (pending[0].get("command", "")[:80] if pending else ""))
        check("默认范围不含主体名称", "principals" not in (payload.get("default_scopes") or []), str(payload.get("default_scopes")))

        print("\n=== 3. 批准 catalog 范围后按范围放行 ===")
        status, payload = http("POST", f"/v1/agents/{key}/approve", {"scopes": ["catalog"]}, token=token)
        check("批准成功", status == 200, str(payload)[:100])
        status, payload = agent_call(str(sock), "GET", "/v1/resource-types")
        check("catalog 端点放行", status == 200 and "items" in payload, f"HTTP {status}")
        status, payload = agent_call(str(sock), "GET", "/v1/actions")
        check("同为 catalog 的端点也放行", status == 200, f"HTTP {status}")

        print("\n=== 4. 未授予的范围仍然拒绝 ===")
        status, payload = agent_call(str(sock), "GET", "/v1/principals")
        check("未授予 principals → 403", status == 403, f"HTTP {status}")
        check("说明了缺少哪个范围", "读取主体名称" in str(payload), str(payload)[:140])
        status, payload = agent_call(str(sock), "POST", "/v1/decisions/evaluate",
                                     {"principal_id": "x", "action_id": "y", "resource_type_id": "z", "resource_id": "/r"})
        check("未授予 check → 403", status == 403, f"HTTP {status}")

        print("\n=== 5. 管理接口不对智能体开放 ===")
        status, payload = agent_call(str(sock), "GET", "/v1/agents")
        check("智能体读授权清单 → 403", status == 403, f"HTTP {status}")
        check("错误码为 agent_endpoint_forbidden",
              error_code(payload) == "agent_endpoint_forbidden", str(payload)[:120])
        status, payload = agent_call(str(sock), "POST", f"/v1/agents/{key}/approve", {"scopes": ["principals"]})
        check("智能体自我提权 → 403", status == 403, f"HTTP {status}")
        status, payload = agent_call(str(sock), "PUT", "/v1/settings/language", {"language": "en"})
        check("智能体改设置 → 403", status == 403, f"HTTP {status}")

        print("\n=== 6. 伪造断言无效（直接打回环端口）===")
        status, payload = http("GET", "/v1/resource-types",
                               headers={"X-PO-Agent": "eyJ4IjoxfQ==", "X-PO-Agent-Sig": "deadbeef"})
        check("伪造断言 → 401", status == 401, f"HTTP {status}")

        print("\n=== 7. 撤销后立即失效 ===")
        status, _ = http("POST", f"/v1/agents/{key}/revoke", {}, token=token)
        check("撤销成功", status == 200)
        status, payload = agent_call(str(sock), "GET", "/v1/resource-types")
        check("撤销后 → 403", status == 403, f"HTTP {status}")
        check("提示已撤销", "撤销" in str(payload) or "拒绝" in str(payload), str(payload)[:120])

        print("\n=== 8. 再次批准可恢复 ===")
        http("POST", f"/v1/agents/{key}/approve", {"scopes": ["catalog", "principals"]}, token=token)
        status, _ = agent_call(str(sock), "GET", "/v1/principals")
        check("授予 principals 后放行", status == 200, f"HTTP {status}")
    finally:
        if server is not None:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill()
        shutil.rmtree(work, ignore_errors=True)

    passed = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
    for ok, label in RESULTS:
        if not ok: print(f"  失败：{label}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
