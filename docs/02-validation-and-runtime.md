# 个人本体治理系统 v3.0：验证与运行时规范

版本：3.0  
状态：设计基线  
依据：分享文档第一部分（设计总览、元模型、本体字段表）

本文对应设计分批中的第二部分：SHACL 验证、判定算法、注册中心和存储规范。核心原则是开放世界描述、运行时单一裁决点，以及 fail-closed（信息不足时不放行）。

## 1. 验证约定

- RDF 数据采用 Turtle 序列化；实例 URI 是稳定标识，字段名映射到元模型中的 `po:` 属性。
- SHACL 验证针对完整数据图执行。引用对象应使用 IRI，不以自由文本代替关系。
- 以下 Shapes 把字段表中的必填项落实为 `sh:minCount 1`；枚举值通过 `sh:in` 限定。
- `sh:closed false`：允许应用扩展属性，未知谓词不会使数据无效。安全敏感的核心决策字段仍由 shape 严格约束。
- JSON 对象字段（如 `reason_params`、`input_params`、`extra`）在 RDF 中用 `rdf:JSON` 字面量保存；实现也可用专门的属性图编码，但必须保持 API 往返一致。
- 自定义类型描述符可以扩展，但不得伪装成内置类型；`isBuiltin true` 只能由代码内置注册表产生。

命名空间：

```turtle
@prefix po:   <urn:personalontology:ontology#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
```

## 2. SHACL Shapes（19 个）

将本节保存为 `ontology/shapes.ttl`。所有 Shape 均为节点形状；跨节点引用的完整性（例如 grantee 是否存在）由 `sh:class` 校验。

