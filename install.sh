#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${PERSONAL_ONTOLOGY_HOME:-$HOME/personal-ontology}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "错误：当前一键安装脚本使用 macOS LaunchAgent，仅支持 macOS。"
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "错误：需要 Python 3.11 或更新版本。"
  exit 1
fi
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
  echo "错误：当前 Python 为 $PYTHON_VERSION；请安装 Python 3.11 或更新版本。"
  exit 1
fi

mkdir -p "$INSTALL_DIR/backend" "$INSTALL_DIR/ontology" "$INSTALL_DIR/web" "$INSTALL_DIR/data" \
         "$INSTALL_DIR/assets" "$INSTALL_DIR/tests" "$INSTALL_DIR/scripts" "$INSTALL_DIR/schemas" "$INSTALL_DIR/docs"
chmod 700 "$INSTALL_DIR/data"
cp "$SOURCE_DIR/backend/"*.py "$INSTALL_DIR/backend/"
cp "$SOURCE_DIR/ontology/"*.ttl "$INSTALL_DIR/ontology/"
cp "$SOURCE_DIR/web/"* "$INSTALL_DIR/web/"
cp "$SOURCE_DIR/assets/"* "$INSTALL_DIR/assets/"
cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
cp "$SOURCE_DIR/README.md" "$INSTALL_DIR/README.md"
# README 里指到的目录都要随安装一起就位，否则全新安装的用户按文档操作会找不到文件。
cp "$SOURCE_DIR/tests/"*.py "$INSTALL_DIR/tests/" 2>/dev/null || true
cp "$SOURCE_DIR/scripts/"* "$INSTALL_DIR/scripts/" 2>/dev/null || true
cp "$SOURCE_DIR/schemas/"*.json "$INSTALL_DIR/schemas/" 2>/dev/null || true
cp -R "$SOURCE_DIR/docs/." "$INSTALL_DIR/docs/" 2>/dev/null || true
for extra in README.en.md CHANGELOG.md CHANGELOG.en.md LICENSE install.sh; do
  [ -f "$SOURCE_DIR/$extra" ] && cp "$SOURCE_DIR/$extra" "$INSTALL_DIR/"
done
if [[ ! -x "$INSTALL_DIR/.venv/bin/python" ]]; then python3 -m venv "$INSTALL_DIR/.venv"; fi
"$INSTALL_DIR/.venv/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt"

cat > "$INSTALL_DIR/start.sh" <<'START'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="personalontology.personal-ontology"
BACKEND_LABEL="$LABEL.backend"
DOMAIN="gui/$(id -u)"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
BACKEND_AGENT="$HOME/Library/LaunchAgents/$BACKEND_LABEL.plist"
if [[ ! -f "$AGENT" || ! -f "$BACKEND_AGENT" ]]; then echo "服务管理器尚未安装，请再次运行 install.sh。"; exit 1; fi
launchctl kickstart -k "$DOMAIN/$LABEL" 2>/dev/null || launchctl bootstrap "$DOMAIN" "$AGENT"
launchctl kickstart -k "$DOMAIN/$BACKEND_LABEL" 2>/dev/null || launchctl bootstrap "$DOMAIN" "$BACKEND_AGENT"
for _ in {1..30}; do
  if curl --silent --fail "http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}/manager/health" >/dev/null && curl --silent --fail "http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}/health" >/dev/null; then
    echo "Personal Ontology 已启动：http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}"
    exit 0
  fi
  sleep 1
done
echo "启动失败；查看管理界面与日志：$ROOT/data/server.log"
exit 1
START

cat > "$INSTALL_DIR/stop.sh" <<'STOP'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="personalontology.personal-ontology.backend"
DOMAIN="gui/$(id -u)"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "$DOMAIN" "$AGENT" 2>/dev/null || true
echo "治理后端已停止；服务监控页面仍可用于重新启动：http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}"
STOP

cat > "$INSTALL_DIR/status.sh" <<'STATUS'
#!/usr/bin/env bash
set -euo pipefail
PORT="${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}"
# 状态查询不需要凭据：/manager/health 与 /health 都是公开端点。
manager="$(curl -s -m 5 "http://127.0.0.1:${PORT}/manager/health" || echo '未响应')"
backend="$(curl -s -m 5 "http://127.0.0.1:${PORT}/health" || echo '未响应')"
echo "管理器：${manager}"
echo "治理后端：${backend}"
echo "（若显示 \"locked\":true，请打开控制台输入登录密码解锁。）"
STATUS

