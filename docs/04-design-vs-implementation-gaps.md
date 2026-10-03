# 差距清单：`docs/03` 场景切片设计 vs 当前实现

> **历史快照（说明）** —— 本文是当时某一时点的差距核对结果，其中的状态标记已不反映现状。
> 特别是：涉及"资源类型 / 动作 / 授权规则目录页"的条目**均已作废**（那三个页面已移除，
> 见 `docs/03` 文首现状更正）。2026-10-02 迭代查出的四个契约缺口（策略缺动作维度、
> 无条件 deny、跨领域扩张、多资源类型丢失）**已全部修复**，当前契约与容错规则以
> `docs/09-scenario-analysis-schema.md` 为准。保留本文仅供追溯当时的判断依据。

# 差距清单：`docs/03` 场景切片设计 vs 当前实现

核对对象与基线：

| 项 | 内容 |
|---|---|
| 设计基线 | `docs/03-scenario-slices-design.md`（709 行；自述"设计稿，尚未进入实现"，仅 §26 标注为已实现） |
| 实现基线 | 工作区 `backend/`（7 个模块）、`web/`（3 个文件）、`ontology/`（2 个文件），未纳入版本控制 |
| 核对方式 | 逐节提取可检验要求 → 静态核对代码 + 对运行中的本机服务与实际 RDF 图做只读实测 |
| 设计基线时效性 | `docs/03` §7 主张"保留资源类型／动作／授权规则页面"，**该主张已被最新（v3.1）设计取消**：`README.md` 与 `web/index.html` 的菜单均无这三项。UI 类要求以 v3.1 实际设计为准，§7 过时部分单列于第 5.1 节 |
| 判定图例 | ✅ 已对齐 ／ ⚠️ 部分实现或形式不同 ／ ❌ 未实现（含 2 项实测缺陷） |

**结论口径**：共核对 46 项可检验要求 —— ❌ 32 项、⚠️ 14 项；另有 11 项已对齐（见第 6 节）、1 项判定为文档过时而非实现差距（见第 5.1 节）。`docs/03` 的完整通用元模型（ScenarioDefinition / SlotValue / Clarification / WorkflowStep + 规范约束执行器 + 迁移）**基本未落地**；真正实现的是 §26 那条"场景切片 + 偏好分组"竖切，外加 `policyStatus`、场景预演与 MCP 反馈。

---

## 1. P0：阻断级（正确性与安全）

| # | 问题 | 现状与证据 | 判定 |
|---|---|---|---|
| **A1** | **场景生成的约束在 RDF 中序列化损坏，规则永不匹配** | `api.py:308`、`447-450` 把 `constraint_value` 写成 dict；`model.py:83` 走 `lit` 分支（非 `json` 分支），`Literal(dict, datatype=RDF.JSON)` 落盘为 Python repr 单引号文本。实测本机图：`ns1:constraintValue "{'key': 'check_in_date'}"^^rdf:JSON`，`toPython()` 返回 `Literal` 而非 dict；`store.py:292` 的 `json.loads` 对单引号必然失败 → `_constraints_match` 返回 `False`。实测对照：图内字符串形式 `matches=False`，同样内容的 dict 形式 `matches=True`。**后果：即使把这 4 条 draft 授权手工改为 active，其条件也永不成立，判定永远落到 `default_deny`。** | ❌ |
| **A2** | **场景实例编辑保存必然 500（`NameError`）** | `api.py:416` 在 `api.py:417` 之前就引用 `suffix`（生成器在 `list(...)` 内立即求值）。实测（stub store，未触碰真实数据）：`NameError: cannot access free variable 'suffix'`。只要已确认场景的资源带有参数（本机 2 个场景均如此），`PATCH /v1/scenario-slices/{id}/instance` 与依赖它的 `/feedback`（`instance_preference` 模式）都会失败。 | ❌ |
| **A3** | **无图级事务：确认与删除都是分步写入** | `confirm` 对资源、动作、参数、约束、授权逐个调用 `store.put`（`api.py:241-315`），每次 put 独立完成"复制全图→校验→落盘"，中途失败不回滚已写入的对象；`delete_scenario_instance` 逐个删除并吞掉 `StoreError`（`api.py:325-344`）。§24.1/§24.2/§25 明确要求"批量写入在单一图事务中验证并落盘；失败不留下部分主体/资源/动作/规则"。 | ❌ |
| **A4** | **没有独立"启用授权"确认点，通用 PATCH 可绕过守卫，且界面上无处启用** | 设计的三确认点（确认参数／保存草稿／启用规则，§8、§14 第 5 条）缺第三个：无 `/{id}/activate`；启用只能改 `policy_status` 字段，而通用 `PATCH /v1/authorizations/{id}`（`api.py:677-691`）不校验完整性、不写审计、不检查场景状态。§24.2 要求"不能通过 PATCH 绕过场景状态守卫或策略启用守卫"。**后果**：唯一能改 `policy_status` 的控件位于已取消导航入口的授权规则表单（见 5.1）；场景切片页只显示"仅草稿，尚未生效"徽标，场景实例编辑页无启用控件 → 当前界面**无法启用任何场景生成的规则**。 | ❌ |
| **A5** | **偏好被编译成硬约束，与"偏好不得提升为硬性限制"冲突** | `api.py:388-398` 把 `instance_preferences` 无条件转成 conditions，`444-451` 再写成 Constraint；判定侧 `_constraints_match` 对每条约束都按"不满足即不匹配"处理，`strength` 只在 analysis JSON 与预演里使用（`api.py:623`）。§3.3/§8 要求 preference 只用于排序或提示。 | ❌ |