```turtle
@prefix po:   <urn:personalontology:ontology#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

po:PrincipalShape a sh:NodeShape ; sh:targetClass po:Principal ;
  sh:property [ sh:path po:principalId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:principalType ; sh:minCount 1 ; sh:maxCount 1 ; sh:in ("person"^^xsd:string "agent"^^xsd:string "group"^^xsd:string "role"^^xsd:string "org"^^xsd:string) ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:hasParent ; sh:maxCount 1 ; sh:class po:Principal ] .

po:ResourceTypeDescriptorShape a sh:NodeShape ; sh:targetClass po:ResourceTypeDescriptor ;
  sh:property [ sh:path po:typeName ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:usesMatcher ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:Matcher ] ;
  sh:property [ sh:path po:supportsAction ; sh:class po:Action ] ;
  sh:property [ sh:path po:hasParam ; sh:class po:ParamDefinition ] ;
  sh:property [ sh:path po:defaultPriority ; sh:minCount 1 ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path po:isBuiltin ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] .

po:ParamDefinitionShape a sh:NodeShape ; sh:targetClass po:ParamDefinition ;
  sh:property [ sh:path po:paramName ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:paramType ; sh:minCount 1 ; sh:in ("string"^^xsd:string "number"^^xsd:string "bool"^^xsd:string "date"^^xsd:string) ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:paramRequired ; sh:minCount 1 ; sh:datatype xsd:boolean ] .

po:ActionShape a sh:NodeShape ; sh:targetClass po:Action ;
  sh:property [ sh:path po:actionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:actionResourceType ; sh:minCount 1 ; sh:class po:ResourceTypeDescriptor ] ;
  sh:property [ sh:path po:riskLevel ; sh:minCount 1 ; sh:in ("low"^^xsd:string "medium"^^xsd:string "high"^^xsd:string "critical"^^xsd:string) ] .

po:AuthorizationShape a sh:NodeShape ; sh:targetClass po:Authorization ;
  sh:property [ sh:path po:authorizationId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:grantor ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:Principal ] ;
  sh:property [ sh:path po:grantee ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:Principal ] ;
  sh:property [ sh:path po:appliesToResource ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:ResourceTypeDescriptor ] ;
  sh:property [ sh:path po:resourcePattern ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:patternType ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:allowsAction ; sh:minCount 1 ; sh:class po:Action ] ;
  sh:property [ sh:path po:hasEffect ; sh:minCount 1 ; sh:maxCount 1 ; sh:in (po:Allow po:Deny po:Ask) ] ;
  sh:property [ sh:path po:priority ; sh:minCount 1 ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path po:source ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:term ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:revoked ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] ;
  sh:property [ sh:path po:createdAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:hasConstraint ; sh:class po:Constraint ] ;
  sh:property [ sh:path po:hasRedline ; sh:class po:Redline ] .

po:ConstraintShape a sh:NodeShape ; sh:targetClass po:Constraint ;
  sh:property [ sh:path po:constraintType ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:constraintValue ; sh:minCount 1 ] .

po:RedlineShape a sh:NodeShape ; sh:targetClass po:Redline ;
  sh:property [ sh:path po:redlineId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:descriptionZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:descriptionEn ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:redlinePattern ; sh:minCount 1 ; sh:datatype xsd:string ] .

po:DecisionResultShape a sh:NodeShape ; sh:targetClass po:DecisionResult ;
  sh:property [ sh:path po:resultId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:severity ; sh:minCount 1 ; sh:minInclusive 0 ; sh:maxInclusive 10 ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path po:nextAction ; sh:minCount 1 ; sh:in ("execute"^^xsd:string "pause"^^xsd:string "refuse"^^xsd:string) ] .

po:DecisionShape a sh:NodeShape ; sh:targetClass po:Decision ;
  sh:property [ sh:path po:decisionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:phase ; sh:minCount 1 ; sh:in ("pre_planning"^^xsd:string "pre_execution"^^xsd:string) ] ;
  sh:property [ sh:path po:hasResult ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:DecisionResult ] ;
  sh:property [ sh:path po:reasonKey ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:inputParams ; sh:minCount 1 ; sh:datatype rdf:JSON ] ;
  sh:property [ sh:path po:timestamp ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:citesEvidence ; sh:class po:Evidence ] .

po:TaxonomyShape a sh:NodeShape ; sh:targetClass po:Taxonomy ;
  sh:property [ sh:path po:taxonomyId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:hasTaxonomyItem ; sh:minCount 1 ; sh:class po:TaxonomyItem ] ;
  sh:property [ sh:path po:extensible ; sh:datatype xsd:boolean ; sh:maxCount 1 ] .

po:TaxonomyItemShape a sh:NodeShape ; sh:targetClass po:TaxonomyItem ;
  sh:property [ sh:path po:itemId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:parentTaxonomyItem ; sh:maxCount 1 ; sh:class po:TaxonomyItem ] .

po:ContextShape a sh:NodeShape ; sh:targetClass po:Context ;
  sh:property [ sh:path po:contextId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:timestamp ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:userStatus ; sh:minCount 1 ; sh:class po:TaxonomyItem ] ;
  sh:property [ sh:path po:taskType ; sh:class po:TaxonomyItem ] ;
  sh:property [ sh:path po:sourceTrust ; sh:minCount 1 ; sh:in ("high"^^xsd:string "medium"^^xsd:string "low"^^xsd:string) ] .

po:InteractionShape a sh:NodeShape ; sh:targetClass po:Interaction ;
  sh:property [ sh:path po:interactionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:sessionId ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:userInput ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:status ; sh:minCount 1 ; sh:in ("in_progress"^^xsd:string "completed"^^xsd:string "interrupted"^^xsd:string) ] ;
  sh:property [ sh:path po:startedAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:endedAt ; sh:maxCount 1 ; sh:datatype xsd:dateTime ] .

po:ExecutionShape a sh:NodeShape ; sh:targetClass po:Execution ;
  sh:property [ sh:path po:executionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:interaction ; sh:minCount 1 ; sh:class po:Interaction ] ;
  sh:property [ sh:path po:executedAs ; sh:minCount 1 ; sh:class po:Decision ] ;
  sh:property [ sh:path po:action ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:executionResult ; sh:minCount 1 ; sh:in ("success"^^xsd:string "failure"^^xsd:string "exception"^^xsd:string) ] ;
  sh:property [ sh:path po:executedAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] .

po:ContactPointShape a sh:NodeShape ; sh:targetClass po:ContactPoint ;
  sh:property [ sh:path po:contactId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:contactType ; sh:minCount 1 ; sh:in ("phone"^^xsd:string "email"^^xsd:string "address"^^xsd:string) ] ;
  sh:property [ sh:path po:value ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:label ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:verified ; sh:minCount 1 ; sh:datatype xsd:boolean ] ;
  sh:property [ sh:path po:disclosure ; sh:minCount 1 ; sh:in ("self_only"^^xsd:string "internal"^^xsd:string "external"^^xsd:string) ] ;
  sh:property [ sh:path po:createdAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] .

po:MatcherShape a sh:NodeShape ; sh:targetClass po:Matcher ;
  sh:property [ sh:path po:patternType ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] .

po:NotifierShape a sh:NodeShape ; sh:targetClass po:Notifier ;
  sh:property [ sh:path po:channelId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:enabled ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] .

po:CryptoProviderShape a sh:NodeShape ; sh:targetClass po:CryptoProvider ;
  sh:property [ sh:path po:cryptoName ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:keySize ; sh:minCount 1 ; sh:minInclusive 16 ; sh:datatype xsd:integer ] .

po:TriggerShape a sh:NodeShape ; sh:targetClass po:Trigger ;
  sh:property [ sh:path po:triggerId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:eventType ; sh:minCount 1 ; sh:in ("time_expired"^^xsd:string "person_left"^^xsd:string "context_changed"^^xsd:string "risk_event"^^xsd:string) ] ;
  sh:property [ sh:path po:condition ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:triggerAction ; sh:minCount 1 ; sh:in ("revoke"^^xsd:string "escalate"^^xsd:string "notify"^^xsd:string) ] .

```