chmod 700 "$INSTALL_DIR/start.sh" "$INSTALL_DIR/stop.sh" "$INSTALL_DIR/status.sh"
# 不再生成 data/api-token：控制台改用登录密码，容器密钥由用户口令派生（见 docs/05）。
AGENT_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENT_DIR"
AGENT_FILE="$AGENT_DIR/personalontology.personal-ontology.plist"
BACKEND_LABEL="personalontology.personal-ontology.backend"
BACKEND_AGENT_FILE="$AGENT_DIR/$BACKEND_LABEL.plist"
PERSONAL_ONTOLOGY_HOME="$INSTALL_DIR" \
PERSONAL_ONTOLOGY_MANAGER_PORT="${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}" \
PERSONAL_ONTOLOGY_BACKEND_PORT="${PERSONAL_ONTOLOGY_BACKEND_PORT:-8766}" \
SCENARIO_LLM_BASE_URL="${SCENARIO_LLM_BASE_URL:-}" \
SCENARIO_LLM_MODEL="${SCENARIO_LLM_MODEL:-}" \
SCENARIO_LLM_API_KEY="${SCENARIO_LLM_API_KEY:-}" \
AGENT_FILE="$AGENT_FILE" BACKEND_AGENT_FILE="$BACKEND_AGENT_FILE" \
"$INSTALL_DIR/.venv/bin/python" - <<'PY'
import os, plistlib
from pathlib import Path

root = Path(os.environ["PERSONAL_ONTOLOGY_HOME"])
manager_file = Path(os.environ["AGENT_FILE"])
backend_file = Path(os.environ["BACKEND_AGENT_FILE"])
legacy = {}
for old_file in (manager_file, backend_file):
    try:
        old = plistlib.load(old_file.open("rb"))
        legacy.update(old.get("EnvironmentVariables", {}))
    except (OSError, ValueError, plistlib.InvalidFileException):
        pass
keys = ("SCENARIO_LLM_BASE_URL", "SCENARIO_LLM_MODEL", "SCENARIO_LLM_API_KEY")
legacy = {k: os.environ.get(k) or legacy.get(k, "") for k in keys}

# Move valid legacy environment settings into the encrypted local settings file.
migrated = False
if legacy["SCENARIO_LLM_BASE_URL"] and legacy["SCENARIO_LLM_MODEL"]:
    try:
        import sys
        sys.path.insert(0, str(root))
        from backend.config import MODEL_CONFIG_FILE
        from backend.model_service import save_settings
        if not MODEL_CONFIG_FILE.exists():
            save_settings(legacy["SCENARIO_LLM_BASE_URL"], legacy["SCENARIO_LLM_MODEL"], legacy["SCENARIO_LLM_API_KEY"])
        migrated = True
    except Exception:
        migrated = False

if not migrated:
    fallback = {k:v for k,v in legacy.items() if v}
else:
    fallback = {}

def write(path, label, module, port, log):
    document = {
        "Label": label,
        "ProgramArguments": [str(root / ".venv/bin/uvicorn"), module, "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(root / "data" / log),
        "StandardErrorPath": str(root / "data" / log),
        "EnvironmentVariables": {
            "PERSONAL_ONTOLOGY_MANAGER_PORT": os.environ["PERSONAL_ONTOLOGY_MANAGER_PORT"],
            "PERSONAL_ONTOLOGY_BACKEND_PORT": os.environ["PERSONAL_ONTOLOGY_BACKEND_PORT"],
            **fallback,
        },
    }
    with path.open("wb") as stream:
        plistlib.dump(document, stream, sort_keys=False)
    path.chmod(0o600)

write(manager_file, "personalontology.personal-ontology", "backend.manager:app", os.environ["PERSONAL_ONTOLOGY_MANAGER_PORT"], "manager.log")
write(backend_file, "personalontology.personal-ontology.backend", "backend.api:app", os.environ["PERSONAL_ONTOLOGY_BACKEND_PORT"], "server.log")
PY
launchctl bootout "gui/$(id -u)" "$BACKEND_AGENT_FILE" >/dev/null 2>&1 || true
launchctl bootout "gui/$(id -u)" "$AGENT_FILE" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$AGENT_FILE"
launchctl bootstrap "gui/$(id -u)" "$BACKEND_AGENT_FILE"
launchctl kickstart -k "gui/$(id -u)/personalontology.personal-ontology"
launchctl kickstart -k "gui/$(id -u)/$BACKEND_LABEL"
for _ in {1..30}; do
  if curl --silent --fail "http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}/manager/health" >/dev/null && curl --silent --fail "http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}/health" >/dev/null; then break; fi
  sleep 1
done
curl --silent --show-error --fail "http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}/health" >/dev/null
echo
echo "安装目录：$INSTALL_DIR"
echo "控制台地址：http://127.0.0.1:${PERSONAL_ONTOLOGY_MANAGER_PORT:-8765}"
echo "首次打开控制台时需要设置登录密码；本体数据会自动迁移进加密容器 ontology.po.json"
echo "管理器日志：$INSTALL_DIR/data/manager.log"
echo "后端日志：$INSTALL_DIR/data/server.log"
echo "停止服务：$INSTALL_DIR/stop.sh"
echo "查看日志：$INSTALL_DIR/data/server.log"
