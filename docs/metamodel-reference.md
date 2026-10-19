# 个人本体元模型说明（自动生成）

> 生成时间：2026-10-19 14:14　｜　来源：`ontology/personal-properties.ttl`、`ontology/shapes.ttl`、`backend/model.py`
> 本文件由脚本解析上述源文件生成，改了本体或形状后重新生成即可，不要手改本文件。

## 一、这套元模型是什么

个人本体用一个**四层结构**描述「你是谁、你能怎样被调用」：

| 层 | 名称 | 含义 | 存放在哪个集合 |
|---|---|---|---|
| 一 | 领域包 | 某个领域里有哪些资源类型、动作、参数 | `domain-packs` / `resource-types` / `actions` |
| 二 | 场景定义 | 一类场景长什么样（可复用的模板） | `scenario-definitions` |
| 三 | 场景切片 | 属于你的那一条具体场景（偏好、必填、边界、规则） | `scenario-slices` |
| 四 | 判断条目 | 每次判定/执行的记录、证据、反馈 | `decisions` / `decision-results` / `evidence` / `interactions` |

**存储与校验**：整张图用 RDFLib 存在内存里，写入时转成 RDF 三元组并跑 pySHACL 形状校验，通过后整段加密写进容器（PBKDF2-HMAC-SHA256 派生密钥 + AES-256-GCM）。

## 二、类清单（共 20 个）

| 类 | 中文名 | 对应集合 | 是否被形状约束 |
|---|---|---|---|
| `po:Action` | 动作 | actions | 是 |
| `po:Authorization` | 授权规则 | authorizations | 是 |
| `po:Constraint` | 约束 | constraints | 是 |
| `po:ContactPoint` | 联系方式 | contacts | 是 |
| `po:Context` | 上下文 | contexts | 是 |
| `po:CryptoProvider` | 加密提供方 | crypto-providers | 是 |
| `po:Decision` | 判定 | decisions | 是 |
| `po:DecisionResult` | 判定结果 | decision-results | 是 |
| `po:Execution` | 执行记录 | executions | 是 |
| `po:Interaction` | 交互记录 | interactions | 是 |
| `po:Matcher` | 匹配器 | matchers | 是 |
| `po:Notifier` | 通知渠道 | notifiers | 是 |
| `po:ParamDefinition` | 参数定义 | params | 是 |
| `po:Principal` | 主体 | principals | 是 |
| `po:Redline` | 红线 | redlines | 是 |
| `po:ResourceTypeDescriptor` | 资源类型 | resource-types | 是 |
| `po:ScenarioSlice` | 场景切片 | scenario-slices | 是 |
| `po:Taxonomy` | 分类 | taxonomies | 是 |
| `po:TaxonomyItem` | 分类项 | taxonomy-items | 是 |
| `po:Trigger` | 触发器 | triggers | 是 |

## 三、形状约束（必填、类型、取值范围）

形状（SHACL）是**每次写入都会执行**的硬约束。`minCount 1` 即必填。

### po:Action（动作）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:actionId` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  |  |  |  |
| `po:displayNameEn` | 是 |  |  |  |  |
| `po:actionResourceType` | 是 |  |  | ResourceTypeDescriptor |  |
| `po:riskLevel` | 是 |  |  |  | low, medium, high, critical |

### po:Authorization（授权规则）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:authorizationId` | 是 | 1 | string |  |  |
| `po:grantor` | 是 | 1 |  | Principal |  |
| `po:grantee` | 是 | 1 |  | Principal |  |
| `po:appliesToResource` | 是 | 1 |  | ResourceTypeDescriptor |  |
| `po:resourcePattern` | 是 |  | string |  |  |
| `po:patternType` | 是 |  | string |  |  |
| `po:allowsAction` | 是 |  |  | Action |  |
| `po:hasEffect` | 是 | 1 |  |  | urn:personalontology:ontology#Allow, urn:personalontology:ontology#Deny, urn:personalontology:ontology#Ask |
| `po:priority` | 是 |  | integer |  |  |
| `po:source` | 是 |  | string |  |  |
| `po:term` | 是 |  | string |  |  |
| `po:revoked` | 是 | 1 | boolean |  |  |
| `po:policyStatus` |  | 1 |  |  | draft, active, suspended |
| `po:createdAt` | 是 |  | dateTime |  |  |
| `po:hasConstraint` |  |  |  | Constraint |  |
| `po:hasRedline` |  |  |  | Redline |  |

