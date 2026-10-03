"""MCP 端到端自检：真实 uvicorn 后端 + 真实 stdio MCP 子进程。

    ~/personal-ontology/.venv/bin/python tests/test_mcp_e2e.py

覆盖：解锁期凭证按调用读取、目录返回真实数据、锁定后给出明确文案（而不是崩溃）。
"""
from __future__ import annotations

import json
import os
import shutil
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
PASSWORD = "Mcp-Endpoint-73!"
RESULTS: list[tuple[bool, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((bool(condition), label))
    print(f"  {'✔' if condition else '✗'} {label}" + (f" — {detail}" if detail else ""))


def http(method: str, path: str, body: dict | None = None, token: str | None = None, timeout: float = 10):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token: headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try: return exc.code, json.loads(exc.read())
        except Exception: return exc.code, {}


def mcp_call(data_dir: Path, name: str, arguments: dict, token_override: str | None = None,
             manager_url: str | None = None) -> dict:
    """以 stdio 驱动真实 MCP 子进程，返回工具结果。

    token_override / manager_url 用于覆盖跨机路径（令牌只来自环境变量、基址指向隧道出口）。
    """
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-03-26", "clientInfo": {"name": "e2e", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    ]
    payload = "\n".join(json.dumps(m) for m in messages) + "\n"
    env = {**os.environ, "PERSONAL_ONTOLOGY_DATA": str(data_dir), "PERSONAL_ONTOLOGY_MANAGER_PORT": str(PORT),
           "PYTHONPATH": str(ROOT)}
    if token_override is not None: env["PERSONAL_ONTOLOGY_SESSION_TOKEN"] = token_override
    if manager_url is not None: env["PERSONAL_ONTOLOGY_MANAGER_URL"] = manager_url
    proc = subprocess.run([sys.executable, "-m", "backend.mcp_server"], input=payload, capture_output=True,
                          text=True, env=env, timeout=60)
    for line in proc.stdout.splitlines():
        try: message = json.loads(line)
        except ValueError: continue
        if message.get("id") == 2:
            return message.get("result", {})
    return {"error": proc.stderr[-400:]}


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="mcp-e2e-"))
    server = None
    try:
        print("=== 1. 启动真实后端（uvicorn, 独立数据目录）===")
        env = {**os.environ, "PERSONAL_ONTOLOGY_DATA": str(work), "PYTHONPATH": str(ROOT),
               "PERSONAL_ONTOLOGY_BACKEND_PORT": str(PORT), "PERSONAL_ONTOLOGY_PORT": str(PORT),
               "PERSONAL_ONTOLOGY_MANAGER_PORT": str(PORT)}
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1",
                                   "--port", str(PORT), "--no-access-log"], cwd=str(ROOT), env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                status, payload = http("GET", "/health", timeout=2)
                if status == 200: break
            except Exception: pass
            time.sleep(0.2)
        else:
            check("后端启动", False, "10 秒内未就绪"); return 1
        check("后端启动并就绪", payload.get("initialized") is False and payload.get("locked") is True, str(payload))

        print("\n=== 1.5 本机智能体默认未授权 ===")
        result = mcp_call(work, "get_governance_catalog", {})
        text = (result.get("content") or [{}])[0].get("text", "")
        check("未批准的 MCP 客户端被拒绝", result.get("isError") is True and "智能体授权" in text, text[:80])

        print("\n=== 2. 未解锁时 MCP 应给出明确文案 ===")
        result = mcp_call(work, "get_governance_catalog", {})
        text = (result.get("content") or [{}])[0].get("text", "")
        check("未授权的客户端先被拦下", result.get("isError") is True and "智能体授权" in text, text[:80])

        print("\n=== 3. 设置密码（HTTP）并写解锁期凭证 ===")
        status, payload = http("POST", "/v1/setup", {"password": PASSWORD})
        token = payload.get("token", "")
        check("setup 成功", status == 200 and token, f"HTTP {status}")
        check("默认不落盘任何凭据", not (work / "session-token").exists(),
              "跨机接入默认关闭，磁盘上不应有可用令牌")

        print("\n=== 3.5 在控制台批准该 MCP 客户端 ===")
        status, agents = http("GET", "/v1/agents", token=token)
        pending = agents.get("pending") or []
        check("控制台看到待批准请求", len(pending) >= 1, json.dumps(pending, ensure_ascii=False)[:120])
        if pending:
            status, _ = http("POST", f"/v1/agents/{pending[0]['key']}/approve",
                             {"scopes": ["catalog", "rules", "check", "preview", "principals"]}, token=token)
            check("批准成功", status == 200, f"HTTP {status}")

        print("\n=== 4. 造一点数据（主体 / 场景 / 授权）===")
        http("POST", "/v1/principals", {"principal_type": "person", "display_name_zh": "本人"}, token)
        http("POST", "/v1/resource-types", {"type_name": "hotel", "display_name_zh": "酒店", "display_name_en": "Hotel",
                                            "matcher_id": "glob", "default_priority": 0, "is_builtin": False}, token)
        http("POST", "/v1/actions", {"action_id": "hotel.book", "display_name_zh": "预订酒店", "display_name_en": "Book",
                                     "applies_to": "hotel", "risk_level": "medium"}, token)
        scene = {"original_text": "订酒店", "status": "confirmed", "updated_at": "2026-01-01T00:00:00Z",
                 "analysis": {"title": "预订酒店", "required_inputs": [{"name": "destination_city", "label": "目的城市", "type": "string", "required": True}],
                              "instance_preferences": [{"field": "budget_total", "label": "总预算", "value": 400, "operator": "lte"}],
                              "segmentation": {"mode": "global", "dimensions": [], "global_preferences": [], "variants": []},
                              "generated": {"resource_type_id": "hotel", "created_param_ids": [], "authorization_ids": []}}}
        status, _ = http("POST", "/v1/scenario-slices", scene, token)
        check("场景写入", status == 201, f"HTTP {status}")

        print("\n=== 5. 解锁状态下 MCP 读目录 ===")
        print("  （先按管理员操作开启主体目录共享）")
        (work / "mcp-settings.json").write_text(json.dumps({"include_principals": True}), encoding="utf-8")
        result = mcp_call(work, "get_governance_catalog", {"include_principals": True})
        check("MCP 调用成功", result.get("isError") is False, str(result)[:140])
        try:
            data = json.loads((result.get("content") or [{}])[0].get("text", "{}"))
        except ValueError:
            data = {}
            check("目录返回可解析的 JSON", False, str(result)[:140])
        check("读到场景实例", len(data.get("scenario_instances", [])) == 1,
              str([s.get("name") for s in data.get("scenario_instances", [])]))
        check("读到主体", [p.get("display_name_zh") for p in data.get("principals", [])] == ["本人"],
              str(data.get("principals")))
        check("返回授权规则状态字段", all("authorization_state" in s for s in data.get("scenario_instances", [])))

        print("\n=== 6. 锁定后 MCP 再次给出明确文案（不崩溃）===")
        http("POST", "/v1/lock", token=token)
        result = mcp_call(work, "get_governance_catalog", {})
        text = (result.get("content") or [{}])[0].get("text", "")
        check("MCP 锁定提示", result.get("isError") is True and "已锁定" in text, text[:80])

        print("\n=== 6.5 跨机路径：令牌只来自环境变量（本机无 data/session-token）===")
        status, payload = http("POST", "/v1/login", {"password": PASSWORD})
        remote_token = payload.get("token", "")
        result = mcp_call(work, "get_governance_catalog", {}, token_override=remote_token,
                          manager_url=f"http://127.0.0.1:{PORT}")
        check("无令牌文件时靠环境变量可用", result.get("isError") is False, str(result)[:120])
        result = mcp_call(work, "get_governance_catalog", {}, token_override="stale-token",
                          manager_url=f"http://127.0.0.1:{PORT}")
        text = (result.get("content") or [{}])[0].get("text", "")
        check("令牌失效时提示明确", result.get("isError") is True and ("锁定" in text or "令牌" in text), text[:90])

        print("\n=== 7. 重新登录后 MCP 立即可用（按调用读取凭证）===")
        status, payload = http("POST", "/v1/login", {"password": PASSWORD})
        check("重新登录成功", status == 200 and payload.get("token"))
        result = mcp_call(work, "get_governance_catalog", {})
        check("MCP 恢复可用", result.get("isError") is False, str(result)[:100])
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
