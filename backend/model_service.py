"""Encrypted local configuration for an OpenAI-compatible model service."""
from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import DATA_DIR, MODEL_CONFIG_FILE, MODEL_KEY_FILE


class ModelServiceError(RuntimeError):
    pass


# 由 api.py 在创建 store 后注入；模型配置存放在加密容器的 model_service 段（docs/05 §6）。
_store_provider = None


def attach_store(provider) -> None:
    """注入"取当前 store"的回调，避免模块间循环导入。"""
    global _store_provider
    _store_provider = provider


def _container_section() -> bytes | None:
    """容器处于解锁态时返回 model_service 段的明文，否则返回 None。"""
    if _store_provider is None: return None
    try:
        store = _store_provider()
        if store is None or not store.unlocked: return None
        return store.vault.get_section("model_service")
    except Exception:
        return None


def _write_container_section(payload: bytes) -> bool:
    if _store_provider is None: return False
    try:
        store = _store_provider()
        if store is None or not store.unlocked: return False
        store.vault.put_section("model_service", payload)
        return True
    except Exception:
        return False


def _cipher() -> Fernet:
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    if MODEL_KEY_FILE.exists():
        return Fernet(MODEL_KEY_FILE.read_bytes().strip())
    key = Fernet.generate_key()
    try:
        fd = os.open(MODEL_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return Fernet(MODEL_KEY_FILE.read_bytes().strip())
    with os.fdopen(fd, "wb") as stream:
        stream.write(key + b"\n")
    return Fernet(key)


def _legacy() -> dict[str, str]:
    return {
        "base_url": os.environ.get("SCENARIO_LLM_BASE_URL", "").strip().rstrip("/"),
        "model": os.environ.get("SCENARIO_LLM_MODEL", "").strip(),
        "api_key": os.environ.get("SCENARIO_LLM_API_KEY", "").strip(),
        "source": "environment",
    }


def export_for_container() -> bytes:
    """迁移用：把旧配置转成容器段的明文 JSON。

    旧文件里的 API Key 由独立密钥 `model-service.key` 加密，而迁移会删除那把密钥；
    因此必须在这里解开，以明文形式放进容器段（容器本身就是加密层）。
    """
    if MODEL_CONFIG_FILE.exists():
        try:
            raw = json.loads(MODEL_CONFIG_FILE.read_text(encoding="utf-8"))
            encrypted = str(raw.get("api_key_encrypted", ""))
            key = _cipher().decrypt(encrypted.encode()).decode() if encrypted else ""
            return json.dumps({"base_url":str(raw.get("base_url","")), "model":str(raw.get("model","")),
                               "api_key":key}, ensure_ascii=False).encode("utf-8")
        except (OSError, ValueError, InvalidToken, TypeError):
            pass
    legacy = _legacy()
    return json.dumps({"base_url":legacy["base_url"], "model":legacy["model"], "api_key":legacy["api_key"]},
                      ensure_ascii=False).encode("utf-8")


def _read() -> dict[str, str]:
    section = _container_section()
    if section is not None:
        try:
            raw = json.loads(section.decode("utf-8"))
            secret = str(raw.get("api_key",""))
            if not secret and raw.get("api_key_encrypted"):
                # 兼容早期迁移版本：段内可能仍是独立密钥加密的值
                try: secret = _cipher().decrypt(str(raw["api_key_encrypted"]).encode()).decode()
                except (InvalidToken, ValueError, TypeError): secret = ""
            return {"base_url":str(raw.get("base_url","")), "model":str(raw.get("model","")),
                    "api_key":secret, "source":"container"}
        except (ValueError, AttributeError, TypeError):
            pass
    if not MODEL_CONFIG_FILE.exists():
        return _legacy()
    try:
        raw = json.loads(MODEL_CONFIG_FILE.read_text(encoding="utf-8"))
        key = _cipher().decrypt(str(raw.get("api_key_encrypted", "")).encode()).decode() if raw.get("api_key_encrypted") else ""
        return {"base_url":str(raw.get("base_url", "")), "model":str(raw.get("model", "")), "api_key":key, "source":"settings"}
    except (OSError, ValueError, InvalidToken, TypeError) as exc:
        raise ModelServiceError("本机模型服务配置无法读取；请重新保存配置。") from exc


def public_settings() -> dict[str, Any]:
    config = _read()
    return {"configured":bool(config["base_url"] and config["model"]), "base_url":config["base_url"], "model":config["model"], "has_api_key":bool(config["api_key"]), "source":config["source"]}


def validate_settings(base_url: str, model: str) -> tuple[str, str]:
    base_url, model = base_url.strip().rstrip("/"), model.strip()
    if not 1 <= len(base_url) <= 1000 or not 1 <= len(model) <= 200:
        raise ModelServiceError("请填写服务地址和模型名称。")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ModelServiceError("服务地址需为有效的 http/https 地址，不要在地址中填写账号或密钥。")
    return base_url, model


def save_settings(base_url: str, model: str, api_key: str = "", clear_api_key: bool = False) -> dict[str, Any]:
    base_url, model = validate_settings(base_url, model)
    if len(api_key) > 4096:
        raise ModelServiceError("API Key 长度超出限制。")
    current = _read()
    secret = "" if clear_api_key else (api_key.strip() or current["api_key"])
    if _write_container_section(json.dumps({"base_url":base_url, "model":model, "api_key":secret}, ensure_ascii=False).encode("utf-8")):
        return public_settings()
    raw = {"base_url":base_url, "model":model, "api_key_encrypted":_cipher().encrypt(secret.encode()).decode() if secret else ""}
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(prefix="model-service-", suffix=".json", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(raw, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, MODEL_CONFIG_FILE)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return public_settings()


def endpoint(config: dict[str, str] | None = None) -> str:
    cfg = config or _read()
    return cfg["base_url"] if cfg["base_url"].endswith("/chat/completions") else cfg["base_url"] + "/chat/completions"


def test_connection() -> dict[str, str]:
    config = _read()
    if not config["base_url"] or not config["model"]:
        raise ModelServiceError("请先填写并保存服务地址和模型名称。")
    data = json.dumps({"model":config["model"], "temperature":0, "messages":[{"role":"user", "content":"Reply with OK."}] }).encode()
    headers = {"Content-Type":"application/json"}
    if config["api_key"]:
        headers["Authorization"] = "Bearer " + config["api_key"]
    req = urllib.request.Request(endpoint(config), data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            response.read(65536)
        return {"status":"ok", "message":"连接成功，模型已响应。"}
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise ModelServiceError("认证失败，请检查 API Key 或服务权限。") from exc
        if exc.code == 404:
            raise ModelServiceError("接口或模型未找到，请检查服务地址和模型名称。") from exc
        raise ModelServiceError(f"模型服务返回 HTTP {exc.code}。") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ModelServiceError("无法连接模型服务，请检查地址、网络和服务状态。") from exc