### po:Constraint（约束）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:constraintType` | 是 |  | string |  |  |
| `po:constraintValue` | 是 |  |  |  |  |

### po:ContactPoint（联系方式）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:contactId` | 是 | 1 | string |  |  |
| `po:contactType` | 是 |  |  |  | phone, email, address |
| `po:value` | 是 |  | string |  |  |
| `po:label` | 是 |  | string |  |  |
| `po:verified` | 是 |  | boolean |  |  |
| `po:disclosure` | 是 |  |  |  | self_only, internal, external |
| `po:createdAt` | 是 |  | dateTime |  |  |

### po:Context（上下文）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:contextId` | 是 | 1 | string |  |  |
| `po:timestamp` | 是 |  | dateTime |  |  |
| `po:userStatus` | 是 |  |  | TaxonomyItem |  |
| `po:taskType` |  |  |  | TaxonomyItem |  |
| `po:sourceTrust` | 是 |  |  |  | high, medium, low |

### po:CryptoProvider（加密提供方）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:cryptoName` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  | string |  |  |
| `po:keySize` | 是 |  | integer |  |  |

### po:Decision（判定）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:decisionId` | 是 | 1 | string |  |  |
| `po:phase` | 是 |  |  |  | pre_planning, pre_execution |
| `po:hasResult` | 是 | 1 |  | DecisionResult |  |
| `po:reasonKey` | 是 |  | string |  |  |
| `po:inputParams` | 是 |  | JSON |  |  |
| `po:timestamp` | 是 |  | dateTime |  |  |
| `po:citesEvidence` |  |  |  | Evidence |  |

### po:DecisionResult（判定结果）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:resultId` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  |  |  |  |
| `po:displayNameEn` | 是 |  |  |  |  |
| `po:severity` | 是 |  | integer |  |  |
| `po:nextAction` | 是 |  |  |  | execute, pause, refuse |

### po:Execution（执行记录）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:executionId` | 是 | 1 | string |  |  |
| `po:interaction` | 是 |  |  | Interaction |  |
| `po:executedAs` | 是 |  |  | Decision |  |
| `po:action` | 是 |  | string |  |  |
| `po:executionResult` | 是 |  |  |  | success, failure, exception |
| `po:executedAt` | 是 |  | dateTime |  |  |

### po:Interaction（交互记录）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:interactionId` | 是 | 1 | string |  |  |
| `po:sessionId` | 是 |  | string |  |  |
| `po:userInput` | 是 |  | string |  |  |
| `po:status` | 是 |  |  |  | in_progress, completed, interrupted |
| `po:startedAt` | 是 |  | dateTime |  |  |
| `po:endedAt` |  | 1 | dateTime |  |  |

### po:Matcher（匹配器）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:patternType` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  |  |  |  |
| `po:displayNameEn` | 是 |  |  |  |  |

### po:Notifier（通知渠道）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:channelId` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  |  |  |  |
| `po:displayNameEn` | 是 |  |  |  |  |
| `po:enabled` | 是 | 1 | boolean |  |  |

### po:ParamDefinition（参数定义）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:paramName` | 是 | 1 | string |  |  |
| `po:paramType` | 是 |  |  |  | string, number, bool, date |
| `po:displayNameZh` | 是 |  |  |  |  |
| `po:displayNameEn` | 是 |  |  |  |  |
| `po:paramRequired` | 是 |  | boolean |  |  |

### po:Principal（主体）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:principalId` | 是 | 1 | string |  |  |
| `po:principalType` | 是 | 1 |  |  | person, agent, group, role, org, service |
| `po:displayNameZh` | 是 |  | string |  |  |
| `po:hasParent` |  | 1 |  | Principal |  |

### po:Redline（红线）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:redlineId` | 是 | 1 | string |  |  |
| `po:descriptionZh` | 是 |  | string |  |  |
| `po:descriptionEn` | 是 |  | string |  |  |
| `po:redlinePattern` | 是 |  | string |  |  |

### po:ResourceTypeDescriptor（资源类型）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:typeName` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  | string |  |  |
| `po:displayNameEn` | 是 |  | string |  |  |
| `po:usesMatcher` | 是 | 1 |  | Matcher |  |
| `po:supportsAction` |  |  |  | Action |  |
| `po:hasParam` |  |  |  | ParamDefinition |  |
| `po:defaultPriority` | 是 |  | integer |  |  |
| `po:isBuiltin` | 是 | 1 | boolean |  |  |

