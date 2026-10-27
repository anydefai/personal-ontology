# 圈与资料项：字段设计与迁移方案（v0.1 草案）

> 目的：把"个人本体"的范围从"场景与规则"扩到"人的第一性事物"，并修掉两处结构缺陷。
> 本文只谈模型与迁移，不谈界面细节。中文先行，英文版在方案确认后同步（避免翻译一版还要改的稿）。

## 零、为了什么

- 让授权可以从"某个人"升级到"**某一圈**"；
- 让资料可以从"一整块"拆到"**逐项**"，从而能逐项授权、逐项留痕；
- 把现在散落在明文文件里的东西（智能体清单）收进本体；
- 其余几类（事、地、财、痕迹）先建模，不急于做界面。

## 一、通用约定

所有新集合共用这些字段（与现有集合一致）：

| 字段 | 说明 |
|---|---|
| `display_name_zh` / `display_name_en` | 名称（双语是项目硬规矩） |
| `note` | 备注 |
| `source` | 来源：`manual` / `contacts_sync` / `import` / `agent` |
| `sensitivity` | `normal` / `sensitive` / `restricted` |
| `created_at` / `updated_at` | 时间（服务端兜底，缺了自动补） |

主键走 `ID_FIELDS` 约定，集合名 → 类名走 `CLASSES`，字段 → 谓词走 `FIELDS`。

## 二、九个新集合

### 1. `circles` —— 圈

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `circle_id` | string | ✓ | 主键 |
| `display_name_zh` | string | ✓ | 家人 / 朋友 / 同事 / 客户 / 同学 / 邻里 |
| `circle_type` | enum | ✓ | `family` `friend` `work` `class` `service` `org` `other` |
| `my_role` | string |  | **我在这一圈里的身份**：父亲 / 下属 / 甲方 / 病人 |
| `sensitivity` | enum |  | 整圈默认敏感级，默认 `sensitive` |
| `default_grant_note` | string |  | 这一圈默认能被授权什么（一句话，不做成规则） |

### 2. `circle-members` —— 圈成员

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `member_id` | string | ✓ | 主键 |
| `circle_id` | 引用→`circles` | ✓ | 属于哪一圈 |
| `principal_id` | 引用→`principals` |  | 若这人已在主体里 |
| `contact_ref` | 引用→`contacts` |  | 若只有联系方式 |
| `display_name_zh` | string | ✓ | 冗余存一份，便于列表展示（避免跨集合查） |
| `member_role` | string |  | 这人在这圈里的身份：同事 / 客户 / 医生 |
| `strength` | enum |  | `close` `normal` `distant` |
| `last_interaction_at` | 时间 |  | 用于"冷关系"提示 |
| `source` | enum |  | `contacts_sync` `manual` |

**规则**：只存"关系"，不存对方的资料（他的证件、住址、家庭一律不进本体）。

### 3. `profile-items` —— 资料项（拆自 profiles.items）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `item_id` | string | ✓ | 主键 |
| `profile_id` | 引用→`profiles` | ✓ | 属于哪份资料 |
| `field_key` | string | ✓ | 英文码：`name` `id_no` `phone` `address` |
| `label_zh` | string | ✓ | 给人看的名称：身份证号 |
| `value` | string |  | 值（容器整体加密；不放日志、不回声） |
| `kind` | enum |  | `text` `phone` `id` `date` `bool` |
| `sensitivity` | enum |  | `normal` `sensitive` `critical`（证件号默认 critical） |
| `verified` | bool |  | 是否已验证 |
| `verified_at` | 时间 |  | 验证时间 |
| `last_used_at` | 时间 |  | 最近一次被场景使用 |