---

## 2. P1：通用元模型缺失（§3、§10、§15、§19）

| # | 设计要求 | 现状与证据 | 判定 |
|---|---|---|---|
| **B1** | `ScenarioDefinition` 类与集合同步落地 | `CLASSES` 中无该类（`model.py:11-21`，仍是"21 类 + scenario-slices"，与 §2 盘点一致）；无 `scenario-definitions` 集合。场景定义能力被压缩进单条切片记录里的 `analysis` JSON。 | ❌ |
| **B2** | `ScenarioSlice` 属性集 | 仅 `scenarioId/originalText/scenarioStatus/analysis/updatedAt`（`model.py:45`）；缺 `usesScenarioDefinition`、`ownerPrincipal`、`normalizedGoal`、`hasSlotValue`、`hasClarification`、`hasInteraction`、`hasAuthorization`、`revision`、`createdAt`。`revision` 仅以 `analysis.instance_revision` 形式存在。 | ⚠️ |
| **B3** | `SlotValue` 类与六态状态机 | 无类、无集合；值直接以普通 JSON 数组存在 `analysis.segmentation.global_preferences` / `variants[].preferences`。§10.3 的 `state/provenance/confidence/source_text/confirmed_by` 全部缺失。 | ❌ |
| **B4** | `Clarification` 类 | 无类、无集合。追问是模型输出的 `questions` 数组（`scenario_llm.py:157`），回答经 `analyze` 的 `answers` 参数回灌（`api.py:149-159`），不持久化，无 `requirement_level` / `status` / 答案槽位关联。 | ❌ |
| **B5** | `WorkflowStep` 类与 `confirmation_policy` | 完全不存在。"付款前让我确认""提交预订前展示条款"这类流程语义无任何承载。 | ❌ |
| **B6** | `ParamDefinition` 扩展属性 | 仅有 `param_name/param_type/required/display_name_*`（`model.py:26`）；缺 `scope`、`applies_to_ids`、`value_schema`、`unit`、`collection_policy`、`sensitivity`、`examples`、`validation_schema`、`display_order`（§10.3、§19、§23）。 | ❌ |
| **B7** | `Action.hasInputParam` / `hasOutputParam` | 未实现；动作与字段定义仍无输入/输出区分。 | ❌ |
| **B8** | `Constraint` 扩展属性 | 仍是 `constraintType` / `constraintValue`（`model.py:29`）；缺 `constraintPath`、`constraintOperator`、`typedValue`、`constraintUnit`、`constraintMode`、`constraintSource`（§10.4、§19）。 | ❌ |
| **B10** | 旧 Authorization 回填 `policyStatus=active` | 未做数据回填；改为代码默认值兜底 `rule.get("policy_status", "active")`（`store.py:239`），与 §17"回填兼容值"及 §25"缺状态的旧数据按迁移规则显式处理"不符（语义恰好安全，但不可审计）。 | ⚠️ |
| **B11** | 场景状态机与合法转换 | `ScenarioSliceShape` 枚举仅 `draft/analyzed/confirmed`（`shapes.ttl:149`），缺 `clarifying/ready/active/completed/abandoned`；§23.1 的转换守卫（ready 需必需信息齐备、修订回退到 clarifying 并重跑校验）无实现。 | ❌ |
| **B12** | ScenarioSlice ↔ Interaction 关联 | `analyze` 从不写 Interaction（全仓无 `put("interactions", ...)`）；§6 数据流第 1 步"创建 Interaction 并保留原文"与 §24.2"analyze 写入原始 Interaction"未落地。 | ❌ |
| **B13** | revision 递增与幂等/并发控制 | `confirm`、`/instance` 不递增 revision；无幂等键；`store.put` 无 `expected_revision`，并发覆盖不会返回 409（§11.2、§24.3）。 | ⚠️ |

