# 变更记录

本项目此前未纳入版本控制（目录下没有 git 仓库），因此本文件从 2026-10-01 起人工记录改动。
每条包含：改动内容、原因、影响面、验证方式与部署状态。

部署关系：工作区（源码目录）是源；运行副本 `~/personal-ontology` 由
`install.sh` 复制得到，控制台（http://127.0.0.1:8765）实际读取运行副本的 `web/`。**改了工作区不等于生效，
必须同步到运行副本。**

---

## 2026-10-01

### 前端 · 场景实例编辑页：全局偏好模式中文标签错行

- 文件：`web/app.js` → `scenarioSegmentationEditor()`
- 现象：偏好适用范围选"所有情况共用一套偏好"时，偏好行的中文标签（如"最高价格""酒店位置区域"）逐字换行。
- 原因：偏好行使用固定的三列模板 `42px minmax(130px,1fr) minmax(120px,1fr)`，但全局模式下第一个单元格
  （维度勾选框 `display:none`）不参与布局，标签块前移落进 **42px** 的首列。
- 改动：按模式生成列模板
  - 全局：`minmax(150px,1fr) minmax(130px,1fr)`（2 列）
  - 分组：`max-content minmax(130px,1fr) minmax(120px,1fr)`（3 列，首列由固定 42px 改为自适应，
    顺带修掉"维度"两字在 42px 内同样折行的问题）
- 验证：`node --check web/app.js` 通过；用 node 直接渲染该函数并检查产出 HTML ——
  全局 2 列 / 占位 2 个单元格、分组 3 列 / 占位 3 个单元格，均匹配。
- 部署：已同步至 `~/personal-ontology/web/app.js`；两个服务（8765 管理器、8766 后端）返回的
  `/assets/app.js` 均已确认含新模板，旧 `42px` 模板消失。刷新控制台页面生效。

### 前端 · 分组模式维度行读取修复（工作区既有改动，本次一并部署）

- 文件：`web/app.js` → `readScenarioSegmentation()`
- 内容：行过滤由 `x.value!==""` 改为 `x.value!==""||x.dimension`，使已勾选但尚未填值的维度行不再被丢弃；
  分组校验由 `Object.values(values).some(...)` 改为按维度定义逐个检查
  `dimensions.some(d=>values[d.field]===""||values[d.field]===undefined)`。
- 原因：旧过滤会把"已勾选维度但值为空"的行丢掉，导致勾选维度后仍提示"请至少勾选一个区分维度"。
- 状态：该改动此前已存在于工作区（15:34），但一直未部署到运行副本（15:33），本次同步一并生效。
- 部署：同上，已生效。

### 文档 · 新增 `docs/04-design-vs-implementation-gaps.md`

- 内容：`docs/03` 场景切片设计与当前实现的逐项差距清单。
- 规模：46 项可检验要求 —— ❌ 32 项未实现、⚠️ 14 项部分实现；另 11 项已对齐、1 项（E11）判定为
  "文档过时"而非实现差距。
- 结论要点：完整通用元模型（ScenarioDefinition / SlotValue / Clarification / WorkflowStep）基本未落地；
  真正实现的是 §26"场景切片 + 偏好分组"竖切。
- 实测发现的两项 P0 缺陷：
  - **A1** 场景生成的约束值在 RDF 中被写成 Python repr（`"{'key': 'check_in_date'}"^^rdf:JSON`），
    `json.loads` 无法解析 → 规则永不匹配，判定永远落到 `default_deny`。
  - **A2** `api.py:416` 在 `417` 之前引用 `suffix`，已确认场景的实例保存（`PATCH .../instance`）
    与 `/feedback` 必然 `NameError`。
- 后续：`docs/03` §7 主张保留"资源类型 / 动作 / 授权规则"三个页面，该主张已被最新（v3.1）设计取消
  （README 与实际菜单均无此三项）；§7 与 §24.4 中的目录页/`catalog-forms.js` 部分不再适用。

---

## 2026-10-01（第二轮：启用授权 + 阻断缺陷修复）

工作区与运行副本已同步并重启后端；以下改动均已实测。

### 后端 · A1 约束值序列化损坏（阻断）

- 文件：`backend/model.py`、`backend/store.py`
- 现象：场景生成的规则条件在 RDF 中写成 Python repr（`"{'key': 'check_in_date'}"^^rdf:JSON`），
  `json.loads` 必然失败 → 条件永不成立 → 规则永不匹配 → 判定永远 `default_deny`。
- 改动：
  - 写入端 `object_to_graph` 增加分支：映射为 `lit` 但值本身是 dict/list 时，按真实 JSON 文本
    （`json.dumps` + `rdf:JSON`）落盘。
  - 读取端抽出 `decode_constraint_value()`：先按 JSON 解析，失败再按 Python 字面量
    （`ast.literal_eval`）解析 —— 因此**无需数据迁移**，图里现存的 16 条历史条件立即可用。
- 验证：真实 RDFStore 往返 + 副本上对本机 2 个场景的 14 条条件逐条解码。

### 后端 · A2 场景实例保存必然报错（阻断）

- 文件：`backend/api.py` → `update_scenario_instance()`
- 现象：`suffix` 在第 416 行被引用、第 417 行才赋值，只要资源已带参数就 `NameError`
  （本机 2 个场景都满足）。它同时也挡住了 `/feedback` 的长期偏好写入。
- 改动：把 `suffix = scenario_id.removeprefix("scene_")` 提前到使用之前。
- 验证：stub store 复现 → 修复后保存成功，参数定义正确重建。

### 后端 · 新发现：单值关系反序列化成标量（阻断，此前被 A2 掩盖）

- 文件：`backend/store.py` → `evaluate()`
- 现象：图中某关系只有一个取值时，`graph_to_record` 返回裸标量而非列表。于是
  `actions: "hotel.book"` 被逐字符遍历 → **规则永不匹配**；
  `constraints: "c1"` 不是 list → 被 `_constraints_match` 当空列表 → **条件被静默忽略（过宽）**。
- 说明：本机每条规则恰好有 2 个动作、多条条件，所以一直没暴露；只要场景只有一个动作就会命中。
- 改动：在判定入口把 `actions` / `constraints` 归一化为列表后再使用。
- 验证：副本上 `scene_5765508d20d2` 两条规则启用后，上下文完备 → `ask`（ask 胜 allow）；
  缺 `parking_required` → 规则不匹配 → `default_deny`（fail-closed 正确）。

### 后端 · 新发现：重写记录时日期字段丢失 `xsd:dateTime`

- 文件：`backend/model.py` → `datatype()`
- 现象：从图里读回的 `createdAt` 是 `datetime` 对象，重写时 `datatype()` 不认识它 → 降级为
  `xsd:string` → SHACL 校验失败。任何**局部更新带有日期字段的记录**都会失败（通用 PATCH、
  实例保存重写授权、新的启用接口都会踩到）。
- 改动：`datatype()` 增加 `datetime → xsd:dateTime`、`date → xsd:date` 分支。
- 验证：集成测试中启用规则触发重写，此前抛 `ValidationError`，修复后通过。

### 后端 · A4 启用授权

- 文件：`backend/api.py`
- 新增：
  - `GET  /v1/scenario-slices/{id}/policies` —— 返回该场景的规则摘要（主体、资源、动作、效果、
    条件、可执行性问题），供审核面板使用。
  - `POST /v1/scenario-slices/{id}/activate` —— draft → active；逐条校验条件可执行性，
    不可执行的规则被拦下并说明原因；写入 `evolution_log` 审计事件。
  - `POST /v1/scenario-slices/{id}/suspend` —— active → suspended（暂停，区别于 `revoked` 撤销）。
  - 守卫：通用 `PATCH /v1/authorizations/{id}` 改 `policy_status` 返回 409，必须走上面的操作。
  - 回退：编辑实例导致条件真正变化时，生效中的规则自动回到 `draft`，并记录原因。
  - 分组（segmented）场景的规则不允许启用：单条规则表达不了分组条件，启用会波及所有上下文。
- 验证：真实 RDFStore 集成测试 11/11 通过（启用前后判定、条件缺失不匹配、PATCH 守卫、
  回退 draft、分组拒绝、未确认场景拒绝、幂等）。

### 前端 · A4 入口

- 文件：`web/app.js`
- 场景实例**清单页**：每行显示 `N 条生效中 / N 条未生效` 徽标 + 「审核并启用」按钮，
  点开审核面板列出每条规则的主体、资源范围、动作、效果、条件（与设计的三确认点一致）。
- 场景实例**详情页**：新增「授权规则」区块，可逐条「启用规则 / 暂停规则」；条件不可执行或
  分组场景时按钮禁用并说明原因。
- 说明：此前设计的"资源类型 / 动作 / 授权规则"三个目录页已在新版设计中取消，
  因此启用入口落在场景页，而不是恢复旧目录页。

### MCP · 治理目录补上授权规则状态

- 文件：`backend/mcp_server.py`
- 问题：`get_governance_catalog` 只返回分析阶段的 `policies` 草稿，**没有任何 `policy_status`**。
  智能体读目录后无法判断"这个场景的规则到底生效没有"，看到的规则内容也可能与实例编辑后
  重编译的条件不一致。
- 改动：
  - 每个已确认场景新增 `authorization_state`（`none` / `draft` / `partial` / `enabled` /
    `suspended` / `unknown`）、`authorization_state_note`（中文说明）、`rules_total`、
    `rules_active`、`activatable`，以及 `authorization_rules[]`（`policy_status`、`effect`、
    资源、动作、条件、可执行性问题）。
  - 状态来源是判定引擎真正读取的 `Authorization` 记录（走 `GET /scenario-slices/{id}/policies`），
    不再依赖 `analysis` 里的草稿。
  - 单场景读取失败降级为 `unknown` 并给出说明，不影响目录其余部分。
  - 更新工具描述，明确告诉智能体：`draft`/`suspended` 的规则不参与判定、`check_authorization`
    会返回默认拒绝，需要用户到控制台启用。
- 验证：以 stdio JSON-RPC 驱动真实 MCP 子进程（对接运行中的治理服务），
  实测返回 `authorization_state=draft (0/2)` 与逐条规则字段；另用 stub 覆盖
  `none/enabled/partial/draft/suspended/segmented/unknown` 全部分支。
- 说明：MCP 子进程由客户端启动，改动无需重启服务；客户端下次启动即生效。

### 前端 · 总览页重新设计

- 文件：`web/app.js` → `renderDashboard()`
- 问题：总览仍是初版形态——四张卡片是"主体 / 资源类型 / 动作 / 授权规则"的数量。这些对象
  在新版设计中已由场景自动生成、不需要单独维护，作为首屏指标已经没有意义。
- 新设计（回答两个问题：**我的场景现在能不能用／有什么需要我处理**）：
  - **四张状态卡**：已发布场景（智能体可通过 MCP 读取）、生效中的规则 `生效/总数`、
    待启用规则、判定记录（含最近一次时间）。
  - **由场景自动生成** 一行小字保留本体规模（主体/资源类型/动作），并注明不需要单独维护。
  - **需要你处理** 面板（有内容才显示，每条带跳转）：草稿场景未发布、已发布场景的规则未启用、
    模型服务未配置、后端离线。
  - **我的场景**：每个场景一行，显示是否已发布、规则条数与生效情况、更新时间，可直接进入管理。
  - **快速判定**：保留，并在没有生效规则时提示"判定结果会是默认拒绝"。
  - **最近判定**：保留，空状态改为可操作引导。
  - 后端不可达时不再整页报错，而是降级显示"服务离线"待办并给出服务监控入口。
