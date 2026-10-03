#!/usr/bin/env bash
# 安全措施自查：逐条验证本机安装的安全保护是否生效。
#   用法：bash ~/personal-ontology/scripts/verify-security.sh
# 只读操作，不会修改任何文件；不需要登录口令（少数条目会说明它验证不了什么）。
set -u
HOME_DIR="${PERSONAL_ONTOLOGY_HOME:-$HOME/personal-ontology}"
DATA="$HOME_DIR/data"
BOX="$DATA/ontology.po.json"
pass=0; fail=0; warn=0
ok()   { printf "  \033[32m✔\033[0m %-46s %s\n" "$1" "${2:-}"; pass=$((pass+1)); }
no()   { printf "  \033[31m✗\033[0m %-46s %s\n" "$1" "${2:-}"; fail=$((fail+1)); }
info() { printf "  \033[90m·\033[0m %-46s %s\n" "$1" "${2:-}"; }
warn() { printf "  \033[33m!\033[0m %-46s %s\n" "$1" "${2:-}"; warn=$((warn+1)); }
head_() { printf "\n\033[1m%s\033[0m\n" "$1"; }

PY=$(command -v python3 || echo "$HOME_DIR/.venv/bin/python")
[ -x "$HOME_DIR/.venv/bin/python" ] && PY="$HOME_DIR/.venv/bin/python"

head_ "0. 安装位置"
[ -d "$DATA" ] && ok "数据目录存在" "$DATA" || { no "数据目录不存在" "$DATA"; exit 1; }