---

## 3. P1：约束与类型化值（§3.3、§18、§20、§21）

| # | 设计要求 | 现状与证据 | 判定 |
|---|---|---|---|
| **C1** | 操作符白名单 `eq/neq/lt/lte/gt/gte/in/contains/between/before/after/exists` | 仅实现 `context_equals`、`numeric_lte`、`numeric_gte`、`context_exists`、`source_trust_min`（`store.py:298-316`），缺 8 个；§18 第 4 条要求"逐个确认白名单操作符已实现；未实现的类型应使规则保持不可启用"。 | ❌ |
| **C2** | 旧约束迁移映射（`context_equals`→path+`eq`，`source_trust_min`→`rank_gte` 固定等级表） | 未实现，`source_trust_min` 仍作为运行时类型直接存在（`store.py:313-315`）。 | ❌ |
| **C3** | 类型化值：金额携带 `{amount, currency, basis}`，日期/时长分离 | 值只有裸标量（`scenario_llm.py` 的 `facts`/`conditions` 仅 `value`），无币种与计价口径；§20.1 要求的 blocking 追问（"每晚还是全程"）不存在。 | ❌ |
| **C4** | `Constraint` RDF ↔ 规范表达式单一真相 | 部分改善：判定侧确实已从 URI 读回节点再解码（`store.py:244-247`），**§17.1 描述的"读内嵌字典"问题在当前代码中已不成立**；但解码结果仍是旧 `constraint_type/constraint_value` 结构，没有 `constraints.py` 与统一规范 JSON Schema 版本。 | ⚠️ |
| **C7** | 单位不兼容 / 类型不符时阻断放行 | 无单位概念，因此也无单位校验；类型不符会退化为"不匹配"（安全但静默，不生成 §16/§25 要求的复核报告）。 | ❌ |

---

## 4. P1：API 契约与流程（§4、§6、§11、§24）

| # | 设计要求 | 现状与证据 | 判定 |
|---|---|---|---|
| **D1** | `analyze` 请求 = `user_input / scenario_slice_id / principal_id / answers / locale` | 实际为 `text / scenario_id / answers / title_override`（`api.py:138-159`）；无 `principal_id`、无 `locale`。 | ⚠️ |
| **D2** | 响应分层 `recognized / inferred / suggestions / clarifications / validation / next_state` | 仅返回 `{"scenario": {...}}`，全部塞在 `analysis` JSON 里（`api.py:170`）。 | ❌ |
| **D3** | `POST /{id}/answers` | 无该端点；功能以"再次调用 `/analyze` 并携带 `answers`"替代（`api.py:149-159`）。§24.2 把创建草稿与回答追问设计为可区分操作。 | ⚠️ |
| **D4** | `POST /{id}/validate`（结构/语义/执行能力/冲突报告） | 无独立校验端点。 | ❌ |
| **D5** | `POST /{id}/confirm` | 实际路径为 `POST /v1/scenario-slices/confirm`，id 放在 body（`api.py:176-178`）。功能存在，路径与契约不同。 | ⚠️ |
| **D7** | `POST /{id}/execute` | 未实现（§24.2 允许后续版本）。 | ❌ |
| **D10** | 完整性检查的两条来源分离（模型必需项 vs 模型建议） | `questions` 带 `importance/suggested_answers`、`facts` 带 `source`（`scenario_llm.py:157`），但在接口与界面上不分组：草稿预览不区分"用户原话／模型识别／系统建议／校验问题"。 | ⚠️ |
| **D11** | 建议必须是 `suggested` 状态，采纳后才成为约束 | 无状态机，`answers` 只是自由文本回灌给模型；建议可能被模型在下一轮直接写成 preference。 | ❌ |
| **D12** | 分轮追问、控制每轮问题数量 | 未实现：只要存在 `previous` 就直接清空 `questions`（`scenario_llm.py:191-193`），即"补充一次即结束"。 | ❌ |
| **D13** | blocking 项不可跳过 | 无 `blocking/recommended/optional` 概念；预演只把 `required` 缺失报为 `incomplete`（`api.py:562`、`624-625`）。 | ❌ |
| **D14** | `owner_principal_id` 记录（未解析前不臆造身份） | 完全不记录 owner；`confirm` 只接收 `grantor_id/grantee_id`（`api.py:234-236`），主体选择发生在确认阶段而非分析阶段。 | ❌ |

