"""浏览器来源校验（CSRF 防护）—— 管理器与后端共用。

动机：两处中间件原先各自硬编码只允许 http://localhost / http://127.0.0.1，
经反向代理或直连公网地址访问时，登录请求带 Origin=https://域名 被 403
（"Origin not allowed"）。而浏览器只跟**管理器**说话，只修后端不起作用。

允许三类，且**刻意不支持通配**（放开成 * 等于取消 CSRF 防护）：
  1. 本机回环来源；
  2. 与本次请求 Host 同源（含 X-Forwarded-Host 回退）；
  3. PERSONAL_ONTOLOGY_ALLOWED_ORIGINS 显式列出的来源。
"""
from __future__ import annotations

from typing import Any, Mapping

LOOPBACK_PREFIXES = ("http://localhost", "http://127.0.0.1", "http://[::1]",
                     "https://localhost", "https://127.0.0.1", "https://[::1]")


def loopback_origin(origin: str) -> bool:
    return origin.startswith(LOOPBACK_PREFIXES)


def origin_allowed(origin: str, headers: Mapping[str, Any] | None, allowed_origins: list[str] | None = None) -> bool:
    if loopback_origin(origin):
        return True
    for candidate in allowed_origins or []:
        candidate = str(candidate).rstrip("/")
        if origin == candidate or origin.startswith(candidate + "/"):
            return True
    headers = headers or {}
    for key in ("x-forwarded-host", "host"):
        host = str(headers.get(key) or "").strip()
        if host and origin in (f"https://{host}", f"http://{host}"):
            return True
    return False