- 顺带修复：`检查授权` 按钮同时带 `.button`（`display:inline-flex`）与 `.field`（`display:grid`），
  后者覆盖前者导致文字与"→"折成两行、箭头溢出按钮——改为内联 `grid-column:1/-1`。
- 验证：用无头 Chromium 渲染真实 `renderDashboard` + 真实 `app.css`，分别截图核对
  当前状态 / 健康状态 / 空状态 / 离线状态，并在 1180px（真实内容宽度）复查布局。

### 后端 + 前端 · 长期偏好与"本次执行值"分离

- 起因：WorkBuddy 读到的场景实例显示"北京丰台、今天入住明天退房、400 元、无烟房、要车位、
  安静、1 人 1 晚"。核实后确认是**系统缺陷**，不是理解偏差：
  - `analysis.intent` 存的是**那一次描述的原文摘要**，却被 MCP 当作场景描述返回；
  - `instance_preferences` 混进了 14 条，其中 `check_in_date=今天`、`check_out_date=明天`、
    `guest_count=1`、`duration_nights=1`、`booker_relation=本人`、`additional_requirements=暂无`
    等属于本次现场值，而且 `check_in_date`/`check_out_date`/`guest_count` **同时又是
    `required_inputs`**（既声明"每次都问"，又把某次的值固定成偏好）；
  - 最危险的是这些偏好一旦在场景实例页保存，会被编译成硬条件（`check_in_date = "今天"`）。
- 改动（三层）：
  1. **后端**（`backend/api.py`）新增 `_runtime_field_names()` / `_prune_preferences()` /
     `RELATIVE_TIME_PATTERN`：`required_inputs`（含分组维度）里的字段一律不写入偏好；相对时间值
     （今天/明天/本周/now…）不写入偏好。确认阶段若策略条件对运行时字段使用等值比较，降级为
     `exists`——规则只能要求"必须提供"，不能固定"必须是今天"。
  2. **前端**（`web/app.js`）：全局模式的偏好行新增「长期」勾选框。**从本次描述抽出来的值默认
     不勾选**，只有用户明确勾选才会写入实例并成为判定条件；已保存的实例偏好默认勾选。这是
     docs/03 §4"模型建议不是事实，必须由用户明确接受才能成为偏好"的最小落地。
  3. **MCP**（`backend/mcp_server.py`）：`intent` 更名为 `first_request_summary`，附
     `first_request_summary_note` 说明它只是首次描述摘要，并在工具描述里指明场景的可复用名称是
     `name`、长期偏好看 `preferences`、每次执行要收集的字段看 `required_inputs`。
- 数据清理：备份后经 API 重写 `scene_5765508d20d2` 的偏好，14 条 → 4 条
  （`budget_total≤400`、`quiet_environment`、`non_smoking_room`、`parking_required`）。
  规则条件里不再出现日期/人数/时长/关系等一次性值。备份：
  `backup/ontology-20261001-1737-before-preference-cleanup.ttl`。
- 补充：`scene_5765508d20d2` 新增运行时必填项 `guest_name`（入住人姓名）。酒店预订需要的姓名
  来自"每次执行由用户提供"，不取自主体目录（主体是授权对象，不等于入住人；`contacts` 也未对
  MCP 暴露）。实测：新增后判定对缺少姓名的请求返回
  `ask / decision.required_context_missing{fields:[guest_name]}`，智能体据此向用户询问；
  该字段未进入 `instance_preferences`，规则条件不受影响。
- 副作用（预期）：条件变化 → 生效中的 2 条规则**自动回到 draft** 并写入审计，需用户重新审核启用。
- 验证：后端集成测试 9/9；前端用真实 `readScenarioSegmentation` 单元测试（全部未勾选 → 不写入；
  勾选两条 → 只写入那两条）；MCP stdio 实测目录返回清理后的偏好与新字段名。

### 权限与隐私 · 主体目录共享

- **主体改名**：`principal_06b354287191` 的显示名由真名改为 `本人 / Me`。授权判定只认 ID，
  改名不影响任何规则；此前真名只在主体记录与 2 条验证判定记录里出现，现已全部清除
  （图中真名残留 0 处）。
- **清理验证数据**：删除我验证判定时写入的 3 条 `decisions` 记录（此前为 0 条），
  其中 2 条 `inputParams` 含真名。审计记录按设计是追加式，这 3 条属于测试产物，
  删除后你的判定历史从空开始。
- **打开主体目录共享**：`PUT /manager/agent-settings {include_principals:true}`，
  生成 `data/mcp-settings.json`。智能体重连后可读取主体目录（只有中性名）。
- **补齐 MCP 缺口**：`authorization_rules[]` 之前不返回主体，导致打开共享开关也无从对应。
  现补充 `grantor_id` / `grantee_id`，并在工具描述里说明"仅在允许提供主体目录时才能解析成名称"。
- 说明：主体是**授权对象**，不是订酒店要填的入住人；后者已作为运行时必填项 `guest_name`，
  由用户在每次执行时提供。

### 加密容器 · P0 清理 + P1 容器模块

设计依据：[docs/05](docs/05-secret-and-sensitive-data-design.md) v2.1。

- **P0 清理明文残留**：删除运行目录里 9 个未完成的图快照（`ontology-*.ttl`，268KB，
  8 个含真名）——它们是 `_persist()` 写入被中断留下的孤儿文件。活跃图 `ontology.ttl`
  未受影响（55 个类型断言完好）。
  `data/backup/` 下的 4 个 `*.before-migrate-*` 文件**未动**：其命名来自那些孤儿快照
  （`ontology-<随机>.ttl.before-migrate-*`），提示当时的迁移脚本可能把孤儿快照当成了图来源，
  来源待确认。
- **P1 容器模块**：新增 `backend/vault.py` —— 单文件、两个独立加密段
  （`ontology` / `model_service`）、PBKDF2-HMAC-SHA256 派生、AES-256-GCM 整段加密、
  临时文件 + 一次 `os.replace` 原子替换。
- **新增自检**：`tests/test_vault.py`，**34/34 通过**，覆盖——
  往返一致；磁盘上无明文/无口令/无凭据；权限 0600；错口令拒绝；
  密文篡改、头部参数篡改、**段间密文互换**均被 GCM/AAD 拒绝；
  未改动段原样搬运（不重复加密、不复用 nonce）；写入不残留临时文件；
  锁定后拒绝访问；改口令后旧口令失效、两段内容完好、错口令改密被拒；
  非容器文件与不支持版本被拒；**写入中断后旧文件仍可用**；
  真实迭代次数解锁耗时 235 ms（与实测基准一致）。
- 实现修正：`create()` 原先声称已解锁却不持有密钥（`get_section` 会 KeyError），
  改为创建时缓存派生密钥、直接可用。

### 加密容器 · P1 容器接入 + P2 登录界面（已部署）

- **存储层**（`backend/store.py`）：不再启动即读 `ontology.ttl`；改为锁定态启动，
  `unlock(password)` 时解密到内存，写入时重新加密回容器。删除字段级加密（`contact.key`
  与 `_decrypt_contact` 静默失败路径一并消失）。互斥锁改名 `_mutex`——原先 `self.lock`
  属性与新增的 `lock()` 方法同名冲突。
- **凭据模型**（`backend/api.py`）：`api-token` 被密码登录取代。新增 `/v1/setup`、`/v1/login`、
  `/v1/logout`、`/v1/lock`、`PUT /v1/account/password`、`GET /v1/account`。
  登录即解锁（口令既认证又派生容器密钥，GCM tag 充当唯一验证器，盘上无 verifier）。
  契约：未初始化 **409**、未登录/已锁定 **401**；登录失败指数退避（最多 30s）。
  口令策略落地：≥8 字符 + ≥3 类字符 + 高频弱口令表与规则检测。
  会话令牌只存内存（滑动 30 分钟），解锁期间写 `data/session-token`（0600）供 MCP 使用，锁定即删。
- **迁移**：`/v1/setup` 检测到明文 `ontology.ttl` 时自动迁移——解密后逐三元组校验
  （缺一条即保留明文并报错），通过后删除 `ontology.ttl`、孤儿快照、`api-token`、
  `model-service.json`、`model-service.key`，并把模型配置并入容器 `model_service` 段。
- **管理器**（`backend/manager.py`）：不再持有 `api-token`，改为把令牌交给后端 `/v1/account`
  校验；后端不可达时进入**本机恢复模式**（否则后端挂掉就永远无法通过鉴权重启它）。
  `/health` 改为透传后端真实状态（含 `initialized`/`locked`）。
- **前端**（`web/app.js`、`web/index.html`）：移除 API Token 对话框，新增「设置登录密码」与
  「本体已锁定」两个首屏（含实时强度提示、离线态提示）；新增「配置与监控 → 登录与安全」页
  （修改密码 / 立即锁定 / 容器状态 / 明文残留提示）。`api()` 在 401/409 时自动回到登录屏。
- **安装脚本**：`install.sh` 不再生成 `api-token`；`status.sh` 改为调用无需凭据的
  `/manager/health` 与 `/health`。
- **模型配置接入容器**（`backend/model_service.py`）：原实现仍读 `model-service.json`，
  而迁移会删除该文件——若不改，迁移后"模型服务"会显示未配置。现改为优先读写容器的
  `model_service` 段（未解锁时不可读、不泄露），仅在容器不可用时回退旧文件/环境变量。
  `api.py` 通过 `attach_store()` 注入 store 引用，避免循环导入。
- **MCP 按调用读取凭证**（`backend/mcp_server.py`）：原先启动时读 `api-token`，
  该文件迁移后即删除，会让 WorkBuddy 直接启动失败。现改为每次调用读取解锁期凭证
  `data/session-token`；锁定态返回明确文案"本体已锁定。请让用户先在本机控制台用登录密码解锁"。
- **清理逻辑修正**：原先只有检测到旧明文图时才执行清理，导致"有旧模型配置但无旧图"时
  文件残留（并使锁定后仍能从旧文件读到配置）。现改为始终清理已并入容器的旧文件，
  仅"明文图删除"以逐三元组校验通过为前提。
- **测试**：`tests/test_vault.py` 34/34；`tests/test_api_auth.py` 40/40（含迁移子进程场景）；
  模型配置容器化 9/9；另做**真实数据迁移演练**（副本上）24/24——419 条三元组全部保留、
  逐集合数量与真实图一致（1 场景 / 2 授权 / 12 动作 / 2 约束 / 23 参数 / 1 主体 / 5 资源类型），
  明文文件按要求清理，锁定后重新解锁数据完好。
- **部署状态**：后端与管理器已重启，当前 `/health` = `initialized:false, locked:true`，
  等待用户在控制台设置登录密码。迁移前的明文备份：
  `backup/ontology-20261001-2104-before-container-migration.ttl`（迁移成功后应删除）。

### 加密容器 · P3 剩余 + P4 + P5（已部署）

- **MCP 端到端实测**：新增 `tests/test_mcp_e2e.py`（13/13）——拉起**真实 uvicorn 后端**
  与**真实 stdio MCP 子进程**，覆盖：未解锁时给出明确文案、解锁后读到真实场景与主体、
  锁定后凭证文件被删除且 MCP 不崩溃、重新登录后立即可用（按调用读取凭证）。
- **审计字段最小化（P4）**：`store.evaluate()` 现返回 `context_keys_used`（判定实际读取过的
  上下文字段 = 约束引用的 key + source_trust）；`api._minimized_input()` 据此只保留这些字段，
  其余只记下键名到 `context_not_retained`。实测：判定携带的 `guest_name`、`check_in_date`
  等不再入库，而 `budget_total`、`source_trust` 与判定依据完整保留（11/11）。
