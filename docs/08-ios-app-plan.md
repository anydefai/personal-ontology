# iOS App 实施计划（原生 Swift / 全本机运行）

状态：已定方向，尚未开工
目标：iPhone / iPad 上**独立运行**本体（不依赖 Mac 开机），iOS 18.7+
约束：**运行时零第三方依赖**；数据独立一份，手工导出/导入

## 1. 已定的三个决定

| 决定 | 内容 | 影响 |
|---|---|---|
| 形态 | **B：原生 Swift 全本机**（引擎跑在手机上） | 后端 4,665 行 Python 需按层重写 |
| 数据 | **手机独立一份**，通过 AirDrop / 文件 App 手工传递容器 | **无需同步协议、无冲突**；容器本身是密文，传输即加密 |
| 依赖 | 运行时**零第三方**（全系统框架） | 排除了内嵌 CPython 方案；Turtle 需自己写子集 |

## 2. 架构映射（Python → Swift）

| 现有模块 | 行数 | iOS 对应 | 说明 |
|---|---|---|---|
| `vault.py` | 315 | `ContainerCrypto.swift` | CryptoKit `AES.GCM` + CommonCrypto `CCKeyDerivationPBKDF` |
| `model.py` | 134 | `OntologyModel.swift` | 13 个集合、字段类型映射 |
| `store.py` | 541 | `GraphStore.swift` + `DecisionEngine.swift` | 图读写 + 判定引擎（默认拒绝、deny>ask>allow、红线、风险门槛） |
| `field_names.py` | 549 | `FieldNaming.swift` | 英文机器键 + 中英显示名 + 别名归一 |
| `scenario_llm.py` | 225 | `ScenarioAnalyzer.swift` | `URLSession` 调 OpenAI 兼容接口，无 SDK |
| `api.py`（业务部分） | 1510 | `Services.swift` + `LocalServer.swift` | 实体 CRUD、场景确认、规则编译、判定留档 |
| `api.py`（鉴权/会话） | — | 简化 | 单机单用户：解锁即会话，不再需要令牌与会话表 |
| `manager.py` / `agent_gateway.py` / `peercred.py` / `agent_access.py` | 828 | **不移植** | 见第 6 节：iOS 用 App Intents 取代 MCP |
| `web/*`（app.js/app.css/i18n.js/index.html，188 KB） | — | **原样复用** | WKWebView 宿主，指向本机回环服务；**UI 零重写** |
| `ontology/*.ttl` | 273 | 资源文件 | 元模型 + SHACL 子集校验规则 |

## 3. 分阶段任务与验收标准

### P0 加密容器（1–2 周）— **go/no-go 门槛**
- 读出 `format/version/sections`，按 `AAD = po-container-v1|section|version|salt|iterations|nonce` 解密
- 写回走"临时文件 + 替换"，保持原子性
- **验收**：用 `docs/05` §3.5 的冻结测试向量，在真机上跑出**完全相同**的密文
- **测试**：错误口令拒绝；段独立性（改一段不影响另一段）；版本不符时报错而非误读
- **不宜通过就停下来**：说明格式仍有歧义，必须先回 Mac 侧澄清

### P1 规范 Turtle 子集（1–2 周）
- 只支持**我们自己序列化**的构造：前缀、IRI、字符串/数字/布尔/日期字面量、`rdf:type`、JSON 字面量、多值属性
- **验收**：把 Mac 上导出的容器解开，解析后**逐三元组比对**（沿用迁移脚本那套校验思路）
- **测试**：往返一致（解析→写出→再解析，集合相等）

### P2 领域模型 + 校验（2–3 周）
- 13 个集合的 Swift 模型；字段命名契约（含中英显示名与别名归一）
- SHACL 子集校验：`sh:property` / `sh:path` / `sh:minCount` / `sh:maxCount` / `sh:datatype` / `sh:in` / `sh:nodeKind`
- **验收**：对 Mac 侧 6 份测试用例逐条得到相同结论
- **测试**：删除被引用节点必须失败；缺必填字段必须失败