---

## 5. P2：校验、迁移、代码结构与前端

| # | 设计要求 | 现状与证据 | 判定 |
|---|---|---|---|
| **E1** | 新增 4 个 Shape（ScenarioDefinition / SlotValue / Clarification / WorkflowStep） | `shapes.ttl` 无这 4 个 target class（仅 20 个 shape，含 1 个 `ScenarioSliceShape`）。 | ❌ |
| **E2** | `ScenarioSliceShape` 按 §16 约束 | 只有 5 条属性约束（`shapes.ttl:147-151`），状态枚举与 §23.1 不符，`confirmed` 不得含未解决 blocking 问句的跨对象规则不存在。 | ⚠️ |
| **E3** | `ParamDefinitionShape` / `ConstraintShape` 扩展 | 两者均未扩展（`shapes.ttl` 仍是旧字段）；`valueSchema`/`scope`/`collectionPolicy` 必填与"operator 为已注册白名单"都未写。 | ❌ |
| **E4** | `AuthorizationShape` 中 `policyStatus` 必填 | 已有 `sh:in (draft/active/suspended)` 但为 `maxCount 1` 可选（`shapes.ttl:49`），靠代码默认值；§16 要求新规则必须有。 | ⚠️ |
| **E5** | 事务级语义校验（ready 前 blocking 已答／answered 必有关联答案槽位） | 无此类校验的承载对象。 | ❌ |
| **E6** | 迁移脚本、回填、盘点报告（§17、§21、§22） | 无 `migration.py`，无任何盘点/回填/报告脚本；§22 的 6 个阶段没有任何一步落地。 | ❌ |
| **E7** | 后端拆出 `backend/scenarios/`（dto/service/analyzer/completeness/catalog/validator/compiler/constraints/migration） | 未拆分；分析编排与 RDF 编译全在 `api.py`（729 行）+ `scenario_llm.py`，§24.1 点名的 8 个模块无一存在。 | ❌ |
| **E8** | `LLMProvider` 为协议/接口，供应商无关 | 部分满足：有 `configured()` 守卫、未配置时报明确错误不伪造结果（`api.py:173-174`、`scenario_llm.py:153-154`）；但没有 Protocol/接口，绑定 OpenAI 兼容 JSON 格式。 | ⚠️ |
| **E9** | 前端拆出 `web/modules/`（含 `dynamic-form.js`） | `web/` 只有 `app.js`/`app.css`/`index.html`，无 `modules/`。注：其中 `catalog-forms.js` 随目录页一并取消，不再适用；`dynamic-form.js` 部分对场景实例编辑页仍适用。 | ❌ |
| **E10** | 元数据驱动的动态表单（金额/日期区间/重复项/未知 schema 只读） | `app.js` 有固定 `COLLECTIONS` 字段配置驱动通用表单（如 `app.js:14` 授权表单），但不按 `ParamDefinition/valueSchema` 渲染，也不支持金额（数额+币种+口径）、日期区间、重复项。注：字段类型仅 `string/number/bool/date`（`api.py:369-370`），该要求现仅由场景实例编辑页承载。 | ⚠️ |
| **E12** | 来源分组展示；建议提供"采用/修改/跳过/不适用"；确认草稿与启用规则使用不同按钮和二次说明 | 均未实现；`policy_status` 目前只是授权规则表单里的一个下拉项（该表单已无导航入口，见 5.1）。 | ❌ |
| **E13** | 页面状态由服务端 `status`+revision 驱动，刷新后可继续 | 场景草稿本身持久化（可刷新取回），但对话状态机只在浏览器内存，无 status 驱动的恢复。 | ⚠️ |
| **E14** | 隐私策略可见：远端模型发送范围、脱敏、原文保留期（§13.3、§18.3） | 有发送告知与"主体和授权数据不随请求发送"的说明（README），但无脱敏开关、无原文保留期设置。 | ⚠️ |

### 5.1 文档过时项（不计入实现差距）