- **主体显示策略（P4）**：`mcp-settings.json` 新增 `principal_display_mode`
  （`neutral` 默认 / `full` / `id_only`），MCP 目录据此呈现主体；「智能体接入」页新增三选一，
  选择「真实名称」时界面提示会进入模型上下文。三种模式逐一核对通过。
- **格式冻结与测试向量（P5）**：`backend/vault.build_section()` 支持确定性构造；
  `docs/05 §3.5` 冻结了一组跨语言测试向量（固定 password/salt/nonce/iterations →
  期望派生密钥、AAD、密文），`tests/test_vault.py` 第 12 组断言固定校验（37/37）。
  `version: 1` 标注为跨实现契约，变更须升版本号。
- **文档**：`docs/05` 的 §12 阶段表补上状态与验证证据，§13 更新待定项。

### 加密容器 · 浏览器端到端测试揪出两个严重缺陷（已修复并部署）

新增浏览器端到端验证：用真实 `index.html` 的 DOM + 真实 `app.js` + 真实后端（独立数据目录、
真实明文副本），在无头 Chrome 里走完"设置登录密码 → 迁移 → 总览渲染 → 登录与安全页"。
探针归档于 `tests/browser_e2e_probe.html`（用法见文件头注释）。

它抓到两个只有真机运行才能发现的缺陷：

1. **控制台白屏**：我在接入强度计时删掉了 `const bars`，但模板里仍引用 `${bars}` →
   打开控制台即抛 `ReferenceError: bars is not defined`，认证界面完全不渲染。
   `node --check` 是语法检查，抓不到运行期错误；此前的渲染自检用的是改动前的旧副本，也漏过了。
2. **迁移会毁掉 LLM API Key**：迁移把 `model-service.json` 原样搬进容器，而该文件里的
   `api_key_encrypted` 是用 `model-service.key` 加密的——迁移随后删除那把密钥，
   API Key 将**永久无法解开**（且"模型服务"会显示未配置）。此前的模型配置测试用的是空 Key，
   恰好绕过。现改为迁移时先解出明文再放入容器段（容器本身即加密层），并在读取时兼容
   仍带 `api_key_encrypted` 的历史段。实测迁移后 `configured=true, model=deepseek-flash,
   has_api_key=true`。

修复后浏览器端到端通过：首屏"设置登录密码" → 提交后进入总览（场景出现、状态卡齐全）、
迁移完成（`ontology.ttl`/`api-token`/`model-service.json`/`model-service.key` 均删除，
容器 49KB 可解密且不含明文）、「登录与安全」页显示 KDF 信息。

### 用户数据的真实迁移 + 三项收尾（已部署）

**你的数据已迁移完成**（你在控制台设置了密码）：`ontology.ttl` 419 条三元组进入
`ontology.po.json`（48.9KB），`ontology.ttl`、`api-token`、`model-service.json`、
`model-service.key` 均已删除；逐集合核对与迁移前一致（1 主体 / 1 场景 / 2 授权 / 12 动作 /
2 约束 / 23 参数 / 5 资源类型 / 2 判定），模型服务 `source=container` 且 API Key 保留。
顺带删除了已无保护对象的旧字段级密钥 `contact.key`（联系人 0 条，字段级加密代码已移除）。

按你的要求新增三项：

1. **常见口令表 1 万条**：新增 `assets/common-passwords.txt`（10001 条，源自 SecLists
   `10k-most-common.txt`，MIT；以 `#` 开头的行为注释）。`_looks_common()` 同时做
   整串、纯字母、去首尾数字符号三种归一化比对，并保留长度/字符类别/重复/键盘序列/年份规则。
   实测 `P@ssw0rd1`、`Qwerty123!`、`Sunshine99`、`Iloveyou1!`、`Admin123!` 全部被拒，
   强口令通过。`install.sh` 会复制 `assets/`。
2. **空闲锁定时长可配置**：新增 `data/settings.json`（0600）与
   `PUT /v1/account/session-timeout`（0–1440 分钟，0 = 不自动锁定，默认 30）；
   「登录与安全」页提供 5/15/30/60/120/480 分钟与"不自动锁定"选项。
3. **迁移列出 APFS 本地快照**：`_local_snapshots()` 调用 `tmutil listlocalsnapshots /`，
   迁移报告返回 `local_snapshots`，有快照且发生过迁移时附删除建议；
   「登录与安全」页常驻显示。**本机实测无快照**——没有历史明文残留。
4. **收尾**：启动时删除上一次运行遗留的 `data/session-token`（避免 MCP 读到失效令牌）；
   `contact.key` 纳入迁移清理列表。三项新功能自检 15/15，全量回归 37/37 + 40/40 + 13/13。

注意：本次重启后端使所有会话失效，需要重新登录一次（设计如此）。

### 清除最后的明文副本

按用户指示删除 6 个明文图副本（删除前逐个核验为普通文件、且容器结构完整）：

- `~/personal-ontology/data/backup/` 下 4 个 `*.before-migrate-*`（19:40，来源不明的迁移脚本产物，
  命名显示当时可能把孤儿快照当成图来源）——目录已随之删除；
- `workspace/backup/` 下 2 个迁移安全网备份——目录已随之删除。

**核验结果**：全盘搜索真实姓名，仅存在于加密容器 `ontology.po.json` 内；残留的 `.ttl` 只有
随代码发行的元模型（`ontology/shapes.ttl` 20 个 shape、`personal-properties.ttl`），不含个人数据。
运行目录现在只剩容器、日志与配置。

**代价**（已在界面上告知过）：明文安全网已全部移除，忘记登录密码将无法恢复数据。

### 修复：规则生成了却看不到（三处数据链路缺陷）

用户反馈"场景里没有授权规则，但总览显示有 2 条待启用规则，且看不到这两条"。核查发现是三个叠加缺陷：

1. **确认场景时未选主体 → 不生成任何规则，且事后无补救入口**。`confirm_scene` 只在
   `grantor_id && grantee_id` 时才编译规则；一旦以"待选择主体"确认，场景里的
   `policies`（模型已给出的规则草稿）就永远是草稿，再调确认会被 `already_confirmed` 挡回。
   **修复**：把规则编译提取为 `_compile_rules()`，确认与新增的
   `POST /v1/scenario-slices/{id}/compile` 共用；场景实例页在"有草稿但无规则"时显示提示与
   主体选择器 +「生成授权规则」按钮。自检 14/14（含幂等、运行时字段降级、偏好保留）。
2. **重新分析会丢掉 `generated` → 已创建的规则失去归属**。`analyze` 用新 analysis 整体覆盖
   记录，`generated.authorization_ids` 随之消失，之后删除场景时清理逻辑找不到这些规则，
   于是留下**孤儿规则**——这正是总览里那 2 条的来源（属于已删除的 `scene_8586d44e9790`）。
   **修复**：重新分析时保留上一版 `generated`；`delete_scenario_instance` 除按
   `authorization_ids` 清理外，再按 `source == scenario-slice:<id>` 兜底。
3. **孤儿规则既不属于任何现存场景，也不在总览待办里 → 无处可见、无处清理**（授权规则页已随
   目录页取消）。**修复**：总览「需要你处理」新增「孤立规则」条目（source 指向的场景已不存在），
   一键清理并二次确认；「待启用规则」这个数字从此可追溯。

注意：本次重启后端使会话失效，需要重新登录一次。

### 修复：切片页设了偏好，实例页却不选中、要重选一遍

用户反馈"在场景切片设置好偏好，到场景实例编辑时没有选中，要重新选一遍"。核查其数据：
`segmentation.global_preferences = 0`、`instance_preferences = 0`、`facts = 15`——**偏好根本没被保存**。
原因是上一版为阻止"一次性值自动变长期偏好"而引入的「长期」勾选框默认不勾选；用户在切片页
看到并编辑的那 15 行正是 `facts`，没勾就确认 → 什么都没存；到实例页因保存的偏好为空而回退
显示 facts（依旧未勾选），于是表现为"让我重选一遍"。

改动（`web/app.js`）：

1. **修掉一个连带 bug**：`saved?.global_preferences || a.instance_preferences` 中空数组在 JS 里是真值，
   会短路掉 `instance_preferences` 的回退——改为按 `.length` 判断。
2. **明确来源**：回退显示 facts 时，文案直接说明"下面这些来自首次描述，**还没有保存为长期偏好**——
   勾选「长期」才会保存，否则确认后不会出现在场景实例里"。
3. **实时计数**：说明行显示"已勾选 N / M 条长期偏好"，随勾选更新。
4. **改值即勾选**：手动编辑某行的值会自动勾上该行的「长期」——你既然改了值，就是要它。
5. **确认前拦截**：一条都没勾时点"确认并创建场景实例"，弹出说明并需二次确认，不再静默丢弃。

渲染自检：场景 A（偏好为空→回退 3 行、0 勾选、提示正确、改值后自动勾选）与
场景 B（已保存 1 条偏好→**1 行且已勾选**）均符合预期。

### 修复：长期偏好默认勾选（承接上一版"默认不勾"的错误方向）

用户再次反馈"重新走了一遍，实例页仍没有选中"。核查数据：`segmentation.global_preferences = 0`、
`instance_preferences = 0`、`facts = 9`——**偏好依旧是空的**。

用**运行副本的代码**直接测确认链路，证明后端没有问题（勾选的偏好被正确保存，不在
`required_inputs` 里的字段全部落库）。所以症结在默认值：上一版为阻止"一次性值自动变长期偏好"
而把 facts 行默认设为不勾选；用户看到预填好的值以为"已经设置好了"，直接确认 → 一条都没存。

**而运行副本里的新版 `scenario_llm.py` 已经把契约写清楚了**：facts = 长期偏好（一贯要求），
required_inputs = 每次执行重新收集的字段（城市/日期/人数）。按这个契约，facts 本就该默认选中。

改动（`web/app.js`）：facts 行的默认勾选**与后端的剔除规则对齐**——凡是出现在
`required_inputs` 或分组维度里的字段默认不勾（后端本来也会剔除它们），其余默认勾选。
说明文字同步改为解释这条规则。用户真实场景数据下的渲染结果：

```
[✓] 每晚预算  [✓] 无烟房  [✓] 安静  [✓] 停车位  [✓] 可开发票  [✓] 入住时间  [✓] 含早  [✓] 房型
[  ] 目的城市（每次执行才确定）
已勾选 8 / 9 条长期偏好。
```

端到端复验：默认勾选的 8 条 → 确认后 8 条全部保存为 `instance_preferences`，一次性字段被排除。

**同时修复一处协作风险**：运行副本里存在工作区没有的 `backend/field_names.py`（497 行，字段命名
契约：英文机器键 + 中文显示名）以及被改写的 `backend/scenario_llm.py`（强化提示词以区分
长期偏好与运行时字段，并在末段调用 `normalize_analysis`）。这两项已**同步回工作区**，
否则下一次部署会覆盖掉它们。当前两副本（backend 与 web）已完全一致。

### 修复：两条策略只生成一条规则 + 单条约束被当成 39 条

用户提问"授权规则如何产生、为什么这次只生成一条而不是两条"。核查其场景数据：模型给出
**2 条 policies**，`generated.authorization_ids` 也列了 2 个，但库里只存在 1 条规则，
且那条规则显示 **39 个约束**。查出两个缺陷：

