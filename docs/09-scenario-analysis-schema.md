# 场景分析数据结构（analysis）契约

本文冻结**场景切片分析结果**的结构。它存放在 `scenario-slices` 记录的 `analysis` 字段里
（RDF 中为 `rdf:JSON` 字面量），是**大模型输出与后端编译之间的契约**。

> 注意分工：`docs/05` 冻结的是**加密容器格式**；本文冻结的是**分析结果结构**。
> 两者独立，互不影响。本文不含任何密钥或加密细节。

## 1. 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | string | 场景标题 |
| `scope` | object | `{mode:"global"｜"segmented", dimension?, label?}` |
| `resource_types` | array | 本场景处理的资源类型，`[{name, description?, existing_id?}]` |
| `actions` | array | 本场景的动作，`[{name, description?, risk?, existing_id?}]` |
| `required_inputs` | array | 每次执行要收集的字段（见 §2） |
| `facts` | array | 长期偏好（见 §2） |
| `questions` | array | 模型追问 `[{question, field?, reason?}]`，回答后回填并重跑分析 |
| `policies` | array | 授权策略草稿（见 §3），确认时编译成授权规则 |
| `segmentation` | object | 偏好适用范围（见 §4），`segmentation_schema_version=1` |
| `generated` | object | **后端写入**，记录落地结果（见 §5），模型不应输出 |
| `demoted_fields` | array | **后端写入**：因不适合做运行时字段被降级的项目 |

## 2. 字段分档（三档）—— 每个字段必须给出 `role` 与 `role_reason`

| `role` | 含义 | 应出现在 |
|---|---|---|
| `required` | 值每次不同，且不提供就无法执行 | **仅** `required_inputs` |
| `preference` | 一贯立场，与本次无关，编译成判定条件 | **仅** `facts` |
| `both` | 既有长期立场、值又每次不同 | **同时**出现在两个数组 |

`role_reason` 为一句话理由，界面会展示给用户核对。

**为什么需要 `both`**：`_prune_preferences` 原先丢弃"运行时字段"的偏好，`_compile_rules`
把运行时字段的条件降级为 `exists`，因此"只订未来 30 天内的 + 具体日期"这类字段**无法表达**。
现在：`both` 字段保留在必填清单，**且其立场条件不被降级**（`numeric_lte` 等照常编译）。

- `required_inputs[]`：`{name, label, type, required, help?, role, role_reason?}`
- `facts[]`：`{name, label, value, type, source, role, role_reason?}`
  - `source="user"` 用户明确给出；`source="suggestion"` 模型建议（不参与偏好回退）

## 3. 策略（`policies[]`）

```
{ subject, resource, effect: "allow"|"deny"|"ask", actions: [动作名], conditions: [...] }
```

- **`actions` 必填**：取值必须是本场景 `actions` 里出现过的**名称**。不同动作有不同立场时必须
  拆成多条策略（"允许查看、禁止删除" = 两条）。缺失或名字对不上时回退到"全部动作"。
- `conditions[]`：`{field, operator, value?}`，`operator ∈ {equals, lte, gte, exists, ...}`。
- **禁止无条件的 deny**：`effect="deny"` 且 `conditions` 为空、且场景还有其他策略时，
  该策略会被**跳过并写入 `compile_report`**（deny 优先级最高，无条件拒绝会否决全部动作）。

## 4. 偏好适用范围（`segmentation`）

```
{mode:"global"|"segmented", dimensions:[{field,label,type}], global_preferences:[], variants:[]}
```

偏好项：`{field, label, type, value, operator, strength:"must"}`。
`operator` 支持 `equals/lte/gte/exists`；**值不是数值时 `lte/gte` 会自动降级为 `equals`**
（而非拒绝整次保存）。字段若在 `required_inputs` 里且未被声明为长期偏好，条件降级为 `exists`。

## 5. `generated`（后端写入）

