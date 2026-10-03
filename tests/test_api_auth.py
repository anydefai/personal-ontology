"""登录/锁定态/迁移的集成自检（无第三方测试框架与 httpx 依赖）。

    ~/personal-ontology/.venv/bin/python tests/test_api_auth.py

自建一个最小 ASGI 调用器，因此走的是真实路由、依赖注入、中间件与异常处理器。
迁移场景需要独立的进程与数据目录，脚本会以 --phase migration 自行拉起子进程。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS: list[tuple[bool, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((bool(condition), label))
    print(f"  {'✔' if condition else '✗'} {label}" + (f" — {detail}" if detail else ""))


async def call(method: str, path: str, *, body: dict | None = None, token: str | None = None,
               headers: dict[str, str] | None = None) -> tuple[int, dict]:
    """最小 ASGI 调用器。"""
    from backend.api import app

    raw = b"" if body is None else json.dumps(body).encode()
    extra_headers = headers or {}
    headers = []
    if body is not None:
        headers.append((b"content-type", b"application/json"))
    if token:
        headers.append((b"authorization", b"Bearer " + token.encode()))
    for name, value in extra_headers.items():
        headers.append((name.lower().encode(), str(value).encode()))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
             "root_path": "", "headers": headers, "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 8766)}
    status = {"code": 0}
    chunks: list[bytes] = []
    state = {"body": raw}

    async def receive():
        chunk, state["body"] = state["body"], b""
        return {"type": "http.request", "body": chunk, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    payload = b"".join(chunks)
    try:
        return status["code"], json.loads(payload) if payload else {}
    except ValueError:
        return status["code"], {"_raw": payload[:200].decode("utf-8", "replace")}


def _detail(payload: dict) -> str:
    detail = payload.get("detail", payload)
    return detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)


async def main_phase() -> None:
    print("=== 1. 未初始化：409 + 引导设置 ===")
    status, payload = await call("GET", "/v1/collections")
    check("未初始化访问返回 409", status == 409, f"HTTP {status} {_detail(payload)}")
    status, payload = await call("GET", "/health")
    check("/health 无需认证且报告状态", status == 200 and payload.get("initialized") is False and payload.get("locked") is True)

    print("\n=== 2. 口令策略（8 字符 + 三类字符 + 非常见）===")
    for bad, why in [("short1!", "少于 8 位"), ("abcdefgh", "只有一类"), ("password1A", "常见口令变体")]:
        status, payload = await call("POST", "/v1/setup", body={"password": bad})
        check(f"拒绝弱口令（{why}）", status == 422, _detail(payload))

    print("\n=== 3. 设置密码并创建容器 ===")
    status, payload = await call("POST", "/v1/setup", body={"password": "Ocean-Tide-74!"})
    check("设置成功", status == 200 and payload.get("token"), f"HTTP {status} {_detail(payload)}")
    token = payload.get("token", "")
    check("未检测到明文图（非迁移）", payload.get("migrated") is False)
    from backend.api import SESSION_TOKEN_FILE
    check("默认不把令牌写到磁盘", not SESSION_TOKEN_FILE.exists(),
          "跨机接入默认关闭；本机智能体走 Unix 套接字 + 进程身份授权")
    status, payload = await call("PUT", "/v1/settings/remote-agents", body={"allow_remote_agents": True}, token=token)
    check("显式开启跨机后写入令牌", status == 200 and SESSION_TOKEN_FILE.exists(), str(payload))
    status, payload = await call("PUT", "/v1/settings/remote-agents", body={"allow_remote_agents": False}, token=token)
    check("关闭后删除令牌", status == 200 and not SESSION_TOKEN_FILE.exists(), str(payload))

    print("\n=== 4. 初始化后重复 setup 被拒 ===")
    status, _ = await call("POST", "/v1/setup", body={"password": "Another-Pass-99!"})
    check("重复 setup 返回 409", status == 409)

    print("\n=== 5. 正常数据操作（带会话）===")
    status, payload = await call("POST", "/v1/principals", body={"principal_type": "person", "display_name_zh": "本人"}, token=token)
    check("创建主体成功", status == 201, f"HTTP {status} {payload}")
    status, payload = await call("GET", "/v1/principals", token=token)
    check("列出主体成功", status == 200 and len(payload.get("items", [])) == 1)

    print("\n=== 6. 无会话一律 401 ===")
    for method, path in [("GET", "/v1/collections"), ("GET", "/v1/principals"), ("GET", "/v1/settings/model-service")]:
        status, payload = await call(method, path)
        check(f"{path} 未登录返回 401", status == 401, _detail(payload))

    print("\n=== 7. 锁定 ===")
    status, _ = await call("POST", "/v1/lock", token=token)
    check("锁定成功", status == 200)
    check("锁定后临时凭证被删除", not SESSION_TOKEN_FILE.exists())
    status, payload = await call("GET", "/v1/collections", token=token)
    check("锁定后旧会话失效", status == 401, _detail(payload))
    status, payload = await call("GET", "/health")
    check("/health 报告已锁定", payload.get("locked") is True and payload.get("initialized") is True)

    print("\n=== 8. 错口令与退避 ===")
    status, payload = await call("POST", "/v1/login", body={"password": "Wrong-Pass-11!"})
    check("错口令返回 401", status == 401, _detail(payload))
    status, payload = await call("POST", "/v1/login", body={"password": "Wrong-Pass-11!"})
    check("立即重试被退避（429）", status == 429, _detail(payload))

    print("\n=== 9. 等待退避后正确登录，数据仍在 ===")
    time.sleep(2.2)
    status, payload = await call("POST", "/v1/login", body={"password": "Ocean-Tide-74!"})
    check("正确口令登录成功", status == 200 and payload.get("token"), f"HTTP {status} {_detail(payload)}")
    token2 = payload.get("token", "")
    status, payload = await call("GET", "/v1/principals", token=token2)
    check("解锁后数据完好", status == 200 and payload.get("items", [{}])[0].get("display_name_zh") == "本人")

    print("\n=== 10. 磁盘上无明文 ===")
    from backend.api import store
    container = store.vault.path
    text = container.read_text("utf-8")
    check("容器中无明文数据", "本人" not in text and "po:person" not in text)
    check("容器权限 0600", oct(container.stat().st_mode)[-3:] == "600")
    check("无明文图文件残留", not store.legacy_file.exists())

    print("\n=== 11. 修改密码 ===")
    status, payload = await call("PUT", "/v1/account/password", body={"current": "Wrong-Current-1!", "new": "New-Harbor-58!"}, token=token2)
    check("当前密码错误被拒", status == 401, _detail(payload))
    status, payload = await call("PUT", "/v1/account/password", body={"current": "Ocean-Tide-74!", "new": "weakweak"}, token=token2)
    check("弱的新密码被拒", status == 422, _detail(payload))
    status, payload = await call("PUT", "/v1/account/password", body={"current": "Ocean-Tide-74!", "new": "New-Harbor-58!"}, token=token2)
    check("改密成功", status == 200, _detail(payload))
    status, payload = await call("GET", "/v1/collections", token=token2)
    check("改密后所有会话失效", status == 401, _detail(payload))
    status, payload = await call("POST", "/v1/login", body={"password": "Ocean-Tide-74!"})
    check("旧密码失效", status == 401)
    time.sleep(2.2)
    status, payload = await call("POST", "/v1/login", body={"password": "New-Harbor-58!"})
    check("新密码可用", status == 200 and payload.get("token"), f"HTTP {status}")
    token3 = payload.get("token", "")
    status, payload = await call("GET", "/v1/principals", token=token3)
    check("改密后数据完好", status == 200 and len(payload.get("items", [])) == 1)

    print("\n=== 12. 账户状态 ===")
    status, payload = await call("GET", "/v1/account", token=token3)
    check("返回锁定与容器信息", status == 200 and payload.get("initialized") and payload.get("unlocked"), str(payload)[:120])


def migration_phase(data_dir: str) -> int:
    """在干净的数据目录里放明文图与旧凭证，然后走 setup 迁移。"""
    os.environ["PERSONAL_ONTOLOGY_DATA"] = data_dir
    data = Path(data_dir)
    legacy = data / "ontology.ttl"
    legacy.write_text(
        "@prefix po: <urn:personalontology:ontology#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<urn:personal-ontology:principals:p1> a po:Principal ;\n"
        '    po:principalId "p1"^^xsd:string ;\n'
        '    po:principalType "person"^^xsd:string ;\n'
        '    po:displayNameZh "迁移测试主体"^^xsd:string .\n',
        encoding="utf-8")
    (data / "api-token").write_text("legacy-token\n", encoding="utf-8")
    (data / "model-service.json").write_text('{"base_url":"https://api.example.com","model":"m","api_key_encrypted":"x"}', encoding="utf-8")
    (data / "ontology-deadbeef.ttl").write_text("# 孤儿快照\n", encoding="utf-8")

    import asyncio as _asyncio

    async def run() -> int:
        print("=== 迁移：从明文图创建容器 ===")
        status, payload = await call("POST", "/v1/setup", body={"password": "Harbor-Light-31!"})
        check("迁移式 setup 成功", status == 200 and payload.get("migrated") is True, _detail(payload))
        verification = payload.get("verification") or {}
        check("迁移校验通过", verification.get("ok") is True, str(verification.get("message")))
        token = payload.get("token", "")
        status, payload = await call("GET", "/v1/principals", token=token)
        names = [item.get("display_name_zh") for item in payload.get("items", [])]
        check("迁移后主体可读", status == 200 and "迁移测试主体" in names, str(names))
        removed = verification.get("removed_plaintext") or []
        check("明文图已删除", not legacy.exists(), f"已删：{removed}")
        check("旧 api-token 已删除", not (data / "api-token").exists())
        check("孤儿快照已删除", not (data / "ontology-deadbeef.ttl").exists())
        check("模型配置已纳入容器", "model_service" in json.loads((data / "ontology.po.json").read_text("utf-8"))["sections"])
        return 0

    _asyncio.run(run())
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--phase" and sys.argv[2] == "migration":
        sys.exit(migration_phase(sys.argv[3]))
    if len(sys.argv) >= 3 and sys.argv[1] == "--report":
        # 子进程把结果写进文件，父进程汇总
        work = Path(sys.argv[3])
        migration_phase(str(work))
        (work / "migration-result.json").write_text(json.dumps(RESULTS, ensure_ascii=False), "utf-8")
        sys.exit(0)

    work = Path(tempfile.mkdtemp(prefix="api-auth-test-"))
    os.environ["PERSONAL_ONTOLOGY_DATA"] = str(work)
    try:
        asyncio.run(main_phase())

        print("\n=== 13. 明文迁移（独立子进程/数据目录）===")
        migrate_dir = work / "migrate"
        migrate_dir.mkdir()
        before = len(RESULTS)
        proc = subprocess.run([sys.executable, str(Path(__file__)), "--phase", "migration", str(migrate_dir)],
                              capture_output=True, text=True)
        print(proc.stdout.rstrip() or proc.stderr.rstrip())
        for line in proc.stdout.splitlines():
            if line.strip().startswith(("✔", "✗")):
                RESULTS.append(("✔" in line, line.split(" ", 1)[1]))
        if len(RESULTS) == before:
            check("迁移子进程产出结果", False, proc.stderr[-300:])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    passed = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
    for ok, label in RESULTS:
        if not ok:
            print(f"  失败：{label}")
    sys.exit(0 if passed == len(RESULTS) else 1)
