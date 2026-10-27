"""通讯录同步：从已连接的安卓手机拉取、解析、按 contact_id 就地更新（不产生重复）。"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

DATA_URI = "content://com.android.contacts/data"
RAW_URI = "content://com.android.contacts/raw_contacts"
GROUP_URI = "content://com.android.contacts/groups"
PROJECTION = "contact_id:mimetype:data1:data2:data3:data4:data5:data6:data7:data8:data9"


def adb_available() -> bool:
    return shutil.which("adb") is not None


def _run_adb(args: list[str], timeout: int = 120, serial: str | None = None) -> str:
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "adb failed").strip()[:300])
    return proc.stdout


def list_devices() -> list[dict[str, str]]:
    """已连接的安卓设备（用 adb 的完整序列号区分同型号手机）。"""
    out = _run_adb(["devices", "-l"])
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            model = ""
            for token in parts[2:]:
                if token.startswith("model:"):
                    model = token.split(":", 1)[1]
            devices.append({"serial": serial, "model": model})
    return devices


def device_label(serial: str | None = None) -> str:
    """设备标签：型号 + 完整序列号（序列号为空时退化为 adb 连接序号）。"""
    devs = []
    try:
        devs = list_devices()
    except Exception:                                   # noqa: BLE001
        devs = []
    if serial is None and devs:
        serial = devs[0]["serial"]
    model = ""
    try:
        model = _run_adb(["shell", "getprop", "ro.product.model"], serial=serial).strip()
    except Exception:                                   # noqa: BLE001
        model = ""
    if serial is None and devs:
        serial = devs[0]["serial"]
    if not serial:
        serial = f"device-{(len(devs) or 1)}"
    return f"{(model or 'android')} · {serial}"


def _parse_row(line: str) -> dict[str, str] | None:
    if not line.startswith("Row: "):
        return None
    body = line.split("Row: ", 1)[1]
    idx = body.find("contact_id=")
    if idx >= 0:
        body = body[idx:]
    out: dict[str, str] = {}
    for part in re.split(r",\s*(?=data\d+=|mimetype=|contact_id=)", body):
        if "=" in part:
            key, value = part.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def parse_rows(raw: str) -> list[dict[str, Any]]:
    """把 `content query` 的文本解析成联系人列表（含手机上的稳定 contact_id）。"""
    by_contact: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        row = _parse_row(line)
        if not row:
            continue
        cid = row.get("contact_id", "")
        if not cid:
            continue
        rec = by_contact.setdefault(cid, {
            "contact_id": cid, "name": "", "first": "", "last": "", "org": "", "title": "",
            "phones": [], "emails": [], "addresses": [], "notes": [], "group_ids": [],
        })
        mt = row.get("mimetype", "")
        if mt.endswith("/name"):
            rec["name"] = rec["name"] or row.get("data1", "")
            rec["first"] = rec["first"] or row.get("data2", "")
            rec["last"] = rec["last"] or row.get("data3", "")
        elif mt.endswith("/phone_v2"):
            rec["phones"].append({"number": row.get("data1", ""), "type": row.get("data2", "")})
        elif mt.endswith("/email_v2"):
            rec["emails"].append({"address": row.get("data1", ""), "type": row.get("data2", "")})
        elif mt.endswith("/postal-address_v2"):
            rec["addresses"].append({k: row.get(f"data{i}", "") for i, k in
                                     ((1, "po_box"), (2, "street"), (4, "city"), (5, "region"),
                                      (6, "postcode"), (7, "country")) if row.get(f"data{i}")})
        elif mt.endswith("/note"):
            rec["notes"].append(row.get("data1", ""))
        elif mt.endswith("/organization"):
            rec["org"] = rec["org"] or row.get("data1", "")
            rec["title"] = rec["title"] or row.get("data4", "")
        elif mt.endswith("/group_membership"):
            if row.get("data1"):
                rec["group_ids"].append(row["data1"])
    return [r for r in by_contact.values() if (r["name"] or r["org"] or r["phones"] or r["emails"])]


def parse_accounts(raw: str) -> dict[str, dict[str, str]]:
    """raw_contacts → {contact_id: {account_name, account_type}}，用于给数据打"来自哪个账户/App"的标签。"""
    out: dict[str, dict[str, str]] = {}
    for line in raw.splitlines():
        if not line.startswith("Row: "):
            continue
        body = re.sub(r"^\d+\s+", "", line.split("Row: ", 1)[1])
        fields = dict(p.split("=", 1) for p in re.split(r",\s*(?=account_|_id=)", body) if "=" in p)
        cid = fields.get("contact_id") or fields.get("_id") or ""
        if not cid:
            continue
        out[cid.strip()] = {"account_name": fields.get("account_name", "").strip(),
                            "account_type": fields.get("account_type", "").strip()}
    return out


def pull_from_phone(serial: str | None = None) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], str]:
    """从指定设备拉取并解析。返回 (联系人, 账户映射, 设备标签)。"""
    if not adb_available():
        raise RuntimeError("没有找到 adb，无法从手机同步。")
    label = device_label(serial)
    raw = _run_adb(["shell", "content", "query", "--uri", DATA_URI, "--projection", PROJECTION], serial=serial)
    accounts: dict[str, dict[str, str]] = {}
    try:
        accounts = parse_accounts(_run_adb(["shell", "content", "query", "--uri", RAW_URI,
                                            "--projection", "contact_id:account_name:account_type"],
                                           serial=serial))
    except RuntimeError:
        accounts = {}
    return parse_rows(raw), accounts, label


def upsert(store, records: list[dict[str, Any]], accounts: dict[str, dict[str, str]],
           device: str, mark_missing: bool = True) -> dict[str, int]:
    """按手机上的 contact_id 就地更新：新增 / 更新 / 未变 / 手机已删 四种结果，绝不产生重复。"""
    existing = {}
    for row in store.list("contact-records"):
        key = str(row.get("source_contact_id") or "")
        if key:
            existing[key] = row
    stats = {"created": 0, "updated": 0, "unchanged": 0, "deleted_on_phone": 0}
    pending: list[tuple[str, dict[str, Any]]] = []
    seen = set()
    for rec in records:
        cid = str(rec["contact_id"])
        seen.add(cid)
        acc = accounts.get(cid) or {}
        tags = [device] if device else []
        if acc.get("account_type"):
            tags.append(acc["account_type"])
        if acc.get("account_name"):
            tags.append(acc["account_name"])
        name = str(rec.get("name") or "").strip()
        org = str(rec.get("org") or "").strip()
        payload = {
            "display_name_zh": name or org, "display_name_en": name or org,
            "contact_org": org, "contact_title": str(rec.get("title") or ""),
            "contact_phones": rec.get("phones") or [],
            "contact_emails": rec.get("emails") or [],
            "contact_addresses": rec.get("addresses") or [],
            "contact_note": "；".join(str(x) for x in (rec.get("notes") or []))[:2000],
            "contact_group_ids": rec.get("group_ids") or [],
            "contact_source": "android-sync",
            "contact_sensitivity": "restricted",
            "source_contact_id": cid,
            "source_device": device,
            "source_account": str(acc.get("account_name") or ""),
            "contact_tags": tags,
            "from_phone_deleted": "",
        }
        old = existing.get(cid)
        if not old:
            stats["created"] += 1
            pending.append(("cr_" + __import__("uuid").uuid4().hex[:12], payload))
            continue
        same = all(str(old.get(k) or "") == str(payload[k] or "") for k in
                   ("display_name_zh", "contact_org", "contact_note"))
        same = same and [str(p.get("number")) for p in (old.get("contact_phones") or [])] == \
                        [str(p.get("number")) for p in payload["contact_phones"]]
        same = same and [str(p.get("address")) for p in (old.get("contact_emails") or [])] == \
                        [str(p.get("address")) for p in payload["contact_emails"]]
        if same:
            stats["unchanged"] += 1
        else:
            stats["updated"] += 1
            pending.append((str(old.get("id")), payload))
    if mark_missing:
        for cid, old in existing.items():
            if cid in seen:
                continue
            stats["deleted_on_phone"] += 1
            touched = {k: v for k, v in dict(old).items() if k not in {"id"}}
            touched["from_phone_deleted"] = "true"
            pending.append((str(old.get("id")), touched))
    if pending:
        store.put_many("contact-records", pending, batch_size=200)
    return stats