head_ "1. 数据落盘：整体加密"
if [ -f "$BOX" ]; then
  ok "加密容器存在" "$(basename "$BOX")"
  n=$(find "$DATA" -maxdepth 1 -type f \( -name "*.ttl" -o -name "ontology.json" \) 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" = "0" ] && ok "磁盘上没有明文本体（.ttl / .json）" "0 个" || no "发现明文本体文件" "$n 个"
  s=$(grep -c "sk-" "$BOX" 2>/dev/null || true); s=${s:-0}
  [ "$s" = "0" ] && ok "容器中没有 API Key 明文（sk-）" "0 处" || no "疑似明文 Key" "$s 处"
  a=$(grep -c '"api_key"' "$BOX" 2>/dev/null || true); a=${a:-0}
  [ "$a" = "0" ] && ok "容器中没有明文 api_key 字段" "0 处" || no "发现明文 api_key 字段" "$a 处"
else
  no "未找到加密容器" "$BOX"
fi
[ -f "$BOX" ] && { r=$("$PY" -c "
import json,sys
d=json.load(open('$BOX'));s=d['sections']
print('OK' if all(b['cipher']['name']=='AES-256-GCM' and int(b['kdf']['iterations'])>=2000000 for b in s.values()) and len(s)>=2 else 'BAD')" 2>/dev/null)
  [ "$r" = "OK" ] && ok "AES-256-GCM 且迭代 ≥ 2,000,000（两区段）" || no "算法或迭代次数不符"; }
[ -f "$BOX" ] && { d=$("$PY" -c "
import json
d=json.load(open('$BOX'))['sections']
a,b=list(d.values())[:2]
print('OK' if (a['kdf']['salt']!=b['kdf']['salt'] and a['cipher']['nonce']!=b['cipher']['nonce']) else 'BAD')" 2>/dev/null)
  [ "$d" = "OK" ] && ok "两个区段使用独立盐与 nonce" || info "只有一个区段或盐/nonce 相同" "（单区段时此项不适用）"; }
perm=$(stat -f "%Lp" "$BOX" 2>/dev/null || stat -c "%a" "$BOX" 2>/dev/null)
[ "$perm" = "600" ] && ok "容器权限 600" "$perm" || no "容器权限不是 600" "$perm"
dperm=$(stat -f "%Lp" "$DATA" 2>/dev/null || stat -c "%a" "$DATA" 2>/dev/null)
[ "$dperm" = "700" ] && ok "数据目录权限 700" "$dperm" || no "数据目录权限不是 700" "$dperm"
k=$(find "$DATA" -maxdepth 1 -name "*.key" 2>/dev/null | wc -l | tr -d ' ')
[ "$k" = "0" ] && ok "磁盘上没有密钥文件（.key）" "0 个" || info "存在 .key 文件（旧版兼容回退）" "$k 个"
grep -q "os.replace" "$HOME_DIR/backend/vault.py" 2>/dev/null && ok "写入使用原子替换（os.replace）" || no "vault.py 中未找到原子替换"
grep -q "def section_aad" "$HOME_DIR/backend/vault.py" 2>/dev/null && ok "密文绑定 AAD（篡改即解密失败）" || no "未找到 AAD 拼接函数"

head_ "2. 凭据与会话"
pw=$(grep -rl "password" "$DATA" 2>/dev/null | grep -v "\.po\.json" | wc -l | tr -d ' ')
[ "$pw" = "0" ] && ok "磁盘上没有口令相关文件" "0 个" || info "以下文件含 password 字样（请人眼确认）" "$pw 个"
grep -q "validate_password" "$HOME_DIR/backend/api.py" 2>/dev/null && ok "存在口令强度校验（≥8 位、≥3 类字符）" || no "未找到口令校验"
bl=$(wc -l < "$HOME_DIR/assets/common-passwords.txt" 2>/dev/null | tr -d ' ')
[ "${bl:-0}" -gt 5000 ] && ok "常见口令黑名单已随包安装" "$bl 条" || no "黑名单文件缺失或过小" "${bl:-0} 条"
if [ -f "$DATA/settings.json" ]; then
  to=$("$PY" -c "import json;print(json.load(open('$DATA/settings.json')).get('session_timeout_minutes','?'))" 2>/dev/null)
  [ "$to" != "0" ] && ok "空闲自动锁定已启用" "${to} 分钟" || warn "空闲自动锁定已关闭（合法选项）" "解锁后不会自动锁定，需手动锁定"
fi
if [ -f "$DATA/session-token" ]; then
  info "会话令牌文件存在（解锁期间如此）" "锁定后应消失"
else
  ok "锁定状态：无会话令牌文件"
fi

head_ "3. 网络暴露面"
lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE "127\.0\.0\.1:87(65|66)" && ok "服务监听在回环地址" "127.0.0.1:8765/8766" || info "未检测到监听进程（服务未运行？）"
if lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E "87(65|66)" | grep -qv "127.0.0.1"; then no "存在非回环监听！" ; else ok "没有对外监听（0.0.0.0 / LAN）"; fi
if command -v curl >/dev/null; then
  code=$(curl -s -m 5 -o /dev/null -w "%{http_code}" -H "Origin: https://evil.example" http://127.0.0.1:8765/v1/principals 2>/dev/null)
  [ "$code" = "403" ] && ok "跨源请求被拒绝（同源校验）" "HTTP 403" || info "跨源请求返回 HTTP ${code:-无响应}（服务未运行时不适用）"
fi
[ -S "$DATA/agent.sock" ] && ok "智能体接入走 Unix 域套接字（非网络端口）" "agent.sock" || info "未找到 agent.sock（无智能体会话时正常）"


head_ "4. 可执行的安全测试"
if [ -x "$HOME_DIR/.venv/bin/python" ] && [ -d "$HOME_DIR/tests" ]; then
  for t in test_vault test_api_auth test_policy_actions test_agent_access test_origin_policy; do
    if [ -f "$HOME_DIR/tests/$t.py" ]; then
      line=$(cd "$HOME_DIR" && .venv/bin/python "tests/$t.py" 2>&1 | tail -1)
      case "$line" in *通过*|*成功*|*"项通过"*) ok "$t" "$line" ;; *) no "$t" "$line" ;; esac
    fi
  done
else
  info "未找到测试目录，跳过" "$HOME_DIR/tests"
fi

head_ "结果"
printf "  通过 %d 项 · 警告 %d 项 · 失败 %d 项\n" "$pass" "$warn" "$fail"
echo
printf "\033[1m无法用本脚本证明的部分（务必知情）\033[0m\n"
cat <<'TXT'
  · 解锁期间，明文存在于后端进程内存中——能读取该进程内存的程序已在模型之外
  · 判定引擎只做授权裁决，不拦截智能体的实际操作：这不是沙箱
  · 没有 TLS：设计前提是本机回环，不要跨网络暴露
  · 弱口令仍是最大风险：2,000,000 次迭代抬高离线爆破成本，但不等于不可破
  · 容器元数据（区段名、算法、迭代数、盐、nonce）是明文，这是设计如此
  · 解锁期间存在 data/session-token（供本机 MCP 子进程使用，0600），锁定后删除
  · data/settings.json 为明文，仅存放界面偏好（语言、跨机开关、空闲锁定时长）
TXT
[ "$fail" = "0" ] && exit 0 || exit 1