| 字段 | 说明 |
|---|---|
| `resource_type_id` / `resource_type_ids` | 第一个 / 全部落地的资源类型 ID |
| `created_resource_type` / `created_resource_type_ids` | 本场景**新建**（区别于复用）的类型 |
| `action_ids` / `created_action_ids` | 动作 ID 与新建的动作 ID |

首个资源类型沿用 `scene_<suffix>_resource`，其余为 `..._resource_N`；动作沿用
`scene_<suffix>_action_<n>`。**删除场景只删除自己新建的类型与动作**（复用的公共词汇保留）。

## 6. 向后兼容

| 情况 | 行为 |
|---|---|
| 策略缺 `actions` | 回退到该场景全部动作（旧数据不改变行为） |
| 字段缺 `role` | 分析出口补默认档位（必填项→`required`，偏好→`preference`） |
| 规范化改了字段名（`budget_max`→`price_max`） | 按 `changes` 的改名记录建别名表搬运 `role`（`_carry_role`） |
| `role="both"` 但字段在 `NEVER_RUNTIME` | **不降级**，仍保留在必填清单 |

## 7. 已知模型行为陷阱（由两轮场景切片推演查出）

1. **策略缺动作维度** → "禁止删除"退化为无条件 deny → 否决全部动作（已在契约层禁止）
2. **无条件 deny** → 同上（已拦截并报出）
3. **跨领域扩张** → "文件"场景吞并"网络连接"的资源类型与动作（提示词已约束）
4. **多资源类型丢失** → 只落地 `types[0]`，其余静默丢弃（已修：逐一落地）
5. **把"决定规则边界的字段"误放进必填** → 例如操作类型（查看/编辑/删除）既是每次执行才知道的，
   又是规则要区分的对象。提示词要求逐字段给出 `role_reason` 正是为了让这类误判**可被人工发现**。

## 8. 相关文件

- 实现：`backend/scenario_llm.py`（提示词与解析）、`backend/api.py`（`_compile_rules`、
  `_normalize_segmentation`、`confirm_scene`）、`backend/field_names.py`（规范化与 `role` 搬运）
- 测试：`tests/test_policy_actions.py`、`tests/test_multi_resource.py`、`tests/test_both_tier.py`
- 容器格式与加密：`docs/05-secret-and-sensitive-data-design.md`

## 9. 可执行的契约

本文不只是文档，配套两件可执行的东西：

**(1) 机器可读的 schema** —— `schemas/scenario-analysis.schema.json`（JSON Schema 2020-12）。
供程序校验，也可让**别的实现**（例如将来若恢复 iOS，Swift 侧）直接照它对齐，不必读 Python 反推。

**(2) 运行时校验** —— `backend/analysis_contract.py` 的 `validate_analysis()`，
在分析出口（`scenario_llm.analyze`）调用，结果写入 `analysis.contract_notes`。

取向与既有容错一致：**违规不阻断分析**，只记录，供界面提示。每条说明含：

| 字段 | 说明 |
|---|---|
| `code` | 稳定标识（供界面/i18n 映射），如 `policy_missing_actions` |
| `field` | 具体位置，如 `policies[2]`、`required_inputs.城市` |
| `message` | 中文说明 |
| `level` | `warn`（后端已容错）或 `error`（需要人看一眼） |

能自动抓到的违规：缺少标题 / 无资源类型 / 无动作 / **策略缺 `actions`** /
**策略引用了不存在的动作** / **无条件 deny** / 字段缺 `role` / `role` 值非法 /
字段名非英文键 / 同一清单重复字段名 / 标为 `both` 却不在两个清单 /
标为 `required` 却在偏好清单 / 标为 `preference` 却在必填清单。

界面上，切片页的「模型对字段的分档判断」摘要行会显示 **`N 处契约提醒`** 徽章，
展开后逐条列出。

**测试**：`tests/test_analysis_contract.py`（10/10），覆盖第 7 节记录的五类陷阱。
**意义**：模型换版本、换厂商时，第一时间就能知道输出是否仍合规——不必再靠两轮推演发现。