1. **一条坏条件作废整条策略**：`policy_1` 含 `check_in_after_time gte "15:00"`——字符串做数值
   比较，被判定为非法条件，而当时的实现是"任一条件非法即 `continue` 丢弃整条策略"，
   于是 `policy_1` 从未生成。**修复**：改为**条件级容错**——只丢弃无法编译的那一条，
   其余照常入库；全部条件都非法时才跳过该策略（避免生成"无条件的 allow"），
   两种情况都写进 `compile_report` 返回给界面。同时修正 `authorization_ids` 会把
   "未真正创建的规则 ID"也列进去的问题（原先在合法性检查之前就 append）。
2. **多值字段单值读出退化成标量**：`graph_to_record` 只在字段出现多次时才累积成列表，
   只有 1 个约束时 `constraints` 返回字符串 `"scene_..._condition_1"`，调用方按字符迭代
   → 1 个约束显示成 39 个。**修复**：`model.MULTI_VALUED` 声明语义上多值的字段
   （`authorizations.{actions,constraints,redlines}`、`resource-types.{actions,params}`），
   读取时即使只有一个值也返回列表，缺失时返回空列表。

自检 10/10：2 条策略生成 2 条规则、`policy_1` 保留 3 条有效条件并说明丢弃了时间比较、
全坏条件的策略被跳过且有说明、单约束往返仍为列表。前端在确认/补生成后会把编译说明
以 toast 显示。全量回归 37/37 + 40/40 + 13/13。

### 新增：时间/日期约束（temporal_lte / temporal_gte）

判定引擎此前只支持数值大小比较，`check_in_after_time gte "15:00"` 这类条件无法编译，
只能整条丢弃。现在支持时间与日期比较：

- `store.parse_temporal()`：识别 `15:00`、`15:00:30`、`15点30分`、`下午3点`、`上午10点`、
  `2026-10-10`、`2026/10/10`、`2026年10月10日`、ISO 日期时间；会剥掉"之前/以后/前后"等修饰；
  纯数字不被当作时间（`400` 是预算）。
- 新增约束类型 `temporal_lte` / `temporal_gte`：判定时按时刻或日期比较，日期与日期时间
  可混比（按当日零点折算）；任一侧无法解析即**不命中**（保守，不让解析失败变成放行）。
- `_compile_condition()` 统一"条件 → 约束"的编译，确认场景与场景实例两条路径共用：
  数值 → `numeric_*`，时间/日期 → `temporal_*`，其余无法编译的只丢弃该条条件并回报。
- 启用规则时的可执行性白名单 `EXECUTABLE_CONSTRAINT_TYPES` 加入两个新类型——
  这道校验正好在工作时挡住了我：新类型未加白名单时启用会被拒绝并明确说明原因。

`tests/test_temporal.py` 13/13：时刻边界（含等号）、日期边界、斜杠/中文日期、
日期与日期时间混比、带秒时间、无法解析时保守不命中、数值比较不受影响。

**测试过程中发现的一个重要交互**：判定会先检查场景的必填字段，缺任何一个就返回
`ask / decision.required_context_missing`，**根本不会进入规则匹配**。写判定相关测试时
必须补齐必填项，否则会得到"假通过"。

### 修复：时间解析只认中文（双语缺陷）

用户指出 `parse_temporal` 里加了中文时段前缀（上午/下午），而系统要支持中英文双语。
这是实际缺陷，不是风格问题——我按观察到的中文数据写解析器，而不是按双语要求写。排查后确认两处：

1. **`parse_temporal` 中文丰富、英文缺失**：`15:00` / `下午3点` / `2026年10月10日` 都能认，
   但 `3 PM` / `3:30pm` / `Oct 10, 2026` / `10 October 2026` **全部解析失败**。
   后果不是"少识别一种写法"这么轻——编译时无法解析的条件会被**丢弃**，
   英文场景的时间条件会静默消失。现补齐：英文 AM/PM（含 `p.m.`、`12 am/pm` 边界）、
   英文月份名与序数词（`10th Oct, 2026`）、点号日期（`2026.10.10`）、英文修饰词
   （`before` / `no later than` / `by`）。
   **顺序有歧义的写法不猜**（`05/10/2026` 日月都可能 → 返回 None，由编译环节明确报出），
   因为猜错会把日/月调换后拿去卡判定，比解析失败更危险。
2. **`RELATIVE_TIME_PATTERN` 漏词**：已有 `today/tomorrow/yesterday/tonight/now`，
   但漏了 `next week`、`this weekend`、`in 3 days`、`下周三`、`3天后` 等。
   后果是这些一次性时间表达会被**当成长期偏好存下来**——正是此前反复出现的那类 bug。
   现按中英文对齐补全。

`tests/test_temporal.py` 扩到 **50/50**，其中解析层断言覆盖中英文时刻、日期、ISO 日期时间、
歧义拒绝、相对时间识别与误判。

**仍存在的双语缺口（未改，需要你决定）**：`scenario_llm.py` 的酒店确定性兜底路径硬编码中文标签
（"目的城市"/"入住日期"…），提示词第 160 行要求"label 必须是中文显示名"，前端取名字段也偏向
`display_name_zh`，且系统没有语言设置项。也就是说**用英文描述场景，得到的仍是中文标签**。
要不要做成跟随用户输入语言，需要先定方案。

### 新增：显示与语言设置（方案 2）

用户选择"界面语言设置"方案。实现范围是**数据与标签的语言**，界面自身文案另计（见文末）。

- **设置项**：`data/settings.json` 的 `display_language`（`zh` 默认 / `en`），与空闲锁定时长共用
  同一文件；`GET/PUT /v1/settings/language` 读写，`GET /health` 公开当前值（登录前界面也要用）。
  非法值一律回退 `zh`。
- **产出跟随语言**：`field_names` 增加 44 条英文标签表（`_LABELS_EN`），`default_label` /
  `display_label` / `normalize_facts` / `normalize_required_inputs` / `normalize_analysis`
  全部接受 `language` 参数；模型提示词里的"label 必须是中文显示名"改为按设置填充
  （含示例 `无烟房`/`Non-smoking room`）；酒店确定性兜底路径的 5 处硬编码中文标签改为
  交由标签表按语言填充。机器键**始终**是英文 snake_case，与语言无关。
- **展示跟随语言**：前端 `serviceHealth()` 顺带同步语言；新增 `fieldLabel()`，
  `displayName()` 与名称列按语言取 `display_name_en` / `display_name_zh`，缺失时互相回退。
- **界面入口**：「配置与监控 → 显示与语言」新增页面与导航项。
- 自检 9/9（默认值、切换、health 反映、非法拒绝、与锁定时长共存于同一设置文件）；
  全量回归 37/37 + 40/40 + 13/13 + 50/50。

**未做（需另行决定）**：界面自身的按钮／菜单／提示等约 630 条中文文案**没有翻译**。
页面里已明确写出这一点。真要做需要把所有字符串抽成词典并逐个替换，是独立的一轮工作。

### 修复：切到英文后界面仍是中文（界面文案翻译）

用户设了英文、保存、刷新，界面仍然全中文。查证：设置确实存了（`settings.json` 与 `/health` 都返回 `en`），
前端也确实读到了——**问题是我上一轮只做了数据标签，界面自身的 618 条文案压根没翻译**，
而且对已有数据几乎看不出差别（多数记录没有英文名）。这等于没解决用户的诉求。

改动：

1. **新增 `web/i18n.js`**：581 条中英词条 + 12 条动态规则（计数、状态拼接等）+ 句内片段规则。
   采用"渲染后遍历文本节点做精确匹配"的方式，而不是把 app.js 里 600 多处字符串逐个改成 `t("...")`
   ——那些串大量嵌在模板字符串里，逐个替换的回归风险高得多。
   表格单元（用户数据）与输入控件被跳过，避免误伤数据：实测切到英文后仍含中文的可见节点
   **只剩 1 个，且正是用户自己的场景名「预订酒店」**。
2. **修一个真实缺陷**：`refreshService()` 自己直接 `fetch("/health")`，从不调用 `serviceHealth()`，
   导致登录状态下语言标志**永远不会被设置**——这是"设置了英文却没反应"的直接原因。
   现改为复用 `serviceHealth()`。
3. **修 `window.displayLanguage`**：`displayLanguage` 是 `let` 声明，不是 `window` 属性，
   i18n 模块读不到就会永远跳过翻译。现由 `setDisplayLanguage()` 同步到 `window`。
4. 界面即时生效：切换语言后重渲染并立即重翻，无需刷新页面。

实测（真实后端 + 无头浏览器，`display_language=en`）：侧栏 Overview / Principals / Scenario slices /
Scenario instances / Scenario preview / Decisions / Model service / Agent access / Service monitor /
Display & language / Login & security；仪表盘 Ontology overview、四张统计卡、My scenarios、
Quick decision 表单全部英文。覆盖率：词条覆盖 562/563（99%），渲染后残留中文 1/101 个节点。

### 语言：保存后自动刷新 + 首次访问跟随系统语言

用户提出两点，都已实现。

1. **保存语言后自动刷新**：原先保存后只重渲染，改为提示"语言已保存，正在刷新…"后
   `location.reload()`（350ms）。刷新是必要的——`i18n.js` 是新文件，且侧栏等外壳由
   `index.html` 提供，必须重新加载才能整体生效。
2. **语言优先级：用户设置 → 系统语言 → 中文**。
   - `config.stored_language()` 只返回**用户显式设置**的值（未设置返回 `None`），
     `normalize_language()` 把 `en-US` / `zh-Hans-CN` 之类收敛成 `zh|en`，
     `display_language(hint)` 按上述优先级取有效值。此前"未设置"与"设为中文"无法区分，
     是这次要改的核心。
   - `GET /health` 返回 `display_language`（未设置时为 `null`），前端据此决定是否回退到
     `navigator.languages`；未登录的登录/设置页也能因此显示正确的语言。
   - 前端每次 API 调用带 `X-Display-Language` 头；后端在**用户未设置**时用它决定模型产出的
     标签语言（`analyze` 端点读取该头）。MCP 等无该头的调用回落中文。
   - 「显示与语言」新增「跟随系统语言（English/中文）」选项，对应 `PUT {"language":"auto"}`：
     清空显式设置、回到跟随系统。页面会显示当前是"由你指定"还是"跟随系统"。

   自检 12/12：未设置 → `null`/`configured=false`；未设置 + `en-US` → en；用户设 zh 时
   `en-US` 不覆盖；可切回 auto 并重新跟随系统；非法值仍拒绝。
   测试辅助 `call()` 增加自定义请求头支持（顺带修掉一处参数被局部变量遮蔽的问题）。

### 文档：README 补上双端口说明并修正过时的登录流程

用户问"为什么 web 起了 8765 和 8766 两个端口"。查证后确认这是有意分工，但 README 只写了
一句话，且残留了已被密码登录取代的 `api-token` 流程（三处，含可直接复制的 curl 示例——
照着做会失败）。现更新：

- 用表格写明两个端口的职责：`127.0.0.1:8765` = 控制台/服务管理器（页面、静态文件、
  `/manager/*` 管理端点，并把 `/v1/*` 反向代理到后端，**始终运行**）；
  `127.0.0.1:8766` = 治理后端（本体数据 + 授权判定引擎，由管理器启动/停止/重启）。
- 写明**为什么分成两个**：后端崩溃或配置写坏时管理器仍在，页面仍打得开，可以从
  「服务监控」重启后端并查看 `data/server.log`；合并成一个进程就会出现"重启后端连带杀掉
  你正在用来修复它的页面"。
- 移除 `data/api-token` 相关说明与示例，改为登录换取会话令牌的 curl 流程，并注明
  未初始化 409 / 未登录或锁定 401 的契约，以及解锁期间临时 `data/session-token`（0600）的用途。