### 2.1 字段名对齐说明

元模型的补充属性声明位于 `ontology/personal-properties.ttl`。映射采用 lowerCamelCase，例如 `reason_key` → `po:reasonKey`、`execution_result` → `po:executionResult`。为避免把 OWL 的 `rdfs:domain` 多值误作“任选其一”，资源类型支持动作使用 `po:supportsAction`，动作适用资源类型使用 `po:actionResourceType`，授权主体层级使用 `po:hasParent`，标签层级使用 `po:parentTaxonomyItem`。`Authorization` 中 `effect` 以 `po:hasEffect` 指向 `po:Allow` / `po:Deny` / `po:Ask`。若 API 使用字符串，转换只发生在序列化边界。

## 3. 判定算法

### 3.1 请求结构

```json
{
  "request_id": "uuid",
  "principal_id": "principal:alice",
  "action_id": "file.read",
  "resource": {"type": "file", "id": "/docs/plan.md"},
  "context": {"timestamp": "RFC3339", "source_trust": "high"},
  "phase": "pre_execution"
}
```

必填项缺失、类型不符、无法解析身份或资源时，结果为 `pause`（需补充信息），不得默认为允许。

### 3.2 决策顺序

对每个请求执行以下确定性流程，并为每一步写入决策证据：

1. **规范化输入**：验证字段和时间格式；解析主体验证状态、资源类型、动作 ID。
2. **加载一致性快照**：读取同一版本的授权、主体继承关系、红线、注册表和上下文；记录 `policy_revision`。
3. **应用红线**：任一已启用红线匹配主体、动作、资源或上下文，立即拒绝。红线先于 allow/ask/deny 普通授权。
4. **构造候选授权集**：包括主体自身规则及其父组、角色、组织的继承规则；检测循环并停止继承，记录配置错误。
5. **过滤候选项**：授权未撤销、未过期，主体与动作匹配，资源类型相同，注册的 matcher 成功匹配，时间及其他约束成立。无法执行的约束视为不满足。
6. **合并效果**：候选中有匹配 deny 时 deny 优先；否则有 ask 时 pause；否则至少一个匹配 allow 才允许；没有匹配规则则拒绝（默认拒绝）。同优先级不改变 deny > ask > allow 顺序。优先级仅用于解释和确定主要引用规则，不得覆盖 deny 或红线。
7. **风险门槛**：`critical` 动作必须满足显式 allow 且无任何未知/低可信关键上下文；`high` 动作的未知约束返回 pause。不得因注册表缺失而降级风险。
8. **输出判定**：映射到已注册 `DecisionResult`，包含结果、`next_action`、原因 key/参数、命中的授权和证据、输入快照摘要、策略版本与时间。
9. **执行前复核**：实际执行前以最新快照再次判定 `pre_execution`。若主体、资源、动作、策略版本或相关上下文改变，旧的 allow 失效。
10. **记录执行**：只在明确 allow 时调用动作执行器；记录成功、失败或异常。判定本身不执行资源操作。

### 3.3 输出契约

```json
{
  "decision_id": "decision:uuid",
  "result_id": "allow|deny|ask",
  "next_action": "execute|refuse|pause",
  "reason_key": "decision.explicit_allow",
  "reason_params": {},
  "phase": "pre_execution",
  "policy_revision": "sha256:…",
  "cited_assertions": ["authorization:…"],
  "timestamp": "RFC3339"
}
```

API 的 `result_id` 以注册的结果 ID 为准；上面三个名称是默认内置结果。前端显示文本由 `reason_key` 与语言包生成，审计记录同时保存当时显示文本，避免后续翻译修改影响历史。

## 4. 注册中心规范

注册中心包含八类：Resource、Action、Constraint、DecisionResult、Matcher、Taxonomy、Notifier、CryptoProvider。内置项由应用启动时加载且只读；扩展项存入本体图并经过 SHACL 校验。

### 4.1 通用注册项

每项需有稳定 `id`、`version`、中英文名称、说明、启用状态、来源、创建/更新时间。ID 在各自类别内唯一。启用前必须校验依赖引用与能力声明；注销使用停用或弃用状态，已有审计记录继续可读。

### 4.2 注册接口契约