### po:ScenarioSlice（场景切片）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:scenarioId` | 是 | 1 | string |  |  |
| `po:originalText` | 是 | 1 | string |  |  |
| `po:scenarioStatus` | 是 | 1 |  |  | draft, analyzed, confirmed |
| `po:analysis` |  | 1 | JSON |  |  |
| `po:updatedAt` | 是 | 1 | dateTime |  |  |

### po:Taxonomy（分类）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:taxonomyId` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  |  |  |  |
| `po:displayNameEn` | 是 |  |  |  |  |
| `po:hasTaxonomyItem` | 是 |  |  | TaxonomyItem |  |
| `po:extensible` |  | 1 | boolean |  |  |

### po:TaxonomyItem（分类项）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:itemId` | 是 | 1 | string |  |  |
| `po:displayNameZh` | 是 |  |  |  |  |
| `po:displayNameEn` | 是 |  |  |  |  |
| `po:parentTaxonomyItem` |  | 1 |  | TaxonomyItem |  |

### po:Trigger（触发器）

| 属性 | 必填 | 最多 | 数据类型 | 指向类 | 可选值 |
|---|---|---|---|---|---|
| `po:triggerId` | 是 | 1 | string |  |  |
| `po:eventType` | 是 |  |  |  | time_expired, person_left, context_changed, risk_event |
| `po:condition` | 是 |  | string |  |  |
| `po:triggerAction` | 是 |  |  |  | revoke, escalate, notify |

## 四、集合 ↔ 类 ↔ 字段 ↔ 谓词映射

这一段是**代码侧**的映射（`backend/model.py`），决定 JSON 字段怎么变成三元组。

### `actions` → `po:Action`（id 字段：`actionId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `action_id` | `po:actionId` | lit |
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `applies_to` | `po:actionResourceType` | 引用 → resource-types |
| `risk_level` | `po:riskLevel` | lit |
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |

### `authorizations` → `po:Authorization`（id 字段：`authorizationId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `grantor_id` | `po:grantor` | 引用 → principals |
| `grantee_id` | `po:grantee` | 引用 → principals |
| `resource_type_id` | `po:appliesToResource` | 引用 → resource-types |
| `resource_pattern` | `po:resourcePattern` | lit |
| `pattern_type` | `po:patternType` | lit |
| `actions` | `po:allowsAction` | 引用 → actions |
| `effect` | `po:hasEffect` | effect |
| `priority` | `po:priority` | lit |
| `constraints` | `po:hasConstraint` | 引用 → constraints |
| `redlines` | `po:hasRedline` | 引用 → redlines |
| `source` | `po:source` | lit |
| `term` | `po:term` | lit |
| `revoked` | `po:revoked` | lit |
| `revoked_at` | `po:revokedAt` | lit |
| `created_at` | `po:createdAt` | lit |
| `policy_status` | `po:policyStatus` | lit |

### `constraints` → `po:Constraint`（id 字段：``）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `constraint_type` | `po:constraintType` | lit |
| `constraint_value` | `po:constraintValue` | lit |

### `contacts` → `po:ContactPoint`（id 字段：`contactId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `contact_type` | `po:contactType` | lit |
| `value` | `po:value` | lit |
| `label` | `po:label` | lit |
| `verified` | `po:verified` | lit |
| `disclosure` | `po:disclosure` | lit |
| `created_at` | `po:createdAt` | lit |

### `contexts` → `po:Context`（id 字段：`contextId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `timestamp` | `po:timestamp` | lit |
| `location` | `po:location` | lit |
| `device` | `po:device` | lit |
| `user_status_id` | `po:userStatus` | 引用 → taxonomy-items |
| `task_type_id` | `po:taskType` | 引用 → taxonomy-items |
| `source_trust` | `po:sourceTrust` | lit |

### `crypto-providers` → `po:CryptoProvider`（id 字段：`cryptoName`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `key_size` | `po:keySize` | lit |
| `description` | `po:descriptionZh` | lit |

### `decision-results` → `po:DecisionResult`（id 字段：`resultId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `severity` | `po:severity` | lit |
| `next_action` | `po:nextAction` | lit |
| `color` | `po:color` | lit |
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |

### `decisions` → `po:Decision`（id 字段：`decisionId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `interaction_id` | `po:interaction` | 引用 → interactions |
| `phase` | `po:phase` | lit |
| `sequence` | `po:sequence` | lit |
| `result_id` | `po:hasResult` | 引用 → decision-results |
| `reason_key` | `po:reasonKey` | lit |
| `reason_params` | `po:reasonParams` | json |
| `reason_display` | `po:reasonDisplay` | json |
| `input_params` | `po:inputParams` | json |
| `cited_assertions` | `po:citedAssertions` | lit |
| `timestamp` | `po:timestamp` | lit |
| `evidence_ids` | `po:citesEvidence` | 引用 → evidence |

### `domain-packs` → `po:DomainPack`（id 字段：`packId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |
| `version` | `po:packVersion` | lit |
| `lifecycle_state` | `po:lifecycleState` | lit |
| `entry_slots` | `po:entrySlots` | json |
| `fields` | `po:packFields` | json |
| `followups` | `po:followups` | json |
| `extends` | `po:extendsPack` | 引用 → domain-packs |
| `operators_required` | `po:operatorsRequired` | json |
| `is_builtin` | `po:packIsBuiltin` | lit |

### `evidence` → `po:Evidence`（id 字段：`evidenceId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `evidence_type` | `po:evidenceType` | lit |
| `created_at` | `po:createdAt` | lit |
| `digest` | `po:digest` | lit |

### `executions` → `po:Execution`（id 字段：`executionId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `interaction_id` | `po:interaction` | 引用 → interactions |
| `decision_id` | `po:executedAs` | 引用 → decisions |
| `action` | `po:action` | lit |
| `params` | `po:params` | json |
| `result` | `po:executionResult` | lit |
| `error_message` | `po:errorMessage` | lit |
| `executed_at` | `po:executedAt` | lit |

### `interactions` → `po:Interaction`（id 字段：`interactionId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `parent_interaction_id` | `po:parentInteraction` | 引用 → interactions |
| `session_id` | `po:sessionId` | lit |
| `user_input` | `po:userInput` | lit |
| `parsed_intent` | `po:parsedIntent` | json |
| `decision_ids` | `po:hasDecision` | 引用 → decisions |
| `execution_ids` | `po:hasExecution` | 引用 → executions |
| `status` | `po:status` | lit |
| `started_at` | `po:startedAt` | lit |
| `ended_at` | `po:endedAt` | lit |

### `knowledge-entries` → `po:KnowledgeEntry`（id 字段：`entryId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `slice_id` | `po:entryOfSlice` | 引用 → scenario-slices |
| `premise` | `po:premise` | json |
| `conclusion` | `po:conclusion` | lit |
| `exception` | `po:exceptionText` | lit |
| `basis` | `po:basis` | lit |
| `authority` | `po:authorityLevel` | lit |
| `applies_to` | `po:appliesTo` | json |
| `review_state` | `po:reviewState` | lit |
| `reviewed_by` | `po:reviewedBy` | lit |
| `reviewed_at` | `po:reviewedAt` | lit |
| `version` | `po:entryVersion` | lit |
| `tags` | `po:entryTags` | json |
| `updated_at` | `po:entryUpdatedAt` | lit |

### `matchers` → `po:Matcher`（id 字段：`patternType`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |

### `notifications` → `po:Notification`（id 字段：`notificationId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `channel_id` | `po:channelId` | lit |
| `created_at` | `po:createdAt` | lit |

### `notifiers` → `po:Notifier`（id 字段：`channelId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `priority` | `po:priority` | lit |
| `enabled` | `po:enabled` | lit |

### `params` → `po:ParamDefinition`（id 字段：`paramId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `param_name` | `po:paramName` | lit |
| `param_type` | `po:paramType` | lit |
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `required` | `po:paramRequired` | lit |

### `principals` → `po:Principal`（id 字段：`principalId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `principal_type` | `po:principalType` | lit |
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `parent_id` | `po:hasParent` | 引用 → principals |

### `profiles` → `po:Profile`（id 字段：`profileId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `principal_id` | `po:profileOf` | lit |
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `items` | `po:profileItems` | json |
| `note` | `po:profileNote` | lit |
| `updated_at` | `po:profileUpdatedAt` | lit |

