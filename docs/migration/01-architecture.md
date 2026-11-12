# 01 · 架构

## 1. 进程拓扑

```
                      浏览器（本机）
                            │  http://127.0.0.1:8765
                            ▼
        ┌───────────────────────────────────────────┐
        │  manager.py   （端口 8765）                │
        │  · 静态页面：/, /assets/*（web/ 目录）      │
        │  · 反向代理：/v1/**  →  http://127.0.0.1:8766│
        │  · 来源校验：Origin / Host 白名单           │
        │  · 注入 X-Display-Language 等请求头         │
        └───────────────────┬───────────────────────┘
                            │  仅回环，不对外
                            ▼
        ┌───────────────────────────────────────────┐
        │  api.py       （端口 8766，uvicorn）        │
        │  104 条 /v1 路由 · 会话校验 · 业务编排       │
        └───────────────────┬───────────────────────┘
                            ▼
        ┌───────────────────────────────────────────┐
        │  store.py   （进程内单例）                  │
        │  · rdflib.Graph（解锁后整库在内存）         │
        │  · put/get/list/delete/rename/put_many    │
        │  · evaluate() 授权判定引擎                 │
        └───────────────────┬───────────────────────┘
                            ▼
        ┌───────────────────────────────────────────┐
        │  vault.py  →  data/ontology.po.json       │
        │  PBKDF2-HMAC-SHA256(2,000,000) + AES-256-GCM │
        │  三段：ontology / model_service / ledger    │
        └───────────────────────────────────────────┘
```

同时存在的另一个入口：**MCP 服务**（`backend/mcp_server.py`，stdio 方式被智能体进程拉起），
它直接调用 `store` 与 `api` 里同样的函数，不经过 8765/8766。它只暴露 3 个工具：

```
get_governance_catalog     读取资源类型、动作、已发布场景（不含个人数据）
check_authorization        判定"这个主体能不能对这个资源做这个动作"
judge_professional_slice   调用某个专业切片给出结论
```

## 2. 请求链路（以"改一条资料项"为例）

```
① 浏览器 app.js  api("/v1/profile-items/pi_x", {method:"PATCH", body})
② manager.py     校验 Origin → 转发到 8766，附上 Authorization: Bearer <session>
③ api.py         require_session 依赖校验会话 → 读 store.get("profile-items", "pi_x")
④ store.put()    克隆现有图 → 新增/替换三元组 → _validate() 跑 SHACL
                 → 成功则整库序列化成 Turtle → vault.put_section("ontology", ...)
                 → 临时文件 + os.replace（原子）
⑤ 返回 JSON      { ...字段 }
⑥ 前端           局部重绘
```

关键点：
- **校验在写入之前**，失败则一字节都不落盘（返回 422 并附 SHACL 报告）；
- 写入是**整段重写**（ontology 段），所以单次写入成本与库大小成正比 —— 这就是批量接口存在的理由；
- 会话令牌与数据分离：锁定时 `data/session-token` 被清除，接口统一 401 `login_required`。

## 3. 模块职责

| 模块 | 职责 | 不该做的事 |
|---|---|---|
| `api.py` | 路由、参数校验、编排、错误消息本地化 | 不要在这里直接操作 RDF 三元组 |
| `store.py` | 图的读写、SHACL、落盘、判定引擎 | 不关心 HTTP、不认识 DTO 命名 |
| `model.py` | 集合→类、字段→谓词、ID 字段（唯一事实来源） | 不要写业务逻辑 |
| `vault.py` | 加密格式、口令派生、原子写 | 不认识业务字段 |
| `manager.py` | 静态资源、代理、来源校验、启动后端 | 不承载业务 |
| `mcp_server.py` | 智能体侧三个工具、预填确认流程 | 不直连 vault（只经 store） |
| `scenario_llm.py` | 场景分析提示词与模型调用 | 不写库（结果交回 api） |
| `line_format.py` | 切片的文本表示与解析 | 不改数据模型 |
| `field_names.py` | 字段名/谓词的双语对照 | 不做校验 |
| `agent_access.py` | 智能体注册、凭据、范围 | 不存明文密钥 |
| `contacts_sync.py` | 调 adb、解析、按稳定 ID 就地更新 | 不碰圈与授权 |

## 4. 五条设计原则（违背它们会立刻出问题）

```
① 单文件、可搬走
   全部状态就是 data/ontology.po.json（外加令牌与设置文件）。没有数据库、没有服务端会话存储。

② 校验先于落盘
   任何写都必须经过 SHACL。宁可 422，也不写进一条坏数据。

③ 段隔离
   流水（ledger）与模型凭据（model_service）各自独立加密段：
   写流水不会重写本体段（已用密文逐字节比对验证过）。

④ 关系与资料分离
   圈里只存"关系"（身份、亲近、最后互动），从不存对方的证件与住址。
   需要联系方式时单独授权，且标 restricted。

⑤ 判定必须可解释
   evaluate 返回 matched_via（本人/上级/圈/代理）+ 命中的规则 id，
   不允许出现"只给结论不给理由"的判定。
```

## 5. 线程与并发

- uvicorn 单进程；`store` 内部 `threading.RLock` 保护图与落盘；
- 所有写操作串行化（这也是"逐条写会慢"的结构性原因）；
- `api.py` 里阻塞的活（adb 拉取、模型调用）走 `asyncio.to_thread`，避免阻塞事件循环；
- 没有后台任务队列：批量导入是同步请求，靠 `put_many` 把耗时压到秒级。

## 6. 依赖

```
Python 3.14（运行目录 .venv）
  fastapi / uvicorn / rdflib / pyshacl / cryptography / httpx
系统
  macOS + launchd（生产用）；adb（仅通讯录同步需要）
```
迁移时 **不要** 升级 rdflib/pyshacl 的大版本而不跑闸门：SHACL 报告格式与推理行为都可能变。
