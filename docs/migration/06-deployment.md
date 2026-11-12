# 06 · 部署与运维

## 1. 两套目录（这是最容易搞错的一点）

```
仓库（git）      /Users/Apple/Documents/personal-ontology       ← 改代码、提交
运行（无 git）    /Users/Apple/personal-ontology                  ← 真正在跑的进程与数据
                 ├── .venv/                  Python 3.14 虚拟环境
                 ├── backend/ web/ ontology/ assets/   （从仓库复制）
                 └── data/                   ★ 唯一的状态：容器、令牌、日志
```

**规则**：仓库里改完 → 复制到运行目录 → 重启；`data/` 永不从仓库复制、永不提交。

## 2. 环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `PERSONAL_ONTOLOGY_DATA` | `<APP_DIR>/data` | 数据目录（测试用它指向临时目录） |
| `PERSONAL_ONTOLOGY_PORT` | 8765 | manager 端口 |
| `PERSONAL_ONTOLOGY_BACKEND_PORT` | 8766 | backend 端口 |
| `PERSONAL_ONTOLOGY_HOST` | 127.0.0.1 | 绑定地址（默认只回环） |
| `PERSONAL_ONTOLOGY_ALLOWED_ORIGINS` | 空 | 额外允许的浏览器来源（跨机访问时） |
| `PERSONAL_ONTOLOGY_MANAGER_URL` | `http://127.0.0.1:8765` | 跨机/隧道场景 |
| `PERSONAL_ONTOLOGY_SESSION_TOKEN` | 空 | 跨机时用它代替 `data/session-token` |

## 3. launchd（macOS 生产）

文件：`~/Library/LaunchAgents/personalontology.personal-ontology.backend.plist`

```
Label            personalontology.personal-ontology.backend
ProgramArguments /Users/Apple/personal-ontology/.venv/bin/uvicorn
                 backend.api:app --host 127.0.0.1 --port 8766 --no-access-log
WorkingDirectory /Users/Apple/personal-ontology
RunAtLoad        true
KeepAlive        true
StandardOut/Err  /Users/Apple/personal-ontology/data/server.log
EnvironmentVariables  PERSONAL_ONTOLOGY_MANAGER_PORT=8765
```

管理命令：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/personalontology.personal-ontology.backend.plist   # 装载
launchctl kickstart -k gui/$(id -u)/personalontology.personal-ontology.backend                             # 重启
launchctl bootout   gui/$(id -u)/personalontology.personal-ontology.backend                                # 停止
```

> manager（8765）由 backend 启动时拉起（见 `manager.py` 的子进程逻辑），
> 所以只需管 backend 这一个 launchd 服务；重启 backend 会顺带重启界面。

## 4. 标准部署（改完代码之后）

```bash
cd /Users/Apple/Documents/personal-ontology

# ① 闸门（见 07，必须全绿）
# ② 前端版本号
python3 - <<'PY'
import re, pathlib
h = pathlib.Path('web/index.html'); s = h.read_text(encoding='utf-8')
s = re.sub(r'\?v=\d{8}[A-Za-z]?', '?v=20261028B', s)
s = re.sub(r'BUILD [0-9A-Za-z]+', 'BUILD 20261028B', s)
h.write_text(s, encoding='utf-8')
PY

# ③ 复制（前端 + 后端，按需）
cp web/app.js web/index.html /Users/Apple/personal-ontology/web/
cp backend/api.py backend/store.py /Users/Apple/personal-ontology/backend/

# ④ 重启（仅后端有改动时需要；纯前端不需要重启）
launchctl kickstart -k gui/$(id -u)/personalontology.personal-ontology.backend
sleep 12

# ⑤ 验证
curl -s -m 6 http://127.0.0.1:8766/health
curl -s -m 6 http://127.0.0.1:8765/ | grep -oE "BUILD [0-9A-Za-z]+"
curl -s -m 6 http://127.0.0.1:8765/assets/app.js | grep -c "<这次新增的关键字符串>"

# ⑥ 提交
git add -A && git commit -m "…" && git push origin HEAD:main
```

**重启会锁住空间**：所有用户需要重新登录。这一点每次都要在汇报里说明。

## 5. 验证脚本

```
scripts/verify-deploy.sh    部署后核对：健康、版本、关键资源、路由可用
scripts/verify-security.sh  安全核对：数据目录权限、git 是否混入数据、容器是否可读
scripts/mcp-remote.sh       MCP 远程连接（SSH 隧道）示例
```

## 6. 日志

```
data/server.log              uvicorn 与 manager 的全部输出（launchd 指定）
data/shacl-errors.log        SHACL 失败详情（api 在 ValidationError 时追加）
定位 422 的方法：tail shacl-errors.log，看"（写入 <集合>/<id>）"前缀后面的具体形状与属性。
```

## 7. 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| 所有接口 401 `login_required` | 进程重启/上锁后会话被清 | 重新登录（正常行为） |
| 页面是旧版 | 浏览器缓存 | 强刷 ⌘⇧R；核对 `BUILD` 与 `?v=` |
| 改的地方没生效 | 忘了复制到运行目录 | `curl /assets/app.js` 查关键字符串 |
| 后端不响应（健康检查超时） | 大批量逐条写入把 store 锁住 | 重启后端；改用 `put_many` |
| 422 且消息看不懂 | SHACL 形状与谓词冲突 | 看 `data/shacl-errors.log`；检查是否复用了带 domain 的谓词 |
| `Unknown collection` | 集合没在 `model.CLASSES` 注册，或落到通用路由 | 断言三处注册；检查路径是否被通用路由吃掉 |
| 通讯录同步失败 | 手机未授权 USB 调试 / 未连 / adb 不在 PATH | 提示用户允许调试；`adb devices` 自查 |
| manager 起不来 | 8765 被占用 | `lsof -i:8765`；改 `PERSONAL_ONTOLOGY_PORT` |

## 8. 回滚

```bash
# 代码回滚
git checkout <上一个好提交> -- <文件> && cp <文件> /Users/Apple/personal-ontology/… && 重启

# 数据回滚（前提：有备份）
cp data/ontology.po.json.bak data/ontology.po.json && 重启 && 用备份当时的口令登录
```

## 9. 迁移到新机器（概要，详细见 09）

```
1) 装 Python 3.14、建 .venv、pip install -r requirements.txt
2) 复制仓库（不含 data/）到新机的运行目录
3) 复制 data/ontology.po.json（唯一必须搬的状态）
4) 写 launchd plist（路径改成新机的绝对路径）
5) 启动 → 用原口令登录 → 跑 scripts/verify-deploy.sh
6) 迁移验收：集合计数一致、revision 一致、随机抽 3 条资料项能读、判定能跑
```