实测：两个端口都**只监听回环地址**；`curl 8765/health` 返回的是后端负载（证明代理生效）；
launchd 两个服务均在运行（管理器 PID 588、后端 PID 1059）。

### 修复：后端端口也能打开控制台（重复且半坏的入口）

用户发现浏览器访问 `127.0.0.1:8766` 也能看到控制台，且界面与 8765 一样。查证属实：
`backend/api.py` 里同时有 `@app.get("/")` 返回 `index.html` 与 `/assets` 静态挂载——这是
引入服务管理器之前的遗留，两处都忘了移除。

问题不只是"多一个入口"：从 8766 打开的页面，点「服务监控」「智能体接入」会 **404**，
因为 `/manager/*` 只存在于管理器。看起来能用、其实半坏，比直接打不开更糟。

修复：后端 `GET /` 改为 **307 跳转到服务管理器**（`http://127.0.0.1:8765/`），
不再返回 `index.html`。管理器只把 `/v1/*` 反向代理给后端，`/` 由管理器自己处理，
因此不会形成跳转环。`/assets` 保留（开发与测试探针直接取静态文件用），并已把
`tests/browser_e2e_probe.html` 取外壳的地址从 `/` 改为 `/assets/index.html`。

实测：`8766/` → `307 → http://127.0.0.1:8765/`；`8765/` → `200 text/html`；
`8766/health` 与 `/v1/*` 不受影响；全量回归 37/37 + 40/40 + 50/50 + 13/13。

### 修复：status.sh 报 FileNotFoundError（模板改了但已装副本没更新）

用户执行 `./status.sh` 报 `FileNotFoundError: .../data/api-token`。原因是 `status.sh` 由
`install.sh` 在**安装时生成**：上一轮我把 `install.sh` 里的模板改成了调用公开健康检查端点，
但**已装好的那个副本仍是旧版**（还在读 `api-token`，而该文件已随密码登录改造删除）。
这是流程漏洞，不只是漏了一个文件。

处理与排查：

1. 把 `install.sh` 中的最新 `status.sh` 模板写入 `~/personal-ontology/status.sh`（0755），实测正常：
   分别输出管理器与后端的状态，并提示 locked 时去控制台解锁。
2. **全面核对所有已装产物**：`start.sh`、`stop.sh` 与模板一致；`backend/`、`web/`、`ontology/`、
   `assets/` 与工作区一致；LaunchAgent 两个 plist 的启动命令与端口正确。
3. 发现并修复另一处同类问题：**已装的 `README.md` 是旧版**（5923 字节，仍描述 `api-token` 流程），
   已同步工作区修正版（7455 字节）。
4. `backend/config.py` 里的 `TOKEN_FILE`（指向 `data/api-token`）**保留**：它现在只用于迁移时
   删除这个历史遗留文件，不是活跃凭据路径。

注：`scripts/migrate_field_names.py` 是此前解决"中文字段名被替换成 `____`"的一次性迁移脚本
（默认 dry-run，`--apply` 才写入）；它不含备份逻辑，因此先前那批 `before-migrate-*` 备份并非它产生。

### 修复：服务监控把"模型服务配置"显示为未运行

用户反馈：模型服务已配置、测试连接也通，但「配置与监控 → 服务监控」里"模型服务配置"显示**未运行**。

根因与之前那类问题同源：`/manager/status` 在**管理器进程**里调用 `model_service.public_settings()`
读配置，但模型配置存放在**加密容器**里，只有解锁的治理后端能解密——管理器没有（也不该有）
登录口令，于是 `_container_section()` 返回 None，代码回落到**已被迁移删除的旧文件**
`model-service.json`，最终判为"未配置"。

修复：

1. **模型配置改由后端提供**：管理器新增 `_backend_model_settings()`，转发调用方的会话令牌
   调用后端 `GET /v1/settings/model-service`。读不到时返回 `configured: None`（"未知"）并附原因，
   **不再谎报成"未配置"**：无令牌 → "需要登录"；401/409 → "本体已锁定，先解锁"；连不上 →
   "治理后端未运行"。实测已配置时返回 `configured: true · deepseek-flash · has_api_key: true · source: container`。
2. **前端服务监控支持三态**：`运行中 / 未运行 / 未知`，未知时把原因显示出来，
   避免把"读不到"误报成"没配置"。
3. **顺带修正 RDF 存储检查**：原判断基于旧的 `ontology.ttl`（`not exists or ...`，迁移后恒为真），
   改为检查加密容器 `ontology.po.json` 是否存在且可读写。

过程中我自己踩了一个坑：辅助函数插入位置错误，被夹在路由装饰器与 `manager_status` 之间，
导致装饰器挂到了辅助函数上（`authorization` 变成查询参数 → 422）。已修正并在部署后复验。

### 新增：跨机使用（远程智能体）——方案 A：SSH 隧道 + 远端运行 MCP

用户问"智能体和本体不在同一台 PC 上、走网络连接该怎么配置"。核查后确认这不是配置问题：
**MCP 使用 stdio 传输**，客户端只能启动**自己那台机器**上的进程；两个 HTTP 服务又都只监听
`127.0.0.1`。架构里根本不存在可供远程智能体访问的入口。同时确认**不能**靠改
`PERSONAL_ONTOLOGY_HOST=0.0.0.0` 解决：接口只有本机会话令牌一道防线，没有 TLS、
没有按智能体分发的可撤销凭据、没有远程来源防护，而 `/v1/*` 可读取整个本体；
Origin 白名单只挡浏览器 CSRF，**不挡 curl 与脚本**。

用户选择方案 A（本机零新增网络暴露），且**不需要无人值守**（用前手动解锁，密钥模型不变）。

实现：

1. **MCP 令牌可来自环境变量**（`PERSONAL_ONTOLOGY_SESSION_TOKEN`）：跨机时令牌文件在原机上，
   远端通过 SSH 取回后经环境变量传入；本机行为不变（仍读 `data/session-token`）。
2. **基址可覆盖**（`PERSONAL_ONTOLOGY_MANAGER_URL`），默认仍是 `http://127.0.0.1:8765`，
   跨机时指向隧道在本机的出口。
3. **错误提示区分场景**：401 提示"锁定或令牌已失效（重新解锁会换令牌），跨机需重启 MCP 连接"；
   连不上时提示"本机请确认服务已启动；跨机请确认 SSH 隧道仍在运行"。
4. **`scripts/mcp-remote.sh`**：远端包装脚本——校验 Python ≥3.11、检查隧道就绪、
   经 SSH 取回解锁令牌、以 stdio 启动 MCP。修了一处 **bash 3.2 兼容问题**
   （macOS 自带 bash 在 `set -u` 下展开空数组会报 `unbound variable`）。
5. **`docs/06-remote-agent.md`**：拓扑图、两侧步骤、客户端配置、行为与限制、安全要点。
   远端**只需 3 个文件**（`backend/{__init__,config,mcp_server}.py`，纯标准库、无需 pip），
   已实测：复制到别处用系统 Python 3.11+ 运行成功（用 3.9 会因类型语法报错，脚本已前置拦截）。
6. README 补充跨机说明与"不要改成 0.0.0.0"的警告；顺带修正 README 中已失效的备份说明
   （仍在讲 `data/ontology.ttl` 与 `data/contact.key`，实际已是加密容器 `ontology.po.json`）。

测试：`tests/test_mcp_e2e.py` 扩到 **15/15**，新增"令牌只来自环境变量（本机无令牌文件）"与
"令牌失效提示明确"两条断言。全量回归 37/37 + 40/40 + 50/50 + 15/15。

### 新增：本机智能体访问控制（T1+T2+T3+T4）

用户要求：本机未授权的应用/智能体不得在未确认的情况下通过 MCP 获取本体任何信息。

**先确认硬限制**：同 uid 的进程即同一主体，纯软件 + 落盘凭据无法区分"已批准的智能体"与
"以你身份运行的恶意程序"；唯一硬边界是硬件密钥 + 用户在场（Touch ID），本层未含。
但当前设计有一处**很具体的弱点**：`data/session-token` 是明文 bearer 令牌，同机任何进程读一行
即可**静默取走整个本体**。这一层就是来堵它的。

- **T1 取消落盘凭据，改用 Unix 域套接字 + 进程身份**：新增 `backend/peercred.py`
  （macOS `LOCAL_PEERPID`/`LOCAL_PEERCRED` + `proc_pidpath` + `KERN_PROCARGS2` 取命令行）与
  `backend/agent_gateway.py`（后端进程内的套接字网关，`data/agent.sock` 0600）。
  网关注入**仅存在于内存**的 HMAC 身份断言，API 端校验签名——伪造断言一律 401。
  命令行识别能把 `python -m backend.mcp_server` 与任意 Python 脚本区分开。
- **T2 默认拒绝 + 控制台批准**：`backend/agent_access.py` 维护客户端清单
  （pending/approved/denied，含可执行文件、命令行、首末次时间、批准次数）；
  未批准即 403 并提示"请在控制台「智能体授权」中批准"。新增页面「配置与监控 → 智能体授权」
  与总览待办提醒；可允许、拒绝、改范围、撤销、移出清单，撤销立即生效。
- **T3 范围最小化**：`catalog`/`rules`/`decisions`/`principals`/`check`/`preview`/`feedback`，
  默认不含 `principals`；MCP 只用 8 个端点，逐条映射到范围；管理类接口与自我提权对智能体一律 403。
- **T4 恢复模式收紧**：后端不可达时仅放行 `health`/`start`/`restart`（原先整个 `/manager/*` 全放行）。
- **跨机接入改为显式开启**：`data/session-token` 默认**不再写入**（它一旦存在即可绕过智能体授权），
  确需跨机时在界面上开启；关闭时保留调用者会话，不把人踢下线。

自检：`tests/test_agent_access.py` **24/24**（含伪造断言、自我提权、撤销即时生效）；
`tests/test_mcp_e2e.py` **17/17**（适配"默认未授权"，新增未授权拦截断言）；
`tests/test_api_auth.py` **42/42**（改为验证令牌默认不落盘、显式开启后才写入）。
文档：新增 `docs/07-local-agent-access.md`。

**未做**：T5（Secure Enclave / Touch ID 硬边界）——经用户决定**作为后续功能**推进，设计草图、取舍与开工前需确定的三项已写入 `docs/07-local-agent-access.md` 第 7 节。

### 规划：iOS App 实施计划（原生 Swift，全本机运行）

评估"把本体做成 iPhone/iPad App"的可行性与工作量，用户决定：**直接做原生 Swift 全本机版本**，
手机**独立一份数据、手工导出/导入**，**运行时零第三方依赖**，iOS 18.7+。

量化依据：后端 **4,665 行 Python / 13 个模块**、SHACL **20 个形状 / 91 个属性**、
**40 个端点 / 6 个 MCP 工具**、前端 188 KB（可原样复用）。

结论：**可行**，P0–P8 合计 **14–22 周（4–6 个月）**，详细任务、每阶段验收标准与测试清单
写入 `docs/08-ios-app-plan.md`。要点：

- **运行时零第三方依赖**成立：CryptoKit（AES-GCM）+ CommonCrypto（PBKDF2）+ Network +
  WebKit + SwiftUI + Security/LocalAuthentication + AppIntents 全是系统框架。
  唯一需自研的替代品是 **Turtle 子集解析器**（无成熟 Swift RDF 库；不引入 Serd/Redland）。