- `list(category, include_disabled=false)`：按 ID 稳定排序返回。
- `get(category, id, version?)`：指定版本不可变读取。
- `validate(category, definition)`：SHACL + 类型专属检查，返回机器可读问题列表。
- `register(category, definition, expected_revision)`：乐观并发写入；修订冲突返回 409。
- `deprecate(category, id, expected_revision)`：停止新引用，不破坏历史引用。
- `resolve(category, id)`：只返回启用且兼容的版本；未找到必须显式报错。

### 4.3 各类要求

- **Resource**：含类型名、matcher、参数定义、可用动作、优先级。自定义资源类型不能声明任意代码入口。
- **Action**：风险等级和适用资源类型不可缺省；执行器代码与动作元数据分开管理。
- **Constraint**：注册可执行、纯函数式约束；声明输入 schema、确定性、超时上限。超时/异常按不满足处理。
- **DecisionResult**：声明 0–10 severity 和 `execute/pause/refuse`；内置 allow 类结果不得自定义为高风险绕过。
- **Matcher**：只支持已审核 matcher 实现；正则需限制长度、输入长度和运行时间，禁止灾难性回溯。matcher 错误不是匹配成功。
- **Taxonomy**：定义 ID、标签项及是否 extensible；引用删除采用弃用，不复用 ID。
- **Notifier**：声明频道和能力；密钥由 secret store 持有，配置图只保存 secret 引用。
- **CryptoProvider**：只声明算法/密钥元数据，密钥材料不进入 RDF、本体文件或普通配置日志。

## 5. 数据存储规范

### 5.1 数据分区

1. **Schema 图**：元模型、SHACL shapes、内置词表版本；随应用发行，只读。
2. **Ontology 图**：自定义资源类型、标签体系、用户扩展的规则定义；支持版本修订。
3. **业务图**：主体、授权、上下文、互动、决策、执行、证据等实例数据。
4. **Secret store**：加密密钥、Notifier 凭据及敏感接入配置；不与 RDF 图混存。

### 5.2 事务与修订

- 授权变更、撤销、注册表修改必须在一个事务内提交，并递增单调 `revision`。
- 判定读取事务一致性快照；决策记录写入实际使用的 `revision`。
- 运行时缓存以 revision 为键；提交后发布失效事件。无法确认缓存版本时绕过缓存读取权威存储。
- 变更采用 append-only 审计事件，当前状态可物化更新；修订事件包含 actor、时间、变更摘要和前后哈希。
- 并发写采用 `expected_revision`；冲突不自动覆盖。

### 5.3 隐私、保留与备份

- 联系方式 `ContactPoint.value` 在应用层加密后存储；普通日志仅可记录不可逆脱敏值或稳定 HMAC，不记录明文。
- 用户输入、上下文和执行错误可能含敏感内容；存储接口支持按字段加密、保留期限与删除/匿名化策略。
- 审计证据需尽量保存最小必要信息；无法保留原文时保存摘要、来源、时间、完整性哈希及删除原因。
- 备份加密，密钥与备份分离；备份包含图数据、修订、SHACL/元模型版本和迁移元数据。
- 恢复后先校验完整性，再运行 SHACL 和引用完整性检查；检查未通过时只读启动并禁止授权判定放行。

### 5.4 迁移与兼容

- 每个 schema/ontology 迁移有唯一版本、前置版本、可重复执行标记和校验步骤。
- 迁移按“备份 → 校验备份 → 迁移临时副本 → SHACL 校验 → 原子切换”执行。
- 不支持降级迁移时，恢复到迁移前备份；不得在原数据上进行不可逆试验。
- 不认识的扩展谓词保留；无法解释的关键授权字段导致该规则失效并生成诊断，不能按 allow 处理。

## 6. 一致性与错误处理

| 情况 | 处理 |
|---|---|
| SHACL 校验失败 | 拒绝写入；返回 shape、focus node、path、severity、message |
| 引用对象缺失 | 拒绝写入；读取旧数据时将相关规则标记无效 |
| matcher/constraint 未注册或执行失败 | 该候选规则不匹配；高风险请求 pause 或 deny，绝不 allow |
| 注册版本冲突 | 返回冲突和当前 revision，由调用方重新读取后提交 |
| 存储不可用或快照不一致 | 判定不可用，不调用执行器 |
| 决策结果类型缺失 | 使用内置 deny/pause 安全结果并发出配置告警 |

## 7. 实施边界

本文给出数据验证和运行时设计基线。合并后的元模型需加载 `ontology/personal-properties.ttl`，使 Shape 引用的属性有明确的 RDF 属性类型和适用范围。SHACL 负责结构和局部约束；授权合并、继承环检测、红线匹配和执行前复核由判定引擎实现，不能仅依靠 OWL 推理或 SHACL 代替。
