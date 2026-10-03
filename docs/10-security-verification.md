# 安全措施清单与验证方法

本文逐条列出当前版本的安全保护措施，并给出**你可以自己运行的验证命令**。

不想逐条跑，直接执行这一条，它会逐项检查并汇总：

```bash
bash ~/personal-ontology/scripts/verify-security.sh
```

下面每条说明三件事：措施是什么、命令怎么跑、预期看到什么。命令默认在 `~/personal-ontology`
目录下执行，**都不需要登录口令**。

## 1. 数据落盘：整体加密

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 1.1 | 本体与模型配置整体存放在单个加密容器 | `ls ~/personal-ontology/data/` | 只有 `ontology.po.json` 及日志/会话文件；**没有** `.ttl` 或明文 JSON 本体 |
| 1.2 | 容器内容不可读 | `more ~/personal-ontology/data/ontology.po.json` | 只见 base64 密文与元数据，**看不到任何中文、字段名或 API Key**（空格翻页，`q` 退出） |
| 1.3 | 密钥派生：PBKDF2-HMAC-SHA256，2,000,000 次 | `python3 -c "import json;d=json.load(open('data/ontology.po.json'));print([(n,b['kdf']['name'],b['kdf']['iterations']) for n,b in d['sections'].items()])"` | 两个区段均为 `pbkdf2-hmac-sha256` / `2000000` |
| 1.4 | 对称加密：AES-256-GCM | 同上，改打印 `b['cipher']['name']` | `AES-256-GCM` |
| 1.5 | 两个区段独立盐与 nonce（密钥分离、不复用 nonce） | 观察 1.3 输出中的 `salt` 与 `nonce` | `ontology` 与 `model_service` 的值**互不相同** |
| 1.6 | 密文绑定 AAD：被挪用或篡改即解密失败 | `grep -n "def section_aad" -A 14 backend/vault.py` | AAD 由区段名、版本、盐、迭代数、nonce 拼接而成 |
| 1.7 | 写入原子（临时文件 + 替换） | `grep -n "os.replace" backend/vault.py` | 存在 `os.replace`（同目录 rename 是原子的） |
| 1.8 | 权限：目录 0700、容器 0600 | `ls -ld data; ls -l data/ontology.po.json` | `drwx------` 与 `-rw-------` |
| 1.9 | 解密密钥不落盘 | `ls data/*.key` | `No such file or directory` |

## 2. API Key 与模型配置

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 2.1 | 模型配置存在容器的 `model_service` 区段 | `python3 -c "import json;print(list(json.load(open('data/ontology.po.json'))['sections']))"` | `['ontology', 'model_service']` |
| 2.2 | **磁盘上不存在 API Key 明文** | `grep -c "sk-" data/ontology.po.json` | `0` |
| 2.3 | 不存在明文 `api_key` 字段 | `grep -c '"api_key"' data/ontology.po.json` | `0` |
| 2.4 | 没有独立的配置文件与密钥文件 | `ls data/model-service.key data/model-service.json` | 两者均不存在 |
| 2.5 | Key 在区段内再加密一层 | `grep -n "api_key_encrypted" backend/model_service.py` | 写入用 `_cipher().encrypt(...)`，读取时解密 |
| 2.6 | 明文只存在于解锁期的内存 | 见 §11 | 无法从磁盘证明，属于设计边界 |

## 3. 口令与会话

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 3.1 | 口令至少 8 位、含至少 3 类字符 | `grep -n "len(password) < 8" backend/api.py` | 存在该校验 |
| 3.2 | 归一化后再比对（挡住 `Password123!`） | `grep -n "strip(" backend/api.py` | 可见「转小写、去尾数字与符号」的归一化 |
| 3.3 | 常见口令黑名单随包安装 | `wc -l assets/common-passwords.txt` | `10004` |
| 3.4 | 磁盘上没有口令 | `grep -rl password data/ \| grep -v '\.po\.json'` | 无输出 |
| 3.5 | 会话令牌只在解锁期存在 | `ls data/session-token` → 在控制台**锁定** → 再 `ls` | 解锁时存在（0600，供本机 MCP 子进程），锁定后消失 |
| 3.6 | 空闲自动锁定 | `cat data/settings.json` | `session_timeout_minutes` 不为 `0`（默认 30 分钟） |
| 3.7 | 改口令会重新加密容器 | 改口令前后对比 `stat -f %m data/ontology.po.json` 与 1.3 输出中的 `salt` | 时间戳与盐都会变化 |

