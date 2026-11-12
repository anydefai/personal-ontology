# 个人本体 · 迁移文档集

> 面向对象：要在新机器上重建这套系统的人，或第一次接手这份代码的开发者。
> 版本基准：`BUILD 20261028A`（提交见 `git log -1`）。
> 这不是用户手册（那在 [docs/user-guide.md](../user-guide.md)），也不是产品介绍（[README.md](../../README.md)）。
> 这一套只回答一个问题：**把它整体搬走、或者交给另一个人，需要知道什么。**

---

## 0. 五分钟读懂这个项目

```
它是什么   一个跑在个人电脑上的"个人数据授权中心"。
           数据只有一份，在你本机的加密文件里；谁能拿你的什么、拿多久，由规则决定。

它怎么跑   两个进程：
             8765  manager.py  对外界面（静态页 + 反向代理 /v1）
             8766  api.py      真正的后端（FastAPI，104 条路由）
           数据落在 data/ontology.po.json 一个加密容器里，三段互不牵连：
             ontology（本体与业务） / model_service（模型服务凭据） / ledger（流水）

它靠什么   ① 单文件加密容器（PBKDF2 200 万次 + AES-256-GCM，原子替换）
           ② 内存里的 RDF 图（rdflib）+ 每次写入走 SHACL 校验
           ③ 授权判定引擎（主体 / 圈 / 代理 / 条件 / 阶段）
           ④ MCP 三个工具，供外部智能体调用
```

## 1. 文档地图

| 文件 | 内容 | 什么时候看 |
|---|---|---|
| [01-architecture.md](01-architecture.md) | 进程拓扑、模块职责、请求链路、设计原则 | 第一天必读 |
| [02-data-model.md](02-data-model.md) | 37 个集合与字段、谓词规则、三个必踩的坑、新增集合 SOP | 改数据模型前必读 |
| [03-storage-security.md](03-storage-security.md) | 容器二进制格式、密钥派生、段隔离、会话、备份、威胁模型 | 动 vault 或做备份前必读 |
| [04-api-reference.md](04-api-reference.md) | 104 条路由分组清单、关键端点、错误格式、路由陷阱 | 写前端或对接前 |
| [05-ui-map.md](05-ui-map.md) | 22 个页面 / 26 个渲染函数、共享组件、i18n、样式约定 | 改界面前 |
| [06-deployment.md](06-deployment.md) | 两套目录、venv、launchd、部署步骤、验证、回滚、故障 | 上线或搬家时 |
| [07-testing.md](07-testing.md) | 68 个测试文件、闸门命令、测试基建、四个已踩的坑 | 每次改代码前 |
| [08-decisions.md](08-decisions.md) | 关键决策与取舍（为什么是这样而不是那样） | 想改设计前 |
| [09-migration-checklist.md](09-migration-checklist.md) | 分步迁移清单 + 验收 + 不要做的事 | **搬家时照这个做** |

## 2. 仓库长什么样

```
backend/          后端（约 9,000 行）
  api.py            3,561 行  FastAPI 路由与业务编排（唯一的"入口大全"）
  store.py            798 行  RDF 图 + SHACL 校验 + 容器落盘 + 判定引擎
  line_format.py      668 行  场景切片的"线格式"解析/渲染
  field_names.py      581 行  字段名与谓词的双语对照
  mcp_server.py       481 行  MCP 三个工具
  vault.py            329 行  加密容器（PBKDF2 + AES-GCM + 原子替换）
  model.py            329 行  37 个集合的字段映射（唯一事实来源）
  manager.py          327 行  界面服务 + /v1 反向代理 + 来源校验
  scenario_llm.py     249 行  场景分析器（调模型）
  agent_access.py     237 行  智能体接入与凭据
  contacts_sync.py    213 行  安卓通讯录拉取与就地更新
ontology/         personal-properties.ttl（OWL 谓词）+ shapes.ttl（SHACL 形状）
web/              index.html 127 行 + app.js 2,380 + pro.js 1,832 + i18n.js 2,113 + app.css 8
tests/            68 个测试文件
docs/             00–08 设计与说明 + migration/（本目录）
samples/          示例与文章
scripts/          运维脚本（部署核对、安全核对、MCP 远程、改名）
assets/           常见密码表等静态资源
data/             【运行期数据，不进 git】容器、日志、令牌
```

## 3. 三个最容易造成事故的地方

```
① 误解"两份目录"
   仓库（git）与运行目录是两份：仓库改完必须"复制到运行目录 + 重启"才生效，
   而 data/ 只在运行目录里——复制前先看清方向，别把 data/ 覆盖掉。

② 误解"每次写入都很贵"
   put() = 整图序列化 + 全量 SHACL + 整库重加密。逐条写一千条会慢到锁死后端。
   批量导入必须用 put_many()（每 200 条一次校验、一次落盘）。

③ 误解"属性可以随便复用"
   谓词带 rdfs:domain/range 时，推理会把节点重新定型，进而触发无关的 SHACL 失败。
   新集合一律用**专属谓词**（见 02 的坑 1）。
```

## 4. 术语表（读代码时对照）

| 中文 | 代码里的名字 | 一句话 |
|---|---|---|
| 本体 | ontology 段 / `store.graph` | 全部业务数据的 RDF 图 |
| 容器 | `data/ontology.po.json` | 加密后的整库文件 |
| 段 | `sections.ontology` / `model_service` / `ledger` | 容器内互相独立加密的三块 |
| 主体 | `principals` | 人、智能体、服务、集体 |
| 圈 | `circles` + `circle-members` | 一群人的关系单位，可整体授权 |
| 代理 | `principals.acts_for` | 智能体代表某人，继承其圈与授权 |
| 切片 | `scenario-slices` | 一个场景被确认后的实例 |
| 判定 | `store.evaluate()` | 一次"能不能做"的计算 |
| 交付 | `decisions` 里 `skill_delivery` | 专业判断对外正式交付 |
| 线格式 | `line_format.py` | 切片在 UI 里的多行文本表示 |
