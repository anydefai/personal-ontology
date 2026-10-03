#!/usr/bin/env bash
# 在【远端机器】上运行：取回原型机的解锁令牌，并以 stdio 方式启动 MCP 服务。
#
# 智能体客户端（WorkBuddy / Muse Code）把 MCP 配置的 command 指向本脚本即可，
# 不要直接指向 python —— 那样拿不到令牌。
#
# 前置条件（见 docs/06-remote-agent.md）：
#   1. 已把 backend/{__init__,config,mcp_server}.py 复制到远端（纯标准库，无需 pip 安装）
#   2. 已在另一个终端建立隧道：
#        ssh -N -L 8765:127.0.0.1:8765 <你的Mac>
#   3. 原型机上的控制台已用登录密码解锁（本体锁定期间本脚本会明确报错退出）
#
# 可用环境变量覆盖：
#   PO_REMOTE        原型机的 ssh 目标，例如 user@example-host.local   （必填）
#   PO_REMOTE_HOME   原型机上的安装目录名，默认 personal-ontology
#   PO_LOCAL_PORT    隧道在本机的入口端口，默认 8765
#   PO_MCP_HOME      远端存放 backend/ 的目录，默认 ~/personal-ontology-mcp
#   PO_PYTHON        远端解释器，默认 python3（必须是 3.11 或更新）
#   PO_SSH_OPTS      额外的 ssh 选项
set -euo pipefail

REMOTE="${PO_REMOTE:-}"
REMOTE_HOME="${PO_REMOTE_HOME:-personal-ontology}"
LOCAL_PORT="${PO_LOCAL_PORT:-8765}"
MCP_HOME="${PO_MCP_HOME:-$HOME/personal-ontology-mcp}"
PYTHON="${PO_PYTHON:-python3}"
# 不用数组：macOS 自带 bash 3.2 在 set -u 下展开空数组会报 unbound variable
SSH_OPTS="${PO_SSH_OPTS:-}"

if [[ -z "$REMOTE" ]]; then
  echo "未设置 PO_REMOTE（原型机的 ssh 目标，例如 user@example-host.local）。" >&2
  exit 1
fi

# 0) 解释器版本：MCP 服务用到 3.10+ 的类型语法，3.11 起才有完整支持。
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "找不到解释器 $PYTHON；可用 PO_PYTHON=python3.11 指定。" >&2
  exit 1
fi
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "需要 Python 3.11 或更新版本；当前 $PYTHON 是 $("$PYTHON" --version 2>&1)。" >&2
  echo "可用 PO_PYTHON=python3.11 指定一个较新的解释器。" >&2
  exit 1
fi

# 1) 隧道是否就绪。用公开的健康检查端点，不需要凭据。
if ! curl -s -m 3 "http://127.0.0.1:${LOCAL_PORT}/manager/health" >/dev/null 2>&1; then
  echo "SSH 隧道未就绪：请先在另一个终端运行" >&2
  echo "    ssh -N -L ${LOCAL_PORT}:127.0.0.1:8765 ${REMOTE}" >&2
  exit 1
fi

# 2) 取回解锁期令牌。它在每次解锁时重新生成，因此这里每次都取。
TOKEN="$(ssh -o BatchMode=yes $SSH_OPTS "$REMOTE" "cat ~/${REMOTE_HOME}/data/session-token 2>/dev/null" || true)"
TOKEN="$(echo "$TOKEN" | tr -d '[:space:]')"
if [[ -z "$TOKEN" ]]; then
  echo "本体当前处于锁定状态。请在那台 Mac 的控制台用登录密码解锁后重试。" >&2
  exit 1
fi

# 3) 以 stdio 方式启动 MCP 服务；令牌与基址通过环境变量传入。
export PERSONAL_ONTOLOGY_SESSION_TOKEN="$TOKEN"
export PERSONAL_ONTOLOGY_MANAGER_URL="http://127.0.0.1:${LOCAL_PORT}"
export PYTHONPATH="${MCP_HOME}${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" -m backend.mcp_server