## 4. 网络暴露面

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 4.1 | 只监听回环地址 | `lsof -nP -iTCP -sTCP:LISTEN \| grep -E "8765\|8766"` | `127.0.0.1:8765` 与 `127.0.0.1:8766` |
| 4.2 | 没有对外监听 | 同上 | 不出现 `0.0.0.0` 或局域网地址 |
| 4.3 | 跨源请求被拒绝 | `curl -s -o /dev/null -w '%{http_code}' -H 'Origin: https://evil.example' http://127.0.0.1:8765/v1/principals` | `403` |
| 4.4 | 未携带凭据的请求被拒绝 | `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/v1/principals` | `401` |
| 4.5 | 智能体接入走 Unix 域套接字，不开放网络端口 | `ls -l data/agent.sock` | `srw-------` 套接字文件 |

## 5. 智能体身份与授权

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 5.1 | 用对端进程凭据识别身份 | `grep -nE "^def (peer_pid\|peer_uid\|executable_path\|command_line)" backend/peercred.py` | 四个函数都存在 |
| 5.2 | 没有可被拷走复用的令牌文件 | `ls data/ \| grep -i token` | 只有解锁期的 `session-token`（见 3.5） |
| 5.3 | 逐能力项授权，并区分待批准 | 控制台「智能体授权」 | 分「等待你批准 / 已授权 / 已拒绝」三区 |
| 5.4 | 未申请过的程序不静默放行 | `grep -n "尚未请求过访问" backend/agent_access.py` | 存在该分支 |

## 6. 判定引擎

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 6.1 | 默认拒绝 | `~/personal-ontology/.venv/bin/python tests/test_policy_actions.py` | `7/7 项通过` |
| 6.2 | 未知操作符、未注册约束不放行 | `grep -n "return False" backend/store.py \| head` | 未知类型分支返回 `False` |
| 6.3 | `draft` / `suspended` 永不参与放行 | `grep -n "policy_status" backend/store.py \| head` | 非 `active` 直接不放行 |
| 6.4 | 正则类匹配器默认禁用 | `grep -n "regex" backend/store.py` | 相关分支被禁用 |
| 6.5 | 授权检查不执行实际操作 | 控制台「快速判定」 | 只返回判定与审计记录，不调用外部服务 |

## 7. 审计与可回溯

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 7.1 | 每次判定都留档 | 控制台「判定记录」 | 有记录，含时间与结果 |
| 7.2 | 记录含执行时的规则引用与快照 | 展开任一条判定记录 | 可回溯到规则版本与执行 ID |
| 7.3 | 场景实例更新保留用户原话与前后值 | 控制台「场景实例」→ 修订记录 | 含用户原话、字段前后值、时间与实例版本 |

## 8. 可用性与恢复

| # | 措施 | 验证命令 | 预期结果 |
|---|---|---|---|
| 8.1 | 控制台与治理后端是两个进程 | `lsof -nP -iTCP -sTCP:LISTEN \| grep -E "8765\|8766"` | 两个端口各自有进程 |
| 8.2 | 后端可由控制台重启 | 控制台「服务监控」→ 停止 / 启动 | 后端停止后控制台仍可用 |
| 8.3 | 备份只需要一个文件 | `ls -l data/ontology.po.json` | 单文件即全部数据 |

## 9. 自动化测试（与上表对应）

```bash
cd ~/personal-ontology
for t in test_vault test_api_auth test_policy_actions test_agent_access test_origin_policy; do
  .venv/bin/python "tests/$t.py" | tail -1
done
```

| 测试 | 覆盖的安全面 |
|---|---|
| `test_vault.py`（37 项） | 容器加密、口令派生、AAD 绑定、原子写、错口令拒绝 |
| `test_api_auth.py`（42 项） | 鉴权、会话、口令策略、初始设置 |
| `test_policy_actions.py`（7 项） | 默认拒绝、按动作限定 |
| `test_agent_access.py`（24 项） | 智能体能力项与批准流程 |
| `test_origin_policy.py`（12 项） | 同源校验 |

## 10. 这些**无法**用命令证明（务必一起读）

- **解锁期间明文在内存里。** 能读取后端进程内存的恶意程序已在本模型之外；本文的"加密"只保证**落盘**安全。
- **它不是沙箱。** 判定引擎只做授权裁决，不拦截智能体的实际操作；代理必须主动调用并遵守结果。
- **没有 TLS。** 设计前提是本机回环，不要跨网络暴露。
- **弱口令仍是最大风险。** 2,000,000 次迭代抬高离线爆破成本，但不等于不可破；口令请存进密码管理器。
- **容器元数据是明文**（区段名、算法、迭代数、盐、nonce）。这是设计如此：解密需要由口令派生的密钥。
- **解锁期间存在 `data/session-token`**（0600，供本机 MCP 子进程读取），锁定后删除。
- **`data/settings.json` 是明文**，只存放界面偏好（语言、跨机开关、空闲锁定时长）。
- **旧版回退文件不会自动删除。** 若 `data/model-service.json` 或 `model-service.key` 存在，说明当前走的是回退路径，可人工删除。