- **P0（容器读写）是 go/no-go 门槛**：用 `docs/05` §3.5 的冻结测试向量在真机验证，
  一次对上即说明格式无歧义。
- **控制台零重写**：`web/` 是 HTML/JS，用 WKWebView + 本机回环服务宿主，双语与授权页等全部沿用。
- **MCP 在 iOS 上不成立**（后台限制使第三方客户端无法启动 stdio 子进程），改用 **App Intents /
  快捷指令**，这反而更贴合平台。
- **手工导出/导入不需要额外加密**：容器本身就是密文，AirDrop/文件 App 传递即安全。
- 顺手把 **T5（Secure Enclave / 生物识别）** 在 iOS 上落地——那里是原生能力。

### 修复：策略无法按动作区分，导致"禁止删除"退化成"否决一切"

用户要求先用**场景切片 + 大模型推演两轮**来设计三个内置场景（文件/应用/网络连接），
而不是手写。推演（deepseek-flash，每域两轮）暴露出一个**模型层面的缺陷**：

- 模型两次都想表达"允许读、禁止删"，但 `policies` 只有 `subject/resource/effect/conditions`，
  **没有 actions 字段**；而 `_compile_rules` 把场景的**全部动作**塞给**每一条**规则。
  于是"禁止删除"被写成一条**无条件 deny**——因 deny 优先级最高，它会**否决该场景的全部动作**，
  连读取也一并拒绝。这是会导致规则不可用的实际缺陷，不是提示词措辞问题。

三处修复：

1. **策略可按动作限定**：提示词要求每条 policy 声明 `actions`（取值必须是本场景动作名称），
   `_compile_rules` 按名称映射成 action id；未声明或名称对不上时回退全部动作并记入说明。
   实测："允许查看/编辑 + 禁止删除"编译成两条**动作不重叠**的规则。
2. **拒绝无条件 deny**：场景还有其他策略时，一条无 conditions 的 `deny` 会被跳过并明确报出
   （"无条件的拒绝会否决该场景的全部动作"），避免静默产生不可用规则。
3. **禁止跨领域扩张**：提示词明确要求不得因补充回答提到其他领域就新增资源类型或动作
   （推演中发现"文件"场景吞并了"网络连接"的资源类型与动作）。

`tests/test_policy_actions.py` 7/7；全量回归 50/50 + 42/42 + 37/37 + 24/24 + 17/17。

推演产出的三个草稿场景（`处理文件` / `启动本机应用` / `联网获取信息`）**尚未确认**——
需在修复部署后用修好的提示词**重新分析一轮**再确认。

### 修复：场景只能落地第一个资源类型（推演发现的第四个缺口）

重跑推演后发现"文件"场景提出的 **`目录`** 被静默丢弃：`confirm_scene` 只处理 `types[0]`，
`generated` 只记一个 `resource_type_id`，所有规则也都挂在它上面。

修复（与"策略按动作限定"对称）：

- **资源类型逐一落地**：遍历 `resource_types`（上限 10），各自的 `existing_id` 可复用；
  首个沿用 `scene_<suffix>_resource` 以保持向后兼容，其余为 `..._resource_N`；
  `generated` 新增 `resource_type_ids` 与 `created_resource_type_ids`。
- **策略按资源类型各归其位**：`_compile_rules` 建立资源类型名 → ID 映射，
  每条策略按其 `resource` 字段决定规则挂在哪个资源类型上，缺失或对不上时回退第一个。
- **删除场景时清理自己创建的全部资源类型**（原先只删一个）。

`tests/test_multi_resource.py` 6/6（两个资源类型都落地、规则分别挂到文件与目录、动作亦各归其位）。

**本轮推演共查出并修掉四个模型层面的缺口**：① 策略缺 `actions` 字段（导致"禁止删除"退化为
否决一切）② 无条件 deny 未拦截 ③ 跨领域扩张（文件场景吞并网络连接）④ 多资源类型丢失。

### 修复：场景切片页两处 UI 问题 + 酒店兜底路径 500

1. **500 Internal Server Error（我的 bug）**：给 `add_fact` 加 `language` 时漏了
   `_hotel_fallback` 这一层——它是独立函数，没有 `analyze` 的局部变量 `language`，
   于是"文本含酒店"且"模型返回空数组"时触发 `NameError`。已让 `_hotel_fallback` 接收并透传
   `language`；补 `tests/test_hotel_fallback.py`（4/4，含中英双语、向后兼容、非酒店不触发）
   ——**这条路径此前零测试覆盖**，所以才溜过去。
2. **已确认的场景仍留在"场景草稿"清单**：`load("scenario-slices")` 没有状态过滤。
   现按 `status !== "confirmed"` 过滤，标题改为「未确认的场景草稿」；侧栏计数仍为全部场景数。
3. **草稿清单的位置**：按用户要求移到详细页（分析结果与偏好编辑器）**之前**，
   顺序为 标题 → 描述你的场景 → 未确认的场景草稿 → 详细页。

前端改动已部署（刷新页面生效）。顺序经结构化校验（区块偏移），非盲改。

### 字段三档分类（必填 / 长期偏好 / 两者兼有）与分档可见性

**背景**：用户指出"很多输入项到底是偏好还是每次必填"很模糊，并要求让模型在场景分析时
给出分类建议。两轮场景切片推演确认了这个缺口：此前系统**明确禁止**"既是必填又是偏好"
（`_prune_preferences` 丢弃运行时字段的偏好；`_compile_rules` 把运行时字段的条件降级为
`exists`），因此"既有长期立场、值又每次不同"（如"只订未来 30 天内的"+具体日期）无法表达。

改动：

1. **第三档"两者兼有"**：允许字段同时出现在 `required_inputs` 与偏好中。
   `_prune_preferences` 不再因字段是运行时字段而丢弃（只丢一次性相对时间）；
   `_compile_rules` 仅对**未被声明为长期偏好**的运行时字段降级为 `exists`，
   声明为兼有的字段**保留立场条件**。实测：兼有字段 → `numeric_lte`（立场保留），
   纯必填字段 → `context_exists`（降级）。`tests/test_both_tier.py` 4/4。
2. **提示词三档分类 + 理由**：每个字段须给 `role`（required/preference/both）与
   `role_reason`；并明确"不要为省事把模糊字段一律塞进必填"。
3. **role 穿过规范化层**：`normalize_*` 会重建对象且可能改名（budget_max → price_max），
   因此按 `changes` 的改名记录建别名表搬运 `role`/`role_reason`（`_carry_role`）。
   同时 `role="both"` 的字段不再被 `NEVER_RUNTIME` 降级出必填清单。
4. **兜底路径补档**：分析出口为缺 `role` 的字段补默认档位，避免界面显示"未标注"。
5. **分档可见**：切片页可折叠摘要（计数 + 逐条理由）、实例页编辑器内联徽章。
6. **待办提醒**：总览「需要你处理」新增"N 个场景的字段分档建议待你核对"；
   摘要行对未确认场景显示 `待核对` 徽章 + 琥珀底色，**确认后自动降级为普通样式**
   （确认动作本身即"已核对"，无需新增状态字段）。

`tests/test_ui_consistency.py` 新增：导航项 ↔ 路由 ↔ 渲染入口的一致性检查
（今天两次踩坑：导航项漏写、渲染片段归属判断错误）。当前 5/6 通过，
唯一告警是 4 个零引用的死路由（旧目录页残留）待清理。

### 场景分析契约：可执行的 schema 与运行时校验

`docs/09-scenario-analysis-schema.md` 冻结分析结构后，进一步让它**可执行**：

- `schemas/scenario-analysis.schema.json`：JSON Schema（2020-12），供程序校验与
  其它实现（如 Swift 侧）对齐，不必读 Python 反推。
- `backend/analysis_contract.py` 的 `validate_analysis()`：在分析出口
  （`scenario_llm.analyze`）调用，结果写入 `analysis.contract_notes`。
  **违规不阻断**（延续"坏的那条降级、不整批作废"），只记录，界面提示。
- 能自动抓到的违规：策略缺 `actions`、策略引用不存在的动作、**无条件 deny**、
  字段缺/错 `role`、字段名非英文键、重复字段名、三档与两个清单不一致、
  无资源类型/无动作、缺标题。
- 界面：切片页摘要行显示"N 处契约提醒"徽章，展开逐条列出。
- `tests/test_analysis_contract.py` 10/10，覆盖 docs/09 §7 记录的五类模型陷阱。

**过程记录（重要）**：首次接入 api.py 时锚点落在语句中间，切断了 `analyze_scene`
的函数体，导致**后端启动失败**；全量回归立即暴露（4 套 SyntaxError + 2 套"后端未就绪"），
随即回滚该处插入、恢复服务，改用 `scenario_llm.analyze` 出口的稳定锚点重新接入并通过回归。
教训：**改动后端的插入必须用独立语句作锚点，并且部署前先跑回归**——本次正是如此才没有留下故障。

### 2026-10-02 迭代汇总

**模型能力（由"用大模型+本体推演两轮"驱动查出并修复）**

1. 策略缺动作维度 → "禁止删除"退化为**否决一切**（新增 `policies[].actions`）
2. 无条件 deny 未被拦截 → 会静默产生不可用规则（改为跳过并报出原因）
3. 跨领域扩张 → "文件"场景吞并"网络连接"（提示词约束）
4. 多资源类型丢失 → 只落地 `types[0]`，"目录"被静默丢弃（改为逐一落地，规则按资源类型分流）
5. 字段分档模糊 → 新增**三档**`required`/`preference`/`both`，并让模型给出 `role_reason`

**修正的实际缺陷**

- 酒店兜底路径 `NameError`（我引入的，因 `_hotel_fallback` 没有 `analyze` 的 `language` 局部变量）→ 修 + 补齐零覆盖的测试
- 偏好操作符与值类型不匹配导致"确认并创建场景实例"整体 422 → 非数值的大小比较降级为等值比较，未知比较方式报错点名到字段
- 已确认的场景仍留在"场景草稿"清单 → 按 `status !== "confirmed"` 过滤

**界面**

- 场景切片页：草稿清单移到详细页之前、只列未确认场景、"模型对字段的分档判断"可折叠摘要
- 分档可见与改档：偏好行 / 必填行**双向**三档切换；未确认场景显示 `待核对` 徽章与琥珀底色，
  总览「需要你处理」新增待办，**确认后自动降级**（无需新增状态字段）
- 删除 4 个零引用死路由（旧目录页残留）

**契约与防护（新增）**

- `docs/09` + `schemas/scenario-analysis.schema.json` + `backend/analysis_contract.py`
  → 让"模型输出是否仍合规"可被执行检查，13 类违规自动抓取，违规不阻断只记录
- `tests/test_ui_consistency.py`：导航项 ↔ 路由 ↔ 渲染入口一致性（今日两次踩坑的根源）
- `scripts/verify-deploy.sh`：部署一致性校验（今日踩了 4 次"改了源码没同步"）

**过程记录**：接入契约校验时锚点落在语句中间，**切断 `analyze_scene` 函数体导致后端启动失败**，
由全量回归当场发现、回滚后改用安全锚点重接；随后又发现首次部署未同步 `analysis_contract.py`，
使校验在生产环境静默失效，由新写的 `verify-deploy.sh` 抓到。两次都是工具发现问题，而非人工碰巧。

### 修复场景预演跳转 Bug + i18n 机制补强（插值串与标签本地化）

1. **场景预演页选实例跳到总览（功能 Bug）**：`$("#preview-scene").onchange` 里给
   `location.search` 赋值会触发浏览器**整页导航**，SPA 重启后落到默认页。
   改为 `history.replaceState(...)`（只更新地址栏），页面渲染仍从
   `URLSearchParams(location.search)` 取场景，行为不变但不再重载。