### 4. `commitments` —— 事（约定、截止、合同、保修）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `commitment_id` | string | ✓ | 主键 |
| `title` | string | ✓ | 例如"车险续保""和张律师的会面" |
| `kind` | enum | ✓ | `appointment` `deadline` `contract` `warranty` `renewal` `promise` |
| `counterparty_kind` | enum |  | `principal` `circle` `external` |
| `counterparty_ref` | string |  | 对方 ID 或名称 |
| `start_at` / `due_at` | 时间 |  | 开始 / 到期 |
| `status` | enum |  | `pending` `done` `expired` `cancelled` |
| `remind_before_days` | number |  | 到期前几天提醒 |
| `sensitivity` | enum |  | 默认 `normal` |

### 5. `places` —— 地

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `place_id` | string | ✓ | 主键 |
| `label_zh` | string | ✓ | 家 / 公司 / 父母家 |
| `kind` | enum | ✓ | `home` `work` `family` `frequent` `travel` |
| `address_text` | string |  | 地址（建议只到街道级；精确坐标单独开关） |
| `geo` | json |  | `{lat,lng}`，默认不采集 |
| `radius_m` | number |  | 到达/离开判定的半径 |
| `sensitivity` | enum |  | 默认 `sensitive` |

### 6. `assets` —— 财

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `asset_id` | string | ✓ | 主键 |
| `label_zh` | string | ✓ | 工资卡 / 车 / 重疾险 / 会员 |
| `kind` | enum | ✓ | `account` `property` `vehicle` `insurance` `subscription` `debt` `tax` |
| `identifier_masked` | string |  | **只存掩码**：`**** 1234`，不存完整卡号 |
| `value_summary` | string |  | 一句话摘要（余额/保额）；明细见 `asset-transactions` |
| `expires_at` | 时间 |  | 保险/订阅到期 |
| `custodian` | string |  | 机构/银行/平台 |
| `sensitivity` |  |  | 默认 `restricted` |

### 7. `devices` —— 器（设备与智能体）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `device_id` | string | ✓ | 主键 |
| `label_zh` | string | ✓ | 我的 iPhone / 家里的 Mac / 车机 |
| `kind` | enum | ✓ | `phone` `computer` `tablet` `vehicle` `home` `wearable` `agent` |
| `agent_client_id` | string |  | 若是智能体：对应现在的 `agent-clients.json` 里的 client |
| `trust_level` | enum |  | `trusted` `limited` `blocked` |
| `last_seen_at` | 时间 |  | 最近活动 |
| `capabilities` | json |  | 能做什么（可留空） |

### 8. `reputation` —— 痕迹

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `item_id` | string | ✓ | 主键 |
| `kind` | enum | ✓ | `profile_public` `publication` `citation` `review` `credential` |
| `title` | string | ✓ | 标题 |
| `venue` | string |  | 平台/刊物/颁发机构 |
| `at` | 时间 |  | 时间 |
| `url` | string |  | 链接（可选） |
| `visibility` | enum |  | `public` `private` |

### 9. `asset-transactions` —— 流水（按决定：存）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `transaction_id` | string | ✓ | 主键 |
| `asset_id` | 引用→`assets` | ✓ | 属于哪个账户/资产 |
| `occurred_at` | 时间 | ✓ | 交易时间 |
| `amount` | number | ✓ | 金额（负数为支出） |
| `direction` | enum |  | `in` / `out` |
| `counterparty` | string |  | 对方名称（商户/个人） |
| `category` | string |  | 分类（餐饮/交通/保费…） |
| `summary` | string |  | 摘要原文（银行给的描述） |
| `balance_after` | number |  | 交易后余额（可选） |
| `source` | enum |  | `statement_import` / `manual` |
| `sensitivity` | enum |  | 默认 `restricted`，**不参与任何对外授权** |

**边界**：流水属于"最不该出本机"的数据之一。默认不进 MCP、不进契约、不进任何一眼可见的界面；要看必须单次确认。

## 三、对现有集合的三处扩展

| 扩展 | 说明 | 兼容性 |
|---|---|---|
| `authorizations.grantee_kind` | `principal`（默认）/ `circle` | 旧数据不写即视为 `principal`，读取时兜底 |
| `contacts.owner_profile` | 这条联系方式属于哪份资料 | 可空 |
| `principals` 不新增冗余字段 | 主体属于哪些圈，靠 `circle-members` 反查 | 避免双写不一致 |

