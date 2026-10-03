"""Local agent access control: who may read the ontology, and how much of it.

Design goals (docs/07-local-agent-access.md):

* **No credential on disk.** An agent is recognised by the kernel — uid, executable
  and command line of the process holding the Unix socket — not by a bearer token
  sitting in a 0600 file that any same-user process can copy.
* **Nothing is granted silently.** The first time a program connects it becomes a
  *pending* request; the console shows it and the user approves or denies.
* **Least privilege.** Every approval carries an explicit scope list; a program
  approved for `check` cannot dump the catalogue.
* **Revocable immediately.** Revoking drops the client back to *denied*.

Honest limit: a program already running as the same user can exec our interpreter
with the same arguments and therefore look identical. This design removes the
silent, trivial path (copy a token) and makes every new client visible, but it is
not a hard boundary against same-user malware.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR

CLIENTS_FILE = DATA_DIR / "agent-clients.json"

SCOPES: dict[str, str] = {
    "catalog": "读取资源类型、动作与场景实例",
    "rules": "读取授权规则",
    "decisions": "读取判定记录",
    "principals": "读取主体名称",
    "check": "提交授权检查（会写入判定记录）",
    "preview": "预演场景实例",
    "feedback": "写回场景反馈与长期偏好",
}

# 一个"只是想让智能体替我做场景"的客户端，这些就够；主体名称与判定记录默认不给。
# 英文范围标签：控制台按显示语言选用（SCOPE 标签是**数据**，前端没有映射表）。
SCOPES_EN: dict[str, str] = {
    "catalog": "Read resource types, actions and scenario instances",
    "rules": "Read authorization rules",
    "decisions": "Read decision records",
    "principals": "Read principal names",
    "check": "Submit authorization checks (writes decision records)",
    "preview": "Rehearse scenario instances",
    "feedback": "Write back scenario feedback and standing preferences",
}

DEFAULT_SCOPES: tuple[str, ...] = ("catalog", "rules", "check", "preview")

STATES = ("pending", "approved", "denied")

_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load() -> dict[str, Any]:
    try:
        value = json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"clients": {}}
    except (OSError, ValueError, TypeError):
        return {"clients": {}}


def _save(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = CLIENTS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, CLIENTS_FILE)


def _fingerprint(peer: Any) -> str:
    """Key a client by *what program it is*, not by which run or pid."""
    tail = " ".join(peer.command[1:]) if getattr(peer, "command", ()) else ""
    material = f"{peer.uid}\n{peer.executable}\n{tail[:2000]}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _display_name(peer: Any) -> str:
    from .peercred import describe

    base = describe(peer.executable)
    tail = " ".join(peer.command[1:]) if getattr(peer, "command", ()) else ""
    if "-m" in tail.split()[:2]:
        module = tail.split()[-1] if tail.split() else ""
        return f"{base} · {module}" if module else base
    return base


def identify(peer: Any) -> dict[str, Any]:
    """The identity record for a connected process (no state, no secrets)."""
    return {
        "key": _fingerprint(peer),
        "uid": peer.uid,
        "pid": peer.pid,
        "executable": peer.executable,
        "command": " ".join(peer.command) if getattr(peer, "command", ()) else peer.executable,
        "name": _display_name(peer),
    }


def note_seen(identity: dict[str, Any]) -> dict[str, Any]:
    """Record a connection; unknown clients become *pending* (nobody is auto-approved)."""
    with _lock:
        data = _load()
        clients = data.setdefault("clients", {})
        record = clients.get(identity["key"])
        if not isinstance(record, dict):
            record = {
                "key": identity["key"],
                "state": "pending",
                "scopes": [],
                "uid": identity["uid"],
                "executable": identity["executable"],
                "command": identity["command"],
                "name": identity["name"],
                "first_seen_at": _now(),
                "approvals": 0,
            }
            clients[identity["key"]] = record
        record["last_seen_at"] = _now()
        record["last_pid"] = identity["pid"]
        # 程序被替换（同一路径、不同命令行）时重新走审批
        if record.get("command") != identity["command"] and record.get("state") == "approved":
            record["state"] = "pending"
            record["command"] = identity["command"]
            record["name"] = identity["name"]
        _save(data)
        return dict(record)


def clients() -> dict[str, list[dict[str, Any]]]:
    with _lock:
        records = [v for v in _load().get("clients", {}).values() if isinstance(v, dict)]
    records.sort(key=lambda x: str(x.get("last_seen_at", "")), reverse=True)
    return {
        "pending": [r for r in records if r.get("state") == "pending"],
        "approved": [r for r in records if r.get("state") == "approved"],
        "denied": [r for r in records if r.get("state") == "denied"],
    }


def _set_state(key: str, state: str, scopes: list[str] | None = None) -> dict[str, Any]:
    with _lock:
        data = _load()
        record = data.get("clients", {}).get(key)
        if not isinstance(record, dict):
            raise KeyError(key)
        record["state"] = state
        if scopes is not None:
            record["scopes"] = [s for s in scopes if s in SCOPES]
        record["decided_at"] = _now()
        if state == "approved":
            record["approvals"] = int(record.get("approvals", 0)) + 1
        _save(data)
        return dict(record)


def approve(key: str, scopes: list[str] | None = None) -> dict[str, Any]:
    return _set_state(key, "approved", scopes if scopes is not None else list(DEFAULT_SCOPES))


def deny(key: str) -> dict[str, Any]:
    return _set_state(key, "denied", [])


def revoke(key: str) -> dict[str, Any]:
    """Withdraw an approval; the client must be approved again to read anything."""
    return _set_state(key, "denied", [])


def forget(key: str) -> None:
    with _lock:
        data = _load()
        data.get("clients", {}).pop(key, None)
        _save(data)


def authorize(key: str, scope: str) -> tuple[bool, str]:
    """May this client perform an action in `scope`? Returns (allowed, message)."""
    with _lock:
        record = _load().get("clients", {}).get(key)
    if not isinstance(record, dict):
        return False, "该程序尚未请求过访问，请在控制台的「智能体授权」中处理。"
    state = record.get("state")
    if state == "pending":
        return False, "该程序正在等待你在控制台「智能体授权」中批准。"
    if state != "approved":
        return False, "该程序的访问已被拒绝或撤销；如需放行，请在控制台「智能体授权」中批准。"
    if scope not in (record.get("scopes") or []):
        return False, f"该程序未被授予「{SCOPES.get(scope, scope)}」范围，请在控制台调整授权范围。"
    return True, ""


# MCP 只使用这几个端点；其余一律要求控制台会话（代理不能借道读取管理接口）。
_SCOPE_RULES: list[tuple[str, str, str]] = [
    ("GET", r"^/v1/resource-types/?$", "catalog"),
    ("GET", r"^/v1/actions/?$", "catalog"),
    ("GET", r"^/v1/scenario-slices/?$", "catalog"),
    ("GET", r"^/v1/scenario-slices/[^/]+/?$", "catalog"),
    ("GET", r"^/v1/scenario-slices/[^/]+/policies/?$", "rules"),
    ("GET", r"^/v1/authorizations/?$", "rules"),
    ("GET", r"^/v1/decisions/?$", "decisions"),
    ("GET", r"^/v1/principals/?$", "principals"),
    ("POST", r"^/v1/decisions/evaluate/?$", "check"),
    ("POST", r"^/v1/scenario-slices/[^/]+/preview/?$", "preview"),
    ("POST", r"^/v1/scenario-slices/[^/]+/feedback/?$", "feedback"),
]


def scope_for_request(method: str, path: str) -> str | None:
    """The scope required by an agent request, or None when agents may not use it."""
    for rule_method, pattern, scope in _SCOPE_RULES:
        if method.upper() == rule_method and re.match(pattern, path):
            return scope
    return None