### `redlines` → `po:Redline`（id 字段：`redlineId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |
| `redline_pattern` | `po:redlinePattern` | lit |

### `resource-types` → `po:ResourceTypeDescriptor`（id 字段：`typeName`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `type_name` | `po:typeName` | lit |
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `matcher_id` | `po:usesMatcher` | 引用 → matchers |
| `pattern_examples` | `po:patternExamples` | lit |
| `actions` | `po:supportsAction` | 引用 → actions |
| `params` | `po:hasParam` | 引用 → params |
| `default_priority` | `po:defaultPriority` | lit |
| `icon` | `po:icon` | lit |
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |
| `is_builtin` | `po:isBuiltin` | lit |

### `scenario-definitions` → `po:ScenarioDefinition`（id 字段：`scenarioDefinitionId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |
| `domain_pack_ids` | `po:usesDomainPack` | 引用 → domain-packs |
| `premise_fields` | `po:premiseFields` | json |
| `entry_slots` | `po:entrySlots` | json |
| `version` | `po:definitionVersion` | lit |
| `lifecycle_state` | `po:lifecycleState` | lit |
| `is_builtin` | `po:definitionIsBuiltin` | lit |
| `updated_at` | `po:definitionUpdatedAt` | lit |
| `framework` | `po:skillFramework` | json |
| `confidence` | `po:skillConfidence` | lit |
| `confidence_status` | `po:skillConfidenceStatus` | lit |
| `confidence_basis` | `po:skillConfidenceBasis` | lit |
| `boundaries` | `po:skillBoundaries` | json |
| `insight` | `po:skillInsight` | lit |
| `owner_credentials` | `po:skillOwnerCredentials` | lit |
| `valid_days` | `po:skillValidDays` | lit |
| `feedback_total` | `po:skillFeedbackTotal` | lit |
| `feedback_accurate` | `po:skillFeedbackAccurate` | lit |

### `scenario-slices` → `po:ScenarioSlice`（id 字段：`scenarioId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `original_text` | `po:originalText` | lit |
| `status` | `po:scenarioStatus` | lit |
| `analysis` | `po:analysis` | json |
| `updated_at` | `po:updatedAt` | lit |
| `scenario_definition_id` | `po:usesScenarioDefinition` | 引用 → scenario-definitions |
| `scenario_profile` | `po:scenarioProfile` | json |
| `framework` | `po:sliceFramework` | json |
| `boundaries` | `po:sliceBoundaries` | json |
| `insight` | `po:sliceInsight` | lit |
| `owner_credentials` | `po:sliceOwnerCredentials` | lit |
| `valid_days` | `po:sliceValidDays` | lit |
| `confidence` | `po:sliceConfidence` | lit |
| `confidence_status` | `po:sliceConfidenceStatus` | lit |
| `confidence_basis` | `po:sliceConfidenceBasis` | lit |
| `feedback_total` | `po:sliceFeedbackTotal` | lit |
| `feedback_accurate` | `po:sliceFeedbackAccurate` | lit |

### `taxonomies` → `po:Taxonomy`（id 字段：`taxonomyId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `items` | `po:hasTaxonomyItem` | 引用 → taxonomy-items |
| `extensible` | `po:extensible` | lit |
| `description_zh` | `po:descriptionZh` | lit |
| `description_en` | `po:descriptionEn` | lit |

### `taxonomy-items` → `po:TaxonomyItem`（id 字段：`itemId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `display_name_zh` | `po:displayNameZh` | lit |
| `display_name_en` | `po:displayNameEn` | lit |
| `parent_id` | `po:parentTaxonomyItem` | 引用 → taxonomy-items |
| `extra` | `po:extra` | json |

### `triggers` → `po:Trigger`（id 字段：`triggerId`）

| JSON 字段 | 谓词 | kind |
|---|---|---|
| `event_type` | `po:eventType` | lit |
| `condition` | `po:condition` | lit |
| `action` | `po:triggerAction` | lit |

## 五、属性声明（domain / range）

⚠️ 注意：`rdfs:domain` 会被 RDFS 推理用来**给节点定型**。例如 `po:updatedAt` 的 domain 是 `po:ScenarioSlice`，那么任何写了 `updated_at` 的节点都会被推断成场景切片，从而触发 ScenarioSlice 的必填形状而校验失败。新增集合时务必用**属于该类**的时间/名称属性，或直接复用不带 domain 的属性。