| # | 原设计要求 | 核对结论 |
|---|---|---|
| **E11** | §7："一级菜单顺序：总览、主体、场景切片、**资源类型、动作、授权规则**、判定记录"；"目录编辑页面：保留资源类型、动作、授权规则页面" | **该设计要求已作废，实现与最新设计一致**。最新（v3.1）设计的菜单为：总览／主体／场景切片／场景实例／场景预演／判定记录／配置与监控（`README.md:15,30,32`；`web/index.html:20-31`）。目录数据（资源类型、动作、参数、约束、授权）不再有独立管理页，而是**由场景切片生成、在场景实例编辑页内维护**：实例编辑页直接编辑 `ParamDefinition`（"这是元模型中的 ParamDefinition"）、偏好范围与分组。侧边栏无这三项入口因此是设计结果，而非缺陷；`app.js` 中 `renderCollection`／`labels` 对这三类集合的支持属未清理的旧代码（无导航入口，无可达路径）。 |

---

## 6. 已对齐项（11 项）

| # | 设计要求 | 证据 |
|---|---|---|
| F1 | `Authorization.policyStatus` 三态，且只有 active 参与判定 | `model.py:28`、`shapes.ttl:49`、`store.py:239`（draft/suspended 永不 allow） |
| F2 | 场景生成的规则默认 draft | `api.py:310`、`scenario_llm.py:206`；本机 4 条授权实测均为 `draft` |
| F3 | 偏好范围 global/segmented 与 `segmentation_schema_version=1` | `api.py:36-76`、`231`、`377` |
| F4 | 预演按维度精确匹配、缺维度要求补充、无匹配返回 `not_applicable` | `api.py:567-584`、`626-629` |
| F5 | 预演不产生副作用、不写判定 | `api.py:543`、`636` 返回 `preview:true, side_effects:false` |
| F6 | 维度字段自动同步为运行时必填，且与偏好值分开保存 | `api.py:225-229`、`360-364`；`required_inputs` 与 `segmentation` 分列 |
| F7 | 授权无法按分组表达时转为询问并暂停 | `api.py:454-456`（`effect=ask`、`policy_status=suspended`） |
| F8 | MCP 目录返回完整 `segmentation`；反馈更新分组需 `variant_id`；原话与修订入演进日志 | `mcp_server.py:67-68`、`99-101`；`api.py:512-517`、`495`、`462-468` |
| F9 | 场景路由注册早于通用 `/{collection}` 路由 | 场景路由 138-636 行，通用路由 638 行起（`api.py`） |
| F10 | 未配置模型时返回明确错误，不生成伪造结果 | `scenario_llm.py:153-154`、`api.py:173-174`；`/v1/scenario-slices/provider` 暴露配置状态 |
| F11 | 未知操作符/未注册约束不得导致 allow | `store.py:316`（未知类型 `return False`）、`store.py:285-286`（正则 matcher 禁用） |

---

## 7. 建议的收敛顺序

按"先堵安全与正确性，再补元模型，最后做体验"排列，与 §24.5 的依赖顺序一致：

1. **A1 约束序列化** —— 修 `model.py` 写入路径或把 `constraint_value` 统一按 `json` 类型映射；补一条 API↔RDF 往返测试。否则所有场景规则都是死的。
2. **A2 实例编辑 500** —— 把 `api.py:417` 的 `suffix` 赋值提到 416 之前；补 `/instance` 与 `/feedback` 的回归测试。
3. **A3 图级事务** —— 在 `store.py` 增加"批量写入 + 整体校验 + 一次落盘"的接口，`confirm`/`delete` 改为单事务。
4. **A4 启用端点 + 启用入口** —— 新增 `POST /v1/scenario-slices/{id}/activate`（校验 + 审计），禁止通用 PATCH 直接改 `policy_status`，并在场景实例/场景切片页给出显式的"启用规则"操作（目录页取消后，此处是唯一合理落点）。
5. **C1/C2 + A5** —— 落地操作符白名单与 `hard/preference` 区分，让偏好不进入判定合并。
6. **元模型主干（B1、B3、B4、B5）** —— 按 §10 建 4 个类与集合，先把现有 `analysis` JSON 无损迁移成真实节点，再谈 §24.1 的模块拆分。
7. **契约与前端（D2-D5、E7、E9、E10、E12）** —— 最后统一 API 响应分层与前端模块化。

> 说明：本清单只做核对与分级，未修改任何实现文件。A1、A2 两项均在只读前提下实测确认（A2 使用 stub store 在临时目录运行，未触碰 `~/personal-ontology/data`）。E11 已按最新设计改判为"文档过时"，不计入差距；若 `docs/03` 仍有其他小节与 v3.1 设计冲突，需以最新设计文档为准重跑本清单。
