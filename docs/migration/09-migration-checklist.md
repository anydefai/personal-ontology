# 09 · 迁移清单

> 两种迁移：**A. 换机器跑起来**（数据要跟着走）、**B. 交给另一个人接手开发**（数据不走）。
> 两种情况都从第 0 步开始。

---

## 第 0 步 · 迁移前先在旧机做一次体检

```bash
cd /Users/Apple/Documents/personal-ontology
git status --porcelain            # 必须干净；有改动先提交
git log --oneline -1              # 记下提交号
python3 -c "import json,pathlib;d=json.loads(pathlib.Path.home().joinpath('personal-ontology/data/ontology.po.json').read_text());print(d['revision'], list(d['sections']))"
ls -la ~/personal-ontology/data/ | head -20    # 看清有哪些文件
```

记录三项，迁移后要对比：

```
□ 提交号：______________________
□ 容器 revision：________________
□ 集合计数（登录后 GET /v1/collections 或逐集合数）：________________
```

---

## A · 换机器（含数据）

### A1 准备新机

```bash
□ 安装 Python 3.14（与旧机一致；`python3 -V` 核对）
□ 装 Xcode Command Line Tools（rdflib/pyshacl 的依赖需要）
□ 确认磁盘加密已开（FileVault）：容器虽加密，但设备层再加一道更稳
```

### A2 搬家

```bash
# 仓库（不含 data/，data 在 .gitignore 里）
git clone git@github.com:anydefai/personal-ontology.git /新路径/personal-ontology

# 虚拟环境
cd /新路径/personal-ontology
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 唯一必须搬的状态：加密容器
scp 旧机:~/personal-ontology/data/ontology.po.json 新机:/新路径/personal-ontology/data/ontology.po.json
chmod 600 /新路径/personal-ontology/data/ontology.po.json

□ 可选：settings.json（界面语言等偏好）
□ 可选：model-service.json + model-service.key（模型服务凭据；不迁就重新配）
□ 不要：server.log、session-token、api-token（会重新生成）
□ 不要：contacts-raw.txt / contacts-import.json（明文中间文件，导入完就该删）
```

### A3 起服务

```bash
□ 写 launchd plist：把 06 里的示例中 3 处绝对路径改成新机路径
   ~/Library/LaunchAgents/personalontology.personal-ontology.backend.plist
□ launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/personalontology.personal-ontology.backend.plist
□ launchctl kickstart -k gui/$(id -u)/personalontology.personal-ontology.backend
□ curl -s http://127.0.0.1:8766/health           → {"status":"ok",...}
□ curl -s http://127.0.0.1:8765/ | grep BUILD    → BUILD <当前版本>
```

### A4 验收（缺一不可）

```
□ 用【旧机的口令】登录成功（口令不对 = 容器或口令记错了，别继续折腾代码）
□ 容器 revision 与迁移前一致
□ 逐集合计数与迁移前一致（至少抽查：profiles / circles / profile-items / decisions）
□ 随机抽 3 条资料项能读、能查看明文（会写一条 reveal 记录）
□ 跑一次判定：POST /v1/decisions/evaluate，返回带 matched_via
□ 跑 scripts/verify-deploy.sh 与 scripts/verify-security.sh
□ 跑三轮闸门（挑 8 个核心套件 + 前端两项）
```

### A5 迁移后立刻做

```
□ 改口令（POST /v1/account/password）：新机新口令，避免旧口令扩散
□ 旧机：launchctl bootout 停服务；把 data/ontology.po.json 改名为 .retired（或加密后归档）
□ 旧机：删除明文中间文件与 session-token
```

---

## B · 交给另一个人（数据不走）

```
□ 给对方：仓库地址 + 本目录（docs/migration/）
□ 让对方先读 01（架构）→ 02（数据模型）→ 07（测试）
□ 让对方在本机用临时数据目录跑一遍闸门（PERSONAL_ONTOLOGY_DATA=$(mktemp -d)）
□ 明确三条禁令：不提交 data/；不跳过闸门；改 app.js 先编译后写盘
□ 交接时口头讲清三件事：
    ① 两份目录的方向（仓库 → 运行）
    ② put 与 put_many 的成本差异
    ③ 新集合必须用专属谓词
```

---

## 迁移后的风险清单（逐条确认）

| 风险 | 表现 | 检查方式 |
|---|---|---|
| 口令丢失 | 永远打不开，无后门 | 迁移前确认口令可用 |
| 只复制了部分文件 | revision 对不上 / 段缺失 | 打印 `sections` 键 |
| 数据目录权限错 | 其他人可读容器 | `ls -l` 应为 600，目录 700 |
| 明文残留 | 旧目录有 contacts-import.json | `find data -name "contacts-*"` |
| 版本漂移 | 新机依赖升级导致 SHACL 行为变化 | 锁 `requirements.txt`；先跑闸门 |
| launchd 路径没改 | 服务起不来，日志 `No such file` | `data/server.log` 头部 |
| 端口被占 | manager 启动失败 | `lsof -i:8765` |
| adb 不在 PATH | 通讯录同步 422 | `which adb` |

---

## 不要做的事（每一条都真实踩过）

```
✗ 不要把 data/ 从仓库复制过去（仓库里没有 data/，复制会得到空目录并覆盖真实数据）
✗ 不要在容器上跑 sed / 编辑器（base64 + GCM 校验会失败）
✗ 不要只备份 ontology 段（容器是一体的）
✗ 不要用"逐条 put"导入几百条（会把后端锁死，必须 put_many）
✗ 不要给已有路径加"查询参数变体"当新接口（会落到通用路由，返回 Unknown collection）
✗ 不要在没有跑闸门的情况下部署（闸门拦下过真实的回归）
✗ 不要在汇报里说"应该没问题"—— 要么验证过，要么说没验证
```

---

## 一页速查（打印贴在桌上）

```
两份目录   仓库 Documents/personal-ontology ｜ 运行 ~/personal-ontology（data 只在这里）
两个端口   8765 界面+代理 ｜ 8766 后端
一个状态   data/ontology.po.json（口令即一切，无法找回）
三段       ontology ｜ model_service ｜ ledger
三道闸门   后端套件 → test_ui_behavior.js 26/26 → test_frontend_syntax.py 10/10
三条铁律   先编译后写盘 ｜ 批量用 put_many ｜ 新集合用专属谓词
重启后果   空间上锁，所有用户需重新登录（每次都要说明）
```