2. **i18n 符号前缀回退**：按钮文本常把图标与文字放在同一文本节点（"↻ 刷新"、"＋ 新建"），
   精确匹配落空且扫描器只抽中文片段 → 这类缺口不可见。`translateText` 现在会剥掉开头
   符号与空白再查一次，命中后接回前缀（`PREFIX_RE`）。`tests/test_i18n_text.py` 8/8。
3. **插值串规则**：新增 14 条 `RULES`，覆盖「已有场景实例 · N」「授权规则 · N（M 条生效中）」
   「实例演进与执行记录 · N」「等待你批准 · N」「已授权/已拒绝 · N」以及搜索框
   「搜索主体…」（函数式规则，捕获的标题也走词典）。`tests/test_i18n_rules.py` 8/8。
4. **字段标签按显示语言本地化**：场景分析产出的标签固定为分析当时的语言，切英文后旧场景
   仍显示中文。新增 `_localize_scene_labels()`，在 `/v1/{collection}` 与
   `/v1/{collection}/{item_id}` 读取时重新取用：已知字段用 `field_names` 的规范英文标签，
   自定义字段含中文时退回英文字段键。**只影响展示，不写回存储**。
   `tests/test_label_localization.py` 6/6。
5. i18n 词典分批补齐 203 条（侧栏、智能体授权页、各页面标题/按钮/表单/状态/空态、长句说明），
   `web/index.html` 侧缺口已归零；新增覆盖率防回退基线（`tests/test_i18n_coverage.py`）。

### 确立第一性原则：全栈中英双语

用户明确要求：双语**不只页面**，而是界面文案、后端消息、数据标签与对象、
安装手册、使用手册、设计文档、变更日志——**一切都要中英双版本**，并以此作为一切工作的首要取舍。

- 新增 `docs/00-first-principle-bilingual.md`：分层要求、命名约定、**可执行检查**、例外（用户自撰内容不翻译、机器键恒英文）、
  以及五条实施纪律（验收对象是服务器给出的文件、改前端必须升版本号、不用自写解析器校验、
  幂等检查要针对具体产物、按"整行"报告中文残留）。
- README 顶部引用该原则。
- 诚实盘点：界面与数据标签 🟢/🟡；**后端消息、设计文档、README/手册、CHANGELOG 仍为 🔴 仅中文**，
  推进顺序见该文档第 5 节。

### 修复语言优先级缺陷（让整个本地化层真正生效）+ 后端消息目录

**根因**：`config.display_language()` 原先写成 `stored_language() or normalize_language(hint) or "zh"`，
落盘的旧设置永远优先 → **请求头 `X-Display-Language` 被完全忽略**。
后果是所有"按请求语言"的本地化形同虚设：数据标签、授权范围标签、后端消息
在英文界面下仍返回中文。前两轮我一直在下游逐条修补，属于治症。

修正为请求头优先、落盘设置仅作无头回退。**验收（直接打后端接口）**：

```
POST /v1/login  X-Display-Language: zh → {"detail":"请输入登录密码。"}
POST /v1/login  X-Display-Language: en → {"detail":"Enter the login password."}
```

**后端消息目录**（`backend/messages.py`）：中英双语键值 + `msg_for(key, language)`；
业务代码用 `messages.detail(key, **kwargs)` 携带消息键，由
`@app.exception_handler(HTTPException)` 按 `request` 解析语言——这样不必给
69 个端点加 `request` 参数。（中间件与依赖里设 contextvars 均实测无效。）

首批转换 13 处（登录/账户、场景偏好与分组校验），后端消息缺口 70 → 57，
双语总缺口 82 → 69（`tests/test_bilingual_coverage.py` 基线）。
新增 `tests/test_messages_bilingual.py` 9/9。

### 后端消息双语：62 处完成转换（缺口 70 → 4）

在 `backend/messages.py` 新增 49 条词条（账户、智能体授权、场景/规则/实例校验、预演、
管理器），并替换 48 处调用点为 `messages.detail(键)`，由异常处理器按请求语言解析。

**验收**（直接打后端接口 + 目录取值）：

```
POST /v1/login  X-Display-Language: en → {"detail":"Enter the login password."}
scene_missing           : zh=场景草稿不存在。 / en=Scenario draft not found.
confirm_before_compile  : zh=请先确认并保存该场景… / en=Confirm and save the scenario…
```

双语总缺口 **69 → 16**（后端消息 57→4；余 4 处为插值列表与长句）。
回归：api_auth 42/42、agent_access 24/24、label_localization 6/6、
messages_bilingual 9/9、both_tier 4/4、multi_resource 6/6、policy_actions 7/7。

### 后端消息双语层完成（70 → 0）

转换最后 4 处特殊结构：分组场景启用限制（长句含内嵌引号）、规则归属校验（尾部拼接列表）、
规则启用入口提示（长句含内嵌引号）、管理器重启结果（三元赋值，且需给端点补 `request` 参数）。

**后端消息层归零**，双语总缺口 **16 → 12**；余下 12 全部是文档（设计文档 10 + README 1 + CHANGELOG 1）。

**验收**：
```
POST /v1/login  X-Display-Language: zh → {"detail":"请输入登录密码。"}
POST /v1/login  X-Display-Language: en → {"detail":"Enter the login password."}
后端消息（含中文的 detail/message）: 0 处
manager HTTP 200 · backend health ok
```
回归：api_auth 42/42、agent_access 24/24、messages_bilingual 9/9、
label_localization 6/6、ui_consistency 5/5、mcp_e2e 17/17。

### README 英文版（README.en.md）+ 中文版自检清单同步

- 新增 `README.en.md`：与中文版**同结构同内容**的完整英文版（安装、双端口分工与理由、
  首启口令与加密容器、服务监控、智能体接入与 MCP、场景偏好与分组、备份与跨机、API、
  安全边界、文档与测试索引）。
- 中文 `README.md`：自检清单同步为**当前实际测试集**（11 → 17 个），文档索引补上
  `docs/00-first-principle-bilingual.md`，并在顶部指引 `README.en.md`。

双语总缺口 **12 → 11**；余 10 份设计文档 + CHANGELOG。

### 设计文档双语：docs/07 英文版

新增 `docs/07-local-agent-access.en.md`（6.5 KB）：与中文版同结构的完整英文版——
问题定义、硬限制（同 uid 恶意程序无法用纯软件区分）、T1–T4 四项措施与实现要点、
诚实说明"这不是硬边界"、跨机接入默认关闭、自检、以及 T5 规划（目标、设计草图、
取舍表、开工前待定三项）。

双语总缺口 **11 → 10**；余 9 份设计文档 + CHANGELOG。
命名约定：中文为 `docs/NN-name.md`，英文为同目录 `docs/NN-name.en.md`（现有文件无需改名）。

### 设计文档双语：docs/06 英文版

新增 `docs/06-remote-agent.en.md`（6.9 KB）：跨机使用方案 A 的完整英文版——为何需要专门处理
（stdio MCP 无法跨机 + 回环监听是有意的）、拓扑图、Mac 侧/远端侧/隧道/客户端配置四步、
环境变量、行为与限制表（锁定、隧道未建、Python 版本、重新解锁、空闲锁定）、
"这不是无人值守方案"的说明与安全要点。

双语总缺口 **10 → 9**；余 8 份设计文档 + CHANGELOG。

### 设计文档双语：docs/09 英文版 + 盘点器新增指标

- 新增 `docs/09-scenario-analysis-schema.en.md`（8.8 KB）：分析契约的完整英文版——顶层字段、
  **字段三档**、策略（含 `actions` 必填与禁止无条件 deny）、偏好适用范围、`generated`、
  向后兼容表、五类模型陷阱、可执行契约（JSON Schema + `validate_analysis`）。
- **写文档时发现一处新债**：`contract_notes[].message` 会显示给用户（切片页"N 处契约提醒"），
  但只有中文，约 13 条，此前不在任何盘点范围内。已在 `test_bilingual_coverage.py` 中
  **新增该指标**并计入总缺口（诚实标注为"新计入的债"，非回退）。

双语总缺口：设计文档 9 → 7（docs/06、07、09 完成）；计入新指标后总数为 **21**
（设计文档 7 + CHANGELOG 1 + 契约提醒消息 13）。

### 契约提醒消息双语化（用户可见，13 → 0）

`backend/analysis_contract.py` 的 `contract_notes[].message` 会显示在切片页的
「N 处契约提醒」徽章里，此前只有中文。改法与后端消息同构：

- `note(code, field, level, **params)` 只携带**消息键（键即 code）+ 参数**；
  中文/英文文本移入 `backend/messages.py`（新增 13 条）；
- 创建时写入中文 `message`（兼容未本地化的读取路径），
  `_localize_scene_labels()` 读取时按显示语言替换 `message`；
- 实测英文渲染含参数正确：`policy_unknown_action` → "A policy declares actions that are not in this scenario: 删除文件."

**双语总缺口 21 → 9**（设计文档 7 + CHANGELOG 1）。回归：analysis_contract 10/10、
api_auth 42/42、messages_bilingual 9/9、both_tier 4/4。

### CHANGELOG 英文版（覆盖本轮起）

新增 `CHANGELOG.en.md`：以英文记录 **2026-10-02（确立双语原则）起**的全部变更——双语原则的确立、
后端消息双语化（70→0）、语言优先级缺陷的修复、契约提醒消息双语化（13→0）、文档双语进展，
以及同一会话中更早的三档字段、四个契约缺口、可执行契约、i18n 机制补全与各项修复。

**范围声明写在文件开头**：历史条目仅存在于中文 `CHANGELOG.md`，并非遗漏——为过程记录逐条翻译
被判定为性价比最低的工作，中文版仍是完整记录；**自本轮起中英两版同步维护**。

双语总缺口 **9 → 8**（余设计文档 7 + i18n 清单 1）。

### 双语：豁免工具清单 + 第一性原则文档英文版

- **豁免工具产出的清单**：`docs/i18n-pending.md` 是扫描产物、服务于维护者，中英各一份反而失去
  意义。已在 `test_bilingual_coverage.py` 加入 `EXEMPT_DOCS`，并在原则文档补上例外第 4 条。
- **新增 `docs/00-first-principle-bilingual.en.md`**：第一性原则文档自身的英文版——分层要求表、
  四条例外、**六条实施纪律**（本轮新增第 5、6 条：先查语言解析链、按整行报告中文残留）、
  现状表、当前缺口、以及"契约提醒消息"这笔新计入的债及其解决。

双语总缺口 **8 → 6**（余 5 份设计文档）。

### 设计文档双语：docs/08 英文版

新增 `docs/08-ios-app-plan.en.md`（13.3 KB）：iOS 实施计划的完整英文版——三项已定决定、
Python→Swift 架构映射表（含"不移植"与"原样复用 web/"）、P0–P8 分阶段任务与验收标准、
第三方依赖（运行时 0 个）、三项已确认决定（文件 App 导出导入 / 不做合并 / 密钥随容器走）、
明确不做的事、风险表，以及**评估结论：暂不实施**（三条理由 + 替代方案）。

本轮取舍：**没有做 `docs/04`**。它是 46 项密集差距分析，以当前预算做不完全的翻译会导致
"文件存在但内容不全"却被盘点计入已覆盖——那是刷指标，不是达标。

双语总缺口 **6 → 5**（余 docs/02、03、04、05）。

### 设计文档双语：docs/02 英文版