### P3 判定引擎（1–2 周）
- 默认拒绝；deny > ask > allow；红线优先；主体继承；匹配器白名单（正则禁用）
- 约束类型：`context_equals` / `numeric_lte` / `numeric_gte` / `context_exists` / `source_trust_min` / `temporal_lte` / `temporal_gte`
- 时间解析：中英双语（`15:00` / `下午3点` / `3 PM` / `Oct 10, 2026` / `2026年10月10日`），**歧义不猜**
- **验收**：`tests/test_temporal.py` 的 50 条断言在 Swift 侧全绿
- **测试**：必填字段缺失时不进入规则匹配（返回需补充信息）

### P4 场景流水线（3–4 周）
- 提示词构造（含语言跟随）、`URLSession` 调用、JSON 解析与容错
- 场景确认 → 规则编译（**条件级容错**：坏条件只丢该条，全坏才跳过）
- 偏好归一与剔除（运行时字段、相对时间）
- **验收**：同一段中文/英文描述，Mac 与 iOS 产出的 `policies` / `facts` / `required_inputs` 结构一致
- **测试**：坏条件容错、幂等（重复补生成不重复建规则）、重新分析不丢归属

### P5 本机服务 + 控制台（1–2 周）
- `Network.framework` 在 `127.0.0.1` 起 HTTP 服务，实现控制台实际调用的端点
- WKWebView 加载 `http://127.0.0.1:<port>/`，宿主现有 `web/`
- **验收**：控制台所有页面可用（总览 / 场景 / 判定 / 模型服务 / 显示与语言）
- **测试**：双语切换生效；401/409 契约与 Mac 一致

### P6 iOS 集成（2–3 周）
- **数据保护**：容器文件设为 `NSFileProtectionComplete`（锁屏即不可读，比 Mac 现状更强）
- **钥匙串 / Secure Enclave**：把 `docs/07` §7 的 **T5** 在这里落地——解锁与批准均需 Face ID / Touch ID
- **导出/导入**：自定义 `UTType`（如 `personalontology.personal-ontology.container`），支持文件 App 原地打开、AirDrop、"导出副本"
- **测试**：锁屏后无法读取容器；导入损坏文件给出明确错误且不破坏现有数据

### P7 智能体面：App Intents（1–2 周）
- 用 `AppIntents` 暴露：查询场景目录、检查授权、预演场景实例
- 走快捷指令 / Siri / 聚焦，**取代 MCP**（iOS 无法让第三方客户端启动 stdio 子进程）
- **验收**：在快捷指令里能完成一次"检查某主体能否执行某动作"

### P8 测试与发布（2–3 周）
- 真机（含 iPad）、低电量/后台/锁屏、大容器性能
- TestFlight，App Store 文案与隐私说明（**不联网到我们自己的服务器**，只连用户自配的模型服务）

**合计 14–22 周（4–6 个月）。**

## 4. 第三方依赖

**运行时：0 个。** 全部系统框架：`CryptoKit`、`CommonCrypto`、`Network`、`WebKit`、`SwiftUI`、`Security`、`LocalAuthentication`、`AppIntents`、`UniformTypeIdentifiers`、`BackgroundTasks`。

唯一需要自研的替代品是 **Turtle 子集解析器**（无成熟 Swift RDF 库）。不引入 Serd/Redland 等 C 库——序列化格式由我们控制，子集可以限制得很小。

## 5. 已确认的三项决定（开工前问题已关闭）

### 5.1 导出/导入走**文件 App**

- 自定义 `UTType`（建议 `personalontology.personal-ontology.container`，扩展名 `.po.json`）
- `Info.plist`：`CFBundleDocumentTypes`（含该 UTType）+ `LSSupportsOpeningDocumentsInPlace = YES`
  → 在文件 App 里点容器可**原地打开并写回**，而不是每次都导入副本
- **导出**：分享菜单 →「存储到文件」，或"导出副本"
- **首次使用**：从文件 App「在我的 iPhone 上」选一个容器；没有则新建
- 注意：原地打开意味着**同一个文件**，因此写入必须保持"临时文件 + 原子替换"，
  否则文件 App / iCloud 侧可能读到半个文件

### 5.2 **不做合并**：两份容器各自演化