### 通讯录导入（按决定：**带备注**）

导入字段：姓名、电话、公司/组织、**备注**、分组（若有）。

**备注的处理（重要）**：
- 备注是很多人写隐私的地方（"这人离过婚""欠我钱""身份证 3301…"），一旦入库，就把**第三方隐私**带进了本体；
- 这与前面定的"只存关系，不存对方资料"直接冲突，属于**例外**，必须显式记账：
  - 备注一律 `sensitivity = restricted`；
  - 备注**不参与任何授权**（不进契约、不进 MCP 返回、不进预填候选）；
  - 导出功能默认**排除**备注；
  - 界面上逐条显示、逐条可删，支持"整批不导入备注"的总开关（默认开，可关）。

## 四、关系图

```
profiles ──┬── profile-items ──┬── contacts（owner_profile）
           │                   └── 被 prefills 引用（场景"每次预填"取哪一项）
           └── principal_id → principals

circles ──── circle-members ──┬── principals（principal_id）
                              └── contacts（contact_ref）

authorizations ── grantor → principals
               └─ grantee → principals  或  circles（grantee_kind）

commitments ── counterparty → circles / principals
             └─ 到期触发 → scenario-slices（预演/提醒）

devices ── agent_client_id → 现有 agent-clients（迁移后进本体）
        └─ 授权状态 → authorizations

scenario-slices ── prefills → profile-items（每次预填，需用户确认）
                └─ authorizations → 圈级授权
```

## 五、迁移方案 A：把 `profiles.items` 拆成 `profile-items`

**目标**：一份资料仍是"容器"，但每一项成为独立节点，能逐项授权、逐项留痕。

### 步骤

1. **建模**：加 `profile-items`（CLASSES / FIELDS / ID_FIELDS）+ 一般形状（必填 `profile_id`、`field_key`、`label_zh`）。
2. **迁移脚本**（一次性、幂等）：
   - 遍历 `profiles`，对 `items[]` 每一项：
     - `item_id = pi_<profile_id 后缀>_<field_key 或序号>`（冲突加 `-2`）
     - 写入 `profile-items`：`profile_id`、`field_key`（无英文码时按名称映射，映射不到用 `field_<n>`）、`label_zh`、`value`、`kind`、`verified`
   - `profiles.items` **不清空**，原样保留（双写期内兼容）
3. **读取改造**：
   - 资料页与预填选择器改读 `profile-items`；
   - 兼容：若某份资料没有 items 节点，回退读旧 `items` 数组（只读）。
4. **写入改造**：保存资料时写 `profile-items`（新增/更新/删除），**不再**写 `items` 数组；旧数组置空但保留键。
5. **验收**：
   - 每份资料的项数与迁移前一致；
   - 预填选择器能列出每一项，且能按项勾选；
   - 使用记录能定位到具体 `item_id`。

### 风险与回滚

| 风险 | 处理 |
|---|---|
| 同名项冲突 | 生成 id 时加后缀；`field_key` 允许重复但 `item_id` 唯一 |
| 双源不一致 | 以 `profile-items` 为准；旧数组只读 |
| 回滚 | 删除 `profile-items` 集合即可，旧 `items` 未动，功能退回旧行为 |

## 六、迁移方案 B：加 `circles` 与"按圈授权"

### 步骤

1. **建模**：`circles`、`circle-members`；`authorizations` 加 `grantee_kind`（默认 `principal`）。
2. **初始化圈**（三选一，可叠加）：
   - 从 `principals` 中 `principal_type in (group, org, role)` 生成候选圈，**由你确认后**建圈；
   - 从通讯录导入（iOS 通讯录授权，只读姓名/电话/公司/备注）；
   - 手工新建。