| 属性 | 类型 | domain | range |
|---|---|---|---|
| `po:action` | 数据类型属性 | Execution | string |
| `po:actionId` | 数据类型属性 | Action | string |
| `po:actionResourceType` | 对象属性 | Action | ResourceTypeDescriptor |
| `po:allowsAction` | 对象属性 | Authorization | Action |
| `po:analysis` | 数据类型属性 | ScenarioSlice | JSON |
| `po:appliesToResource` | 对象属性 | Authorization | ResourceTypeDescriptor |
| `po:authorizationId` | 数据类型属性 | Authorization | string |
| `po:channelId` | 数据类型属性 | — | string |
| `po:citesEvidence` | 对象属性 | Decision | Evidence |
| `po:condition` | 数据类型属性 | Trigger | string |
| `po:constraintType` | 数据类型属性 | Constraint | string |
| `po:constraintValue` | 数据类型属性 | Constraint | — |
| `po:contactId` | 数据类型属性 | ContactPoint | string |
| `po:contactType` | 数据类型属性 | ContactPoint | string |
| `po:contextId` | 数据类型属性 | Context | string |
| `po:createdAt` | 数据类型属性 | — | dateTime |
| `po:cryptoName` | 数据类型属性 | CryptoProvider | string |
| `po:decisionId` | 数据类型属性 | Decision | string |
| `po:defaultPriority` | 数据类型属性 | ResourceTypeDescriptor | integer |
| `po:descriptionEn` | 数据类型属性 | — | string |
| `po:descriptionZh` | 数据类型属性 | — | string |
| `po:disclosure` | 数据类型属性 | ContactPoint | string |
| `po:displayNameEn` | 数据类型属性 | — | string |
| `po:displayNameZh` | 数据类型属性 | — | string |
| `po:enabled` | 数据类型属性 | Notifier | boolean |
| `po:endedAt` | 数据类型属性 | Interaction | dateTime |
| `po:eventType` | 数据类型属性 | Trigger | string |
| `po:executedAs` | 对象属性 | Execution | Decision |
| `po:executedAt` | 数据类型属性 | Execution | dateTime |
| `po:executionId` | 数据类型属性 | Execution | string |
| `po:executionResult` | 数据类型属性 | Execution | string |
| `po:extensible` | 数据类型属性 | Taxonomy | boolean |
| `po:grantee` | 对象属性 | Authorization | Principal |
| `po:grantor` | 对象属性 | Authorization | Principal |
| `po:hasConstraint` | 对象属性 | Authorization | Constraint |
| `po:hasEffect` | 对象属性 | Authorization | AuthorizationEffect |
| `po:hasParam` | 对象属性 | ResourceTypeDescriptor | ParamDefinition |
| `po:hasParent` | 对象属性 | Principal | Principal |
| `po:hasRedline` | 对象属性 | Authorization | Redline |
| `po:hasResult` | 对象属性 | Decision | DecisionResult |
| `po:hasTaxonomyItem` | 对象属性 | Taxonomy | TaxonomyItem |
| `po:inputParams` | 数据类型属性 | Decision | JSON |
| `po:interaction` | 对象属性 | Execution | Interaction |
| `po:interactionId` | 数据类型属性 | Interaction | string |
| `po:isBuiltin` | 数据类型属性 | ResourceTypeDescriptor | boolean |
| `po:itemId` | 数据类型属性 | TaxonomyItem | string |
| `po:keySize` | 数据类型属性 | CryptoProvider | integer |
| `po:label` | 数据类型属性 | ContactPoint | string |
| `po:nextAction` | 数据类型属性 | DecisionResult | string |
| `po:originalText` | 数据类型属性 | ScenarioSlice | string |
| `po:paramId` | 数据类型属性 | ParamDefinition | string |
| `po:paramName` | 数据类型属性 | ParamDefinition | string |
| `po:paramRequired` | 数据类型属性 | ParamDefinition | boolean |
| `po:paramType` | 数据类型属性 | ParamDefinition | string |
| `po:parentTaxonomyItem` | 对象属性 | TaxonomyItem | TaxonomyItem |
| `po:patternType` | 数据类型属性 | — | string |
| `po:phase` | 数据类型属性 | Decision | string |
| `po:policyStatus` | 数据类型属性 | Authorization | string |
| `po:principalId` | 数据类型属性 | — | string |
| `po:principalType` | 数据类型属性 | — | string |
| `po:priority` | 数据类型属性 | Authorization | integer |
| `po:reasonKey` | 数据类型属性 | Decision | string |
| `po:redlineId` | 数据类型属性 | Redline | string |
| `po:redlinePattern` | 数据类型属性 | Redline | string |
| `po:resourcePattern` | 数据类型属性 | Authorization | string |
| `po:resultId` | 数据类型属性 | DecisionResult | string |
| `po:revoked` | 数据类型属性 | Authorization | boolean |
| `po:riskLevel` | 数据类型属性 | Action | string |
| `po:scenarioId` | 数据类型属性 | ScenarioSlice | string |
| `po:scenarioStatus` | 数据类型属性 | ScenarioSlice | string |
| `po:sessionId` | 数据类型属性 | Interaction | string |
| `po:severity` | 数据类型属性 | DecisionResult | integer |
| `po:source` | 数据类型属性 | Authorization | string |
| `po:sourceTrust` | 数据类型属性 | Context | string |
| `po:startedAt` | 数据类型属性 | Interaction | dateTime |
| `po:status` | 数据类型属性 | Interaction | string |
| `po:supportsAction` | 对象属性 | ResourceTypeDescriptor | Action |
| `po:taskType` | 对象属性 | Context | TaxonomyItem |
| `po:taxonomyId` | 数据类型属性 | Taxonomy | string |
| `po:term` | 数据类型属性 | Authorization | string |
| `po:timestamp` | 数据类型属性 | — | dateTime |
| `po:triggerAction` | 数据类型属性 | Trigger | string |
| `po:triggerId` | 数据类型属性 | Trigger | string |
| `po:typeName` | 数据类型属性 | ResourceTypeDescriptor | string |
| `po:updatedAt` | 数据类型属性 | ScenarioSlice | dateTime |
| `po:userInput` | 数据类型属性 | Interaction | string |
| `po:userStatus` | 对象属性 | Context | TaxonomyItem |
| `po:usesMatcher` | 对象属性 | ResourceTypeDescriptor | Matcher |
| `po:value` | 数据类型属性 | ContactPoint | string |
| `po:verified` | 数据类型属性 | ContactPoint | boolean |