- 不实现 diff / merge / 三方合并；两份容器就是两份独立本体
- 因此必须在界面上避免误导：显示当前打开的**容器名与路径**，并明确"这份与 Mac 上那份是两份独立数据"
- 建议：打开时显示最近修改时间与规模（主体/场景/规则计数），便于肉眼确认拿对了文件

### 5.3 模型服务密钥**随容器走**

- 与 Mac 现状一致：API Key 存在容器的 `model_service` 段（整段 AES-256-GCM 加密），
  **不需要钥匙串**、不单独落盘
- 含义：换一份容器 = 换一套模型服务配置；"导出即带走全部配置"因此成立
- 仍需单独处理的是**容器口令本身**：默认每次解锁都输入；可选"用 Face ID 记住口令"
  （口令存钥匙串并由生物识别保护）——与 T5 是同一件事，放在 P6

## 6. 明确不做的事

- ❌ **MCP 服务**：iOS 后台限制决定了第三方客户端无法启动 stdio 子进程；改用 App Intents
- ❌ **iCloud 自动同步**：与"独立一份、手工传递"的决定冲突
- ❌ **两份容器的合并工具**：已确认不合并，各自演化（见 §5.2）
- ❌ **多用户/多主体登录**：仍是单用户本机模型
- ❌ **跨机智能体授权清单**：那是 Mac 侧为同机进程设计的机制，iOS 不需要

## 7. 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 工作量估计偏差 | 集中在 P4（与产品细节耦合最深） | 每阶段单独可发布，随时可停在可用状态 |
| 双端行为漂移 | Mac 与 iOS 各写一套引擎 | **共同测试集**：把 Python 测试逐条移植为 XCTest，任一侧失败即视为 bug |
| 容器格式演进 | 未来若升级 `version`，两端都要改 | 格式已冻结；升级必须同时改两端并提供迁移 |
| Turtle 子集不够用 | Mac 侧序列化若引入新构造 | P1 验收用"逐三元组比对"，能立刻发现 |

---

## 评估结论：暂不实施（2026-10-02）

本计划经评估后**暂不实施**。理由按重要性排列：

1. **原始动机在平台层面不成立。** 该计划的出发点是"iPad 上的本体配合 iPad 版代理
   （WorkBuddy / Muse）控制 iPad 上的 App"。经核实：**iOS 上任何第三方 App 都无法驱动
   另一个第三方 App**——没有公开 API，唯一的跨 App 自动化是 App Intents / 快捷指令，
   且必须由**系统**调度。WorkBuddy iPad 与 Muse Code（终端 CLI）都只能"连到一台主机"，
   结构上不可能访问装在 iPad 里的本体。这不是产品差异，是 Apple 的沙箱设计。

2. **两份独立容器与"唯一权威"相冲突。** 既定数据策略是"独立副本、不合并、各自演化"，
   而本体的核心价值是**唯一事实来源**。一份会分叉的权威不再是权威，长期会产生
   "手机上这条规则和 Mac 上这条哪个算数"这类无解问题。

3. **双端漂移的长期成本高于收益。** 完整版工期 4–6 个月，且需**永久维护两套引擎**
   （Swift 与 Python），行为漂移是本计划自评的最大风险。对单人维护的个人工具，
   这是持续的重税。

**替代方案（已确认）**：

- **单机版做完整、做稳定** —— 治理内核（本体的判定/规则/审计）继续在 macOS 上深化，
  "代理操作 App 前先问本体"在 macOS 上今天就能跑。
- **移动端查看**如确有需要，走 **2–3 周的瘦客户端**（隧道 + 现有 HTML 控制台），
  **不产生第二个事实来源**。
- **iPad 上仅保留 App Intents 这一条路**：由快捷指令调用本体的判定 Intent，
  本体充当策略判定点；"智能体"是系统（快捷指令 + Apple Intelligence），
  而非第三方代理。可控动作限于各 App 主动暴露的快捷指令动作。
- 远程代理访问（`streamable_http` MCP）不是 iOS 议题，而是"本体跑在主机上"那条线。

**本文其余部分保留**，作为该评估的证据与设计参考；若将来前提变化
（如 Apple 开放跨 App 自动化 API），可据此重新评估。