3. **判定引擎改造**：查授权时，规则命中条件从"grantee 是调用主体"改为"grantee 是调用主体 **或** 是调用主体所属的圈"。
4. **圈成员变更的审计**：成员增删时写一条变更记录，并提示"该变更影响 N 条授权"。
5. **验收**：
   - 建一条"给工作圈看空闲时间"的规则，用工作圈内主体调用 → 通过；
   - 用非工作圈主体调用 → 拒绝，且拒绝原因写明"因圈规则"；
   - 从圈里移除该主体后再调用 → 拒绝。

### 风险与回滚

| 风险 | 处理 |
|---|---|
| 圈成员变动导致既有授权静默扩大 | 变更写审计 + 影响面提示；拒绝理由必须可读 |
| 旧数据缺 `grantee_kind` | 读时兜底为 `principal`，不需要批量改写 |
| 回滚 | 删除 `circles` / `circle-members` 即可；授权规则退回"只认个体" |

## 七、顺带修掉的缺口：把智能体清单收进本体

`data/agent-clients.json` 现在是**明文**（智能体 ID、授权范围）。它属于"器"，应该在加密容器里：

1. 建 `devices`（`kind=agent`，`agent_client_id` 对应现有 client）；
2. 迁移：读 `agent-clients.json`，逐条写成 `devices` 节点；
3. 判定与 MCP 读取改为读本体；明文文件降级为"仅启动引导"或删除；
4. 验收：智能体列表在界面可见、授权状态可查、明文文件删除后功能正常。

## 八、落地顺序与成本

| 顺序 | 改动 | 影响文件 | 粗估 |
|---|---|---|---|
| ① | `profile-items` 建模 + 迁移 + 读取改造 | `model.py`、`api.py`、`app.js` | 1 天 |
| ② | `circles` + `circle-members` + `grantee_kind` + 判定改造 | `model.py`、`api.py`、`authorization.py`、`app.js` | 2 天 |
| ③ | `devices` 收编智能体清单 | `model.py`、`api.py`、`agent_access.py` | 0.5 天 |
| ④ | `commitments` / `places`（含到期提醒） | 同上 + 定时任务 | 1.5 天 |
| ⑤ | `assets` + `asset-transactions` / `reputation` | 同上 + 独立持久化段（见 §十一） | 1 天 + 1 天 |

每个集合的"建模"部分都是约 30 行（CLASSES + FIELDS + ID_FIELDS），若要强制约束再加约 10 行形状。

## 九、已定的五条（2026-10 拍板）

| # | 问题 | 决定 |
|---|---|---|
| 1 | 一个主体能否同时在多圈 | **能**（`circle-members` 天然多对多） |
| 2 | 圈是否继承 | **不继承**，避免推理复杂化 |
| 3 | 证件类资料项默认敏感级 | **`critical`** |
| 4 | 通讯录是否导入备注 | **导入**（例外处理见 §三 末尾） |
| 5 | 财务是否存流水 | **存流水**（`asset-transactions`，见 §二.9） |

仍未定（不阻塞开发）：
- 流水保留期限（永久 / 按年归档 / 只留 5 年）；
- 通讯录备注是否参与"关系强度"推断（建议：不参与，避免用隐私做推断）。

## 十、验收清单（要新增的测试）

- `test_profile_items_migration`：迁移前后项数一致、值一致、可逐项读取；
- `test_circle_grants`：圈内主体通过、圈外主体拒绝、移出后拒绝；
- `test_devices_import`：明文文件删除后，智能体清单仍可从本体读出；
- 既有 8 套测试不得回归（模型改动会牵动 SHACL，务必先跑形状校验）。

## 十一、这两个决定的代价（必须记账）

### 代价一：备注入库 = 第三方隐私入库

- 原来的规则是"只存关系，不存对方资料"，导入备注破了这条；
- 现实风险：备注里常有他人的健康、婚姻、债务、证件号，一旦入库，本体就从"我的数据"变成"我收集的他人数据"；
- 缓解（已在 §三 落地）：`restricted` + 不参与授权 + 导出排除 + 逐条可删 + 总开关；
- **要在界面上写明**：备注属于例外，默认只在本机可见。

