import json
from pathlib import Path
from typing import Any
import os


APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PERSONAL_ONTOLOGY_DATA", APP_DIR / "data")).expanduser()
TOKEN_FILE = Path(os.environ.get("PERSONAL_ONTOLOGY_TOKEN_FILE", DATA_DIR / "api-token"))
GRAPH_FILE = DATA_DIR / "ontology.ttl"
CONTAINER_FILE = DATA_DIR / "ontology.po.json"
SESSION_TOKEN_FILE = DATA_DIR / "session-token"
MODEL_CONFIG_FILE = DATA_DIR / "model-service.json"
MODEL_KEY_FILE = DATA_DIR / "model-service.key"
SETTINGS_FILE = DATA_DIR / "settings.json"

SUPPORTED_LANGUAGES = ("zh", "en")


def read_settings() -> dict:
    """Read data/settings.json (non-sensitive runtime preferences)."""
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def stored_language() -> str | None:
    """The language the user explicitly chose, or None when they never set one."""
    language = str(read_settings().get("display_language") or "").strip().lower()
    return language if language in SUPPORTED_LANGUAGES else None


def normalize_language(value: Any) -> str | None:
    """Collapse a system/browser locale ("en-US", "zh-Hans-CN") to "en" | "zh"."""
    text = str(value or "").strip().lower()
    if not text: return None
    if text.startswith("zh") or "chinese" in text: return "zh"
    if text.startswith("en") or "english" in text: return "en"
    return None


def display_language(hint: Any = None) -> str:
    """Precedence: request language -> stored user setting -> Chinese.

    前端已在浏览器侧解析好优先级（用户设置或系统语言），并把它放进
    `X-Display-Language` 请求头。因此**请求头优先**：否则用户在界面上切到英文后，
    后端仍按落盘的旧设置返回中文——本项目曾因此让数据标签、授权范围与后端消息的
    本地化全部形同虚设。
    """
    return normalize_language(hint) or stored_language() or "zh"
COMMON_PASSWORDS_FILE = APP_DIR / "assets" / "common-passwords.txt"
SHAPES_FILE = APP_DIR / "ontology" / "shapes.ttl"
PROPERTIES_FILE = APP_DIR / "ontology" / "personal-properties.ttl"
WEB_DIR = APP_DIR / "web"
HOST = os.environ.get("PERSONAL_ONTOLOGY_HOST", "127.0.0.1")
PORT = int(os.environ.get("PERSONAL_ONTOLOGY_PORT", "8765"))
BACKEND_PORT = int(os.environ.get("PERSONAL_ONTOLOGY_BACKEND_PORT", "8766"))
MANAGER_PORT = int(os.environ.get("PERSONAL_ONTOLOGY_MANAGER_PORT", "8765"))
# 跨机使用时指向 SSH 隧道在本机的出口，例如 http://127.0.0.1:8765
MANAGER_URL_EXPLICIT = "PERSONAL_ONTOLOGY_MANAGER_URL" in os.environ
MANAGER_URL = os.environ.get("PERSONAL_ONTOLOGY_MANAGER_URL", f"http://127.0.0.1:{MANAGER_PORT}").rstrip("/")
# 解锁期会话令牌：默认从 data/session-token 读取；跨机时由环境变量提供（该文件只在原型机上）
# 额外允许的浏览器来源（跨机/公网访问时用）。逗号分隔，如：
#   PERSONAL_ONTOLOGY_ALLOWED_ORIGINS="https://ontology.example.com"
# 留空时只允许本机回环来源，以及"与请求 Host 同源"的来源（经反向代理时最常见）。
ALLOWED_ORIGINS = [x.strip().rstrip("/") for x in os.environ.get("PERSONAL_ONTOLOGY_ALLOWED_ORIGINS", "").split(",") if x.strip()]

SESSION_TOKEN_ENV = "PERSONAL_ONTOLOGY_SESSION_TOKEN"
