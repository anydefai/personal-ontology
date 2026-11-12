# 02 · 数据模型

> 唯一事实来源：`backend/model.py`（集合→类、字段→谓词、ID 字段）。
> 本文件的表格由该文件**自动生成**，改完模型请重新生成，不要手抄。

## 1. 三层映射

```
集合名（API 里用的）     model.CLASSES         RDF 类
如 "profile-items"  →   "ProfileItem"    →    po:ProfileItem
字段名（JSON 里的）      model.FIELDS          RDF 谓词
如 "label_zh"       →   ("displayNameZh", "lit")  →  po:displayNameZh
主键字段               model.ID_FIELDS
如 "profile-items"  →   "itemId"         →  节点 URI 的末段
```

字段映射的第二个元素决定值的写法：

| 类型 | 含义 | 落盘 |
|---|---|---|
| `lit` | 字面量（字符串/数字/日期） | `xsd:string` 等 |
| `json` | 结构化值（数组 / 对象） | JSON 字符串 + `rdf:JSON` 标记 |
| 其它（集合名） | 指向另一个集合的引用 | `po:<集合名>:<id>` 形式的节点 |

## 2. 全部 37 个集合

| 集合 | 类 | 字段数 | 主键 | 部分谓词 |
|---|---|---|---|---|
| `actions` | Action | 7 | `actionId` | action_id→actionId, display_name_zh→displayNameZh, display_name_en→displayNameEn, applies_to→actionResourceType … |
| `asset-transactions` | AssetTransaction | 9 | `transactionId` | asset_id→transactionOf, occurred_at→occurredAt, amount→amount, direction→direction … |
| `assets` | Asset | 9 | `assetId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, asset_kind→assetKind, identifier_masked→assetMasked … |
| `authorizations` | Authorization | 17 | `authorizationId` | grantor_id→grantor, grantee_id→grantee, resource_type_id→appliesToResource, resource_pattern→resourcePattern … |
| `circle-changes` | CircleChange | 6 | `changeId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, circle_id→changeOfCircle, change_kind→circleChangeKind … |
| `circle-members` | CircleMember | 10 | `memberId` | circle_id→memberOfCircle, principal_id→memberPrincipalId, contact_ref→memberContactRef, display_name_zh→displayNameZh … |
| `circles` | Circle | 8 | `circleId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, circle_type→circleType, my_role→myRoleInCircle … |
| `commitments` | Commitment | 10 | `commitmentId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, commitment_kind→commitmentKind, counterparty_kind→counterpartyKind … |
| `constraints` | Constraint | 2 | `—` | constraint_type→constraintType, constraint_value→constraintValue |
| `contact-records` | ContactRecord | 16 | `contactRecordId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, contact_org→contactOrg, contact_title→contactTitle … |
| `contacts` | ContactPoint | 6 | `contactId` | contact_type→contactType, value→value, label→label, verified→verified … |
| `contexts` | Context | 6 | `contextId` | timestamp→timestamp, location→location, device→device, user_status_id→userStatus … |
| `crypto-providers` | CryptoProvider | 3 | `cryptoName` | display_name_zh→displayNameZh, key_size→keySize, description→descriptionZh |
| `decision-results` | DecisionResult | 7 | `resultId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, severity→severity, next_action→nextAction … |
| `decisions` | Decision | 11 | `decisionId` | interaction_id→interaction, phase→phase, sequence→sequence, result_id→hasResult … |
| `devices` | Device | 8 | `deviceId` | display_name_zh→displayNameZh, device_kind→deviceKind, agent_client_id→agentClientId, trust_level→deviceTrustLevel … |
| `domain-packs` | DomainPack | 12 | `packId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, description_zh→descriptionZh, description_en→descriptionEn … |
| `evidence` | Evidence | 3 | `evidenceId` | evidence_type→evidenceType, created_at→createdAt, digest→digest |
| `executions` | Execution | 7 | `executionId` | interaction_id→interaction, decision_id→executedAs, action→action, params→params … |
| `interactions` | Interaction | 9 | `interactionId` | parent_interaction_id→parentInteraction, session_id→sessionId, user_input→userInput, parsed_intent→parsedIntent … |
| `knowledge-entries` | KnowledgeEntry | 13 | `entryId` | slice_id→entryOfSlice, premise→premise, conclusion→conclusion, exception→exceptionText … |
| `matchers` | Matcher | 4 | `patternType` | display_name_zh→displayNameZh, display_name_en→displayNameEn, description_zh→descriptionZh, description_en→descriptionEn |
| `notifications` | Notification | 2 | `notificationId` | channel_id→channelId, created_at→createdAt |
| `notifiers` | Notifier | 4 | `channelId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, priority→priority, enabled→enabled |
| `params` | ParamDefinition | 5 | `paramId` | param_name→paramName, param_type→paramType, display_name_zh→displayNameZh, display_name_en→displayNameEn … |
| `places` | Place | 8 | `placeId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, place_kind→placeKind, address_text→addressText … |
| `principals` | Principal | 5 | `principalId` | principal_type→principalType, display_name_zh→displayNameZh, display_name_en→displayNameEn, parent_id→hasParent … |
| `profile-items` | ProfileItem | 9 | `itemId` | profile_id→itemOfProfile, field_key→itemFieldKey, label_zh→displayNameZh, label_en→displayNameEn … |
| `profile-reveals` | ProfileReveal | 6 | `revealId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, item_id→revealOfItem, profile_id→revealOfProfile … |
| `profiles` | Profile | 6 | `profileId` | principal_id→profileOf, display_name_zh→displayNameZh, display_name_en→displayNameEn, items→profileItems … |
| `redlines` | Redline | 3 | `redlineId` | description_zh→descriptionZh, description_en→descriptionEn, redline_pattern→redlinePattern |
| `resource-types` | ResourceTypeDescriptor | 12 | `typeName` | type_name→typeName, display_name_zh→displayNameZh, display_name_en→displayNameEn, matcher_id→usesMatcher … |
| `scenario-definitions` | ScenarioDefinition | 21 | `scenarioDefinitionId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, description_zh→descriptionZh, description_en→descriptionEn … |
| `scenario-slices` | ScenarioSlice | 16 | `scenarioId` | original_text→originalText, status→scenarioStatus, analysis→analysis, updated_at→updatedAt … |
| `taxonomies` | Taxonomy | 6 | `taxonomyId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, items→hasTaxonomyItem, extensible→extensible … |
| `taxonomy-items` | TaxonomyItem | 4 | `itemId` | display_name_zh→displayNameZh, display_name_en→displayNameEn, parent_id→parentTaxonomyItem, extra→extra |
| `triggers` | Trigger | 3 | `triggerId` | event_type→eventType, condition→condition, action→triggerAction |