新增 `docs/02-validation-and-runtime.en.md`（23.8 KB）：验证与运行时规范的完整英文版——
验证约定与命名空间、19 个 SHACL shape、字段名对齐说明、判定算法（请求结构、**十步决策顺序**、
输出契约）、注册中心规范（八类、接口契约、各类要求）、数据存储规范（分区、事务与修订、
隐私保留备份、迁移兼容）、一致性与错误处理表、实施边界。

**做法**：SHACL 的 Turtle 代码块（约 145 行）**原样复用**——它是语言无关的，翻译它只会引入
不一致风险；只翻译了约 120 行散文。这是此后"含代码块的文档"应遵循的做法。

双语总缺口 **5 → 4**（余 docs/03、04、05）。

### 设计文档双语：docs/05 英文版（价值最高的一份）

新增 `docs/05-secret-and-sensitive-data-design.en.md`（27.9 KB）：本体加密/登录/解锁设计的完整英文版——
为何更换骨架、威胁模型（T1–T3 覆盖与不覆盖）、架构总览、**容器格式规格**（两段结构及理由、算法表、
迭代次数实测依据、AAD 精确拼接、跨平台零依赖路径、**已冻结测试向量**）、登录/解锁/锁定三态与端点、
口令策略（8 位下限 + 三条补偿规则 + 实测爆破成本表）、改密码的事务流程与失败模式表、
凭据模型（盘上无长期凭证）、LLM 凭据入容器、零明文不变量与残留治理、迁移步骤、跨平台路线、
审计分级、界面设计、分阶段实施状态、待定项与已知残留风险。

**做法**：容器 JSON、AAD 拼接、测试向量等**机器块原样保留**；其中测试向量明文
（`测试向量：personal-ontology container v1`）是**输入字节**，翻译它会让实现产出不同密文——
因此新增**第 5 条例外**进原则文档：**冻结的测试向量与机器数据不翻译**。

双语总缺口 **4 → 3**（余 docs/03、04）。

### 设计文档双语：docs/04 英文版（仅余 docs/03）

新增 `docs/04-design-vs-implementation-gaps.en.md`（23.2 KB）：46 项差距核对的完整英文版——
历史快照横幅、核对基线与结论口径、P0 阻断级（A1–A5）、通用元模型缺失（B1–B13）、
约束与类型化值（C1–C7）、API 契约与流程（D1–D14）、校验/迁移/代码结构与前端（E1–E14）、
文档过时项（E11 的详细改判理由）、**11 项已对齐**（F1–F11，含代码行号证据）、
七步收敛顺序与只读核对声明。

双语总缺口 **3 → 2**：**仅余 `docs/03`（724 行）**。计划拆两轮（上半 + 下半），
每轮在 CHANGELOG 注明进度，避免"半份却被计为完成"。

### 设计文档双语：docs/03 Part 1（§1–§14）

新增 `docs/03-scenario-slices-design.en.md` 的**上半部分**（30.7 KB）：目标与边界、现有对象盘点与
分层处理、通用元模型（结构图 + 概念职责 + 字段定义与条件）、信息完整性与主动建议、酒店预订示例映射、
数据流与联合校验（含责任边界）、页面菜单设计、校验与安全原则、分阶段实施顺序、
类与属性契约（ScenarioDefinition / ScenarioSlice / ParamDefinition / SlotValue /
Clarification / WorkflowStep / Constraint / Authorization 生命周期）、通用 API 契约草案、
跨场景通用性检查（网购）、尚待定稿的决策、建议采用的默认决策。

**本文件带 `BILINGUAL-PARTIAL` 标记**（文件头注释说明"part 1 of 2，§15–§26 待补"）。
盘点器识别该标记并**仍把 docs/03 计为缺口**——因此本轮缺口保持 2，**没有把半份文件当作完成**。
标记机制与约定已写入原则文档（中英两版）。

### 全栈双语达标：缺口归零（docs/03 Part 2 完成）

新增 `docs/03-scenario-slices-design.en.md` 的**下半部分**（§15–§26）：RDF 类与属性命名草案、
SHACL 校验边界（8 个 shape 的结构约束 + 示意 Turtle）、现有对象兼容与迁移表（17 个类逐项）、
约束迁移风险与检查点、实施前待确认事项、**RDF 域/值域/基数草案（约 50 行）**、动态值与规范表达式、
旧约束转换表、可执行迁移六阶段、**规范字段名映射表（API↔RDF，20 行）**与状态转换表、
代码结构设计（后端模块边界、路由草案、DTO 与存储格式、前端模块、依赖顺序）、
代码设计评审清单、已实现版本（偏好范围与分组）。文件头的 `BILINGUAL-PARTIAL` 标记已移除。

**全栈双语缺口 2 → 0**，并修掉盘点器自身的两处缺陷：
1. 只在全文搜标记字符串会把"正文里解释该约定"误判为部分翻译 → 改为只认**文件头 HTML 注释**；
2. 契约提醒计数把 `note()` 的中文 **docstring** 当成用户可见文案 → 改为直接计
   `"message": "……中文……"` 这一真实形态。计数修正后暴露出**一处真实残留**：
   `not_an_object` 消息硬编码中文、绕过消息目录 —— 已改为消息键并补入目录。

**达标态语义**：基线设为 0 后，盘点器要求缺口**必须为 0**，任何新增未双语产出都会直接失败。

### 发布准备：许可证、忽略规则、门面截图与路径修复

为发布到 GitHub 做的准备（中文 README 保持默认展示）：

- **新增 `LICENSE`**：GNU GPL-3.0 官方全文（674 行）。
- **新增 `.gitignore`**：明确排除用户数据与凭据（`data/`、`*.po.json`、`*.key`、
  `session-token`、`agent-clients.json`、`settings.json`、`*.log`、`backup/`）、
  根目录明文图、Python 产物、macOS 与编辑器文件。
- **README（中英两版）**：加入**总览截图**、状态行（v3.1 · 仅 macOS · 单用户 · GPL-3.0）、
  一句话定位，并新增**许可证**章节（含 GPL-3.0 与 AGPL-3.0 的取舍说明）。
- **`docs/images/`**：新增占位图 `overview.png`（1600×900，明确标注待替换）与说明文件，
  **强调截图不得含真实主体/场景/个人信息**。
- **修复发布阻塞项**：5 个测试硬编码了本机工作区的绝对路径
  （`test_policy_actions`、`test_both_tier`、`test_temporal`、`test_hotel_fallback`、
  `test_multi_resource`）→ 统一改为 `pathlib.Path(__file__).resolve().parent.parent`，
  并为其中 4 个补上缺失的 `import pathlib`。此前其它测试已是正确写法。
- **清理个人痕迹**：`CHANGELOG.md` 中的绝对工作区路径改为中性表述。

发布前审计结论：workspace **无容器、无密钥、无令牌、无日志、无明文图、无 API Key 形态字符串**；
唯一的 `.ttl` 是元模型与 SHACL（应发布）。

### 去掉个人域名痕迹：命名空间与标识改名

发布前清除所有 `<旧域名>` 字样（代码、本体、元模型、测试、文档、脚本）。

| 项 | 旧值 | 新值 |
|---|---|---|
| RDF 命名空间 | 带个人域名的旧命名空间（已在仓库中彻底移除） | `urn:personalontology:ontology#` |
| launchd 标签 | `tech.<旧域名>.personal-ontology` / `.backend` | `personalontology.personal-ontology` / `.backend` |
| iOS UTType（文档） | `tech.<旧域名>.personal-ontology.container` | `personalontology.personal-ontology.container` |

改动 14 个文件、22 处。**改命名空间会波及已存数据**：容器里的每条三元组都带旧命名空间，
只改代码会让界面看起来"本体空了"。因此新增：

- **`scripts/rename-namespace.py`**：把加密容器里的 RDF 命名空间整体改名。
  **旧命名空间不写死**，运行时从容器内容（`@prefix po: <…>`）自动识别，仓库里因此不留旧域名痕迹。
  只重写 `ontology` 段，`model_service` 段字节原样保留；写后重新解密核对
  （三元组数量一致、旧命名空间已消失、`model_service` 未变）；可重复执行。
  已在**合成容器**上端到端演练：干跑 / 迁移 / 复读核对 / 幂等重跑 全部通过。

**部署顺序（不可调换）**：停服 → 跑迁移脚本 → 同步新代码到已安装目录 → 重装 LaunchAgent
（卸载旧标签）→ 启动 → 验证。迁移需要容器口令，因此由用户执行。

回归：vault 37/37、api_auth 42/42、policy_actions 7/7、both_tier 4/4、analysis_contract 10/10 等全绿。

### 修复 install.sh 缺项：README 记录的命令原本跑不通

`install.sh` 只复制 `backend/ ontology/ web/ assets/ requirements.txt README.md`，
**漏了 `tests/ scripts/ schemas/ docs/`**。而 README 里明确写着
`~/personal-ontology/.venv/bin/python tests/...` 与 `scripts/verify-deploy.sh`——
按文档操作的全新安装会**找不到这些文件**。

已补齐：安装时一并创建并复制 `tests/ scripts/ schemas/ docs/`，以及
`README.en.md / CHANGELOG.md / CHANGELOG.en.md / LICENSE / install.sh`。
并在已安装目录就地补齐，验证 README 记录的命令确实可执行
（bilingual_coverage / api_auth 42/42 / vault 37/37 / i18n_rules 8/8 / ui_consistency 5/5 / temporal 50/50）。

### 修正英文截图中的两处中文残留

`docs/images/overview-en.png` 里有两处中文（`最近 10/02 22:48` 与
`已发布 · 智能体可读取 · 规则 4 条 · 更新于 …`）。这两串的翻译规则**此前是错的**：
规则写的是 `N 条规则`，而产品实际渲染的是 `规则 N 条`——**词序不同**，规则永不匹配。

规则已修正并验证（含 `规则 1 条 → 1 rule` 单数处理），因此截图按**产品修正后的真实英文渲染**
重绘了这两处（字号由源中文像素高度反推并在三处统一，文字色与背景色取样自原图），
其余像素未动。场景名「处理文件/预订机票」属用户数据，按例外保留中文。

**教训**：静态扫描源码无法发现这类缺口（拼接顺序在运行时才成型），
**渲染后的截图是有效的端到端验证手段**。

### 部署与测试

- 已同步 `backend/{api,store,model}.py` 与 `web/app.js` 到 `~/personal-ontology`，并
  `launchctl kickstart -k` 重启后端；8765/8766 健康检查通过，新端点返回真实场景规则。
- 重启后数据图复核：16 约束 / 11 动作 / 7 参数 / 5 资源类型 / 4 授权（全部仍为 `draft`）/
  2 场景 / 1 主体，与改动前一致，无 `decisions` 记录产生。
- 真实数据回归：`PATCH` 改状态被 409 拒绝且未改动数据；副本上完整走了
  启用 → 判定 → 暂停 → 判定 的全过程。

---

## 待办（按优先级，详见 `docs/04-design-vs-implementation-gaps.md` 第 7 节）

1. **A3** 图级事务：`confirm` / `delete` 目前分步写入，失败留半成品（下一个阻断项）。
2. **A5** 偏好被编译成硬约束：本机 `quiet_environment` / `non_smoking_room` / `parking_required`
   等偏好现在都是硬条件，判定会因缺字段直接不匹配；需要引入 preference/hard 区分。
3. 元模型主干：`ScenarioDefinition` / `SlotValue` / `Clarification` / `WorkflowStep` 四个类与集合。
4. UI：场景切片页的"采用/修改/跳过/不适用"、来源分组展示、确认与启用分开的二次说明。