### 代价二：存流水 = 体量与校验成本

- 估个量：一人一年 1–3 千条流水，十年 1–3 万条；
- 现在的写入路径是"整图在内存 + 每次写入全量跑 SHACL"，节点到万级后写入会明显变慢，且每次保存都要重加密整个容器；
- **应对（推荐方案 A）**：利用容器已有的"分段"能力，把流水放进**独立的第三段**（`ledger`）：
  - 写流水只重写 `ledger` 段，不触碰 `ontology` 段；
  - 本体对 `ledger` 只存引用（`asset_id` + 年度汇总），不把流水混进主图；
  - 成本：`vault.py` 已支持多段（`ontology` / `model_service`），需要 `store` 支持"第二个图 + 独立持久化"，约 1 天；
- 备选方案 B：按年拆集合（`asset-transactions-2026`）——破坏"集合名固定"的假设，不推荐；
- 备选方案 C：只存汇总、明细留在银行导出文件——与你"存流水"的决定冲突，仅在体积失控时回退。


---

## 12. 圈与智能体的联动（2026-10 落地，实现为准）

这一节记录实现时定下的三件事。前几节是设计，这一节是**已经跑通的**。

### 12.1 圈成员可以是主体，不只是名字

`circle-members` 增加 `member_kind`（`person` / `agent` / `service`）与 `principal_id`（可选）。

- 只填名字 → 这是一条"关系占位"，等以后有主体再挂上；
- 选了已有主体 → 记 `principal_id` + `member_kind`，这时判定引擎才能真正认出"它在这个圈里"。

界面上：圈的"加成员"表单有"从已有主体里选（人 / 智能体 / 服务）"，选中后自动带出姓名与类型。

**为什么必须要 `principal_id`**：判定看的是主体 ID，不是名字。只记名字的成员，对授权没有任何作用。

### 12.2 代理关系 `acts_for`

智能体可以声明"我代表某人办事"。字段落在主体上：`principals.acts_for` → 被代表的主体 ID。

判定时（`store.evaluate`）：

1. 用调用者自身的上级链与所属圈；
2. **若调用者是智能体且设了 `acts_for`**，把被代表者的上级链与所属圈**也并入** ancestry；
3. 之后的规则匹配完全不变 —— 老规则、老数据不受影响。

接口：`POST /v1/principals/{id}/acts-for`，`{"represents": "<person_id>"}`；传空串即取消。只能代理到 `person` / `role`，不能代理到另一个智能体（避免代理链套娃）。

界面：器页「代理关系」每个智能体一个"代表谁"下拉，改完立刻生效。

### 12.3 判定结果要能解释"凭什么"

`evaluate` 的返回里新增 `reason_params`：

| 字段 | 含义 |
|---|---|
| `matched_via` | `self`（本人）/ `ancestor`（上级主体）/ `circle`（所属圈）/ `acting_for`（代理） |
| `matched_rule` | 命中的规则 id |
| `via_circle` | 若靠圈命中，是哪个圈 |
| `acting_for` | 若靠代理命中，代表谁 |

这样一件授权到底"因为什么"生效，可以原样交给用户与智能体阅读，而不是只说"允许/拒绝"。

### 12.4 验收（已通过）

```
✓ 智能体作为成员进圈 → 给圈授权 → 放行；圈外智能体 → 拒绝
✓ 智能体设 acts_for → 继承被代表者的圈与个人授权
✓ 直接给"人"的授权 → 经代理命中，matched_via = acting_for
✓ 取消代理 / 移出圈 → 立刻失效
```

### 12.5 还未做的

- 判定历史里没有单独一页列出"授权判定"（现有「判定记录」只记正式交付）；
- `matched_via` 还没翻成中文显示在界面上，只存在于接口返回里；
- 代理关系还没做"有效期"（现在是长期有效，取消即失效）。