## 3. 三个必踩的坑

### 坑 1：复用带 `rdfs:domain` 的谓词，会把节点重新定型

`store._validate()` 把本体与数据合并后跑 `inference="rdfs"`。
若某个谓词带 `rdfs:domain po:ScenarioSlice`，那么任何写了该谓词的节点都会被推理成"场景切片"，
接着触发 ScenarioSlice 的 SHACL 形状 —— 报错内容完全与你的新集合无关，极难定位。

**规则**：新集合一律用**专属谓词**（`profileUpdatedAt`、`circleType`、`deviceKind`、`contactTags`…）。
唯一例外是 `displayNameZh` / `displayNameEn`：它们没有 domain，但被通用形状**要求**，所以新集合通常都要带。

### 坑 2：单值关系从图里读回来是标量，不是列表

`constraints: [id]` 这种单值关系，读回后是字符串 `"id"`。
直接 `for x in value` 会遍历字符。凡是"可能是列表"的字段，读的时候一律归一化：

```python
values = record.get("actions", [])
if not isinstance(values, list):
    values = [values] if values else []
```

### 坑 3：删除会被"被引用"挡住

`store.delete()` 会检查入边，若还有记录指向它，抛 `StoreError("cannot delete; referenced by N ...")`。
这是**故意**的（防止悬空引用）。因此级联删除要在调用方显式做，例如：

- 删资料 → 先删该资料下的 `profile-items`；
- 删圈 → 先删 `circle-members` 与 `circle-changes`，有授权规则指向它时直接 409 拒绝；
- 删资产 → **不删**流水（流水在独立段，删资产只报告条数）。

## 4. 新增一个集合的 SOP（照做不会出错）

```python
# ① model.py 三处都要改
CLASSES["my-things"] = "MyThing"
FIELDS["my-things"] = {
    "display_name_zh": ("displayNameZh", "lit"),   # 通用形状要求
    "display_name_en": ("displayNameEn", "lit"),
    "my_updated_at":   ("myUpdatedAt", "lit"),     # 专属谓词，别用 updatedAt
}
ID_FIELDS["my-things"] = "myThingId"

# ② 落地后立刻断言（漏了这步会浪费半天）
python3 -c "import sys;sys.path.insert(0,'.');from backend import model as M;\
assert 'my-things' in M.CLASSES and 'my-things' in M.FIELDS and 'my-things' in M.ID_FIELDS"

# ③ 写测试：建 → 读 → 改 → 删 → 校验失败分支
# ④ 跑闸门（见 07-testing.md）
```

如果集合涉及大量数据（导入、日志、流水），**不要**走主图，走 ledger 段（见 03）。

## 5. 数据集与常量

| 名字 | 位置 | 说明 |
|---|---|---|
| `DATETIME_FIELDS` | model.py | 这些字段才允许被推断成 `xsd:dateTime`（曾因"任何含 T 的长字符串都当时间"导致 422） |
| `NUMBER_FIELDS` / `BOOLEAN_FIELDS` | model.py | 数值与布尔字段集合 |
| `shapes.ttl` | ontology/ | SHACL 形状：必填、类型、范围、枚举 |
| `personal-properties.ttl` | ontology/ | 谓词的 OWL 定义（domain/range/标签） |

## 6. 改模型时的自检清单

```
□ 新谓词是否专属？（不要复用 updated_at / createdAt / sensitivity 这类通用名，除非确认无 domain）
□ 三条：CLASSES / FIELDS / ID_FIELDS 都加了吗？（有断言脚本）
□ displayNameZh / displayNameEn 加了吗？（通用形状要）
□ 是否可以只在 ledger 段？（大批量数据）
□ 删除路径上的级联对象想清楚了吗？
□ 闸门里 test_bilingual_coverage / test_label_localization 是否还会过？
```