## 六、新增一个集合要改哪些地方（清单）

1. `backend/model.py` 的 `CLASSES`：集合名 → 类名（RDF 里的 `rdf:type`）
2. `backend/model.py` 的 `FIELDS`：JSON 字段 → (谓词, kind)；kind 可为 `lit` / `json` / `effect` / 或某个集合名（表示引用）
3. `backend/model.py` 的 `ID_FIELDS` 与 `INPUT_ID_FIELDS`：id 字段的驼峰名与下划线名
4. 若该集合需要强制约束：在 `ontology/shapes.ttl` 里加一个 `sh:NodeShape` + `sh:targetClass`
5. 若用到新谓词：在 `ontology/personal-properties.ttl` 里声明（并想清楚 domain，见第五节警告）
6. 自测：`python -m py_compile backend/model.py` + 写入一次（会跑 SHACL）+ 跑相关测试套件

## 七、一个具体例子（场景切片）

```turtle
@prefix po: <urn:personalontology:ontology#> .

po:scenario-slices:scenario_slice_abc a po:ScenarioSlice ;
    po:scenarioId "scenario_slice_abc" ;
    po:originalText "预订酒店时先问清城市、入住日期、人数；房价不超过 300 元。" ;
    po:scenarioStatus "confirmed" .
```

对应到控制台里看到的：场景实例的「标题 / 每次必填 / 长期偏好 / 每次预填 / 授权规则」，都在这条切片的 RDF 图里（`analysis` 这类复杂字段整段存成 JSON 字面量）。

## 八、设计与局限（如实写）

- 全图在内存 + 每次写入全量 SHACL 校验：个人量级（10^2–10^4 节点）够用，百万级会慢。
- 没有索引层：复杂查询靠遍历。需要 SQL 式查询或语义检索时，应把容器数据投影到 PostgreSQL + pgvector 作为**读模型**，容器仍是事实源。
- 加密在应用层：容器文件对任何外部工具都是密文，这既是隐私保证，也意味着不能用通用工具直接查看。
