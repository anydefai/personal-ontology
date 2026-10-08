# 判定模型架构设计：引擎与算法分离（待确认，未写代码）

> 状态：**设计稿。** 你确认后才动代码。目标：判定模型**不写在引擎里**，而是可声明、可替换、可版本化、可审计。

---

## 一、问题（我实测的证据）

```
backend/skill_framework.py 一个 374 行的文件里同时焊着四样东西：
  ① 判定模型的字段名   signals 出现 7 次、combination_rules 2 次、score_bands/thresholds/… 各 1 次
  ② 执行顺序           compute_threshold → eval_signals → 例外 → 组合规则 → 打分 → 兜底
  ③ 那一条算法         score += weights[dim] * weight_factors[dim]     （第 227 行）
  ④ 输出的裁剪与分层   判定包字段、TIERS/ALWAYS
全文件搜不到 model / registry / plugin / strategy / scorecard —— 一个都没有。
→ 后果：想支持另一种判定方式（要件逻辑、领域公式）＝ 改产品代码。这正是必须改掉的地方。
```

## 二、目标（四条，都可验收）

1. **判定模型可声明**：切片自己说"我用哪种判定模型"。
2. **算法可替换**：新增一种判定方式 = 新增一个模型文件 + 注册一行，**不改引擎**。
3. **可版本化、可审计**：判定包里记下 `model` 与 `model_version`，事后能复现"当时用哪个算法"。
4. **零破坏**：现有切片、界面、判定包字段、调用说明、审计**全部不变**（有逐字段相等的回归测试）。

## 三、架构

```
backend/engine.py                  引擎：接口 + 注册表 + 调度（不含任何具体算法）
backend/models/scorecard_v1.py     现在这套：证据累积 → 分档（原样搬，行为零变化）
backend/models/requirements_v1.py  要件逻辑：any_of / not / 嵌套（法律最需要）
backend/models/formula_v1.py       领域公式：受限表达式算阈值或分值（医疗剂量、精算）
```

引擎负责的三件事：
- **取模型**：`get_model(framework)` —— 读 `framework.model`，缺省 `scorecard_v1`
- **校验**：调用模型的 `validate(framework)`，把错误原样返回给界面（不静默）
- **调度**：按模型声明的步骤执行，产出判定包，并**盖上 model 与 version**

## 四、判定模型接口（契约）

```python
class JudgmentModel(Protocol):
    id: str                      # "scorecard_v1"
    version: str                 # "1"；语义变更必须升版本
    label_zh: str                # 界面上显示的中文名
    label_en: str
    applicable: str              # 适用边界（给用户看的一句话，见第八节）
    not_applicable: list[str]    # 不适用哪些判断

    def input_contract(self) -> dict:
        """这个模型需要框架里有哪些字段、每个字段的形状与校验规则。界面与调用说明据此渲染。"""

    def validate(self, framework: dict) -> list[dict]:
        """返回问题清单（可空）。绝不静默：维度对不上、字段缺失都要在这里说出来。"""

    def judge(self, framework: dict, data: dict) -> dict:
        """纯函数：同样的入参必得同样的判定包；不读写外部状态、不联网、不 eval。"""

    def output_contract(self) -> dict:
        """判定包会包含哪些字段、每个字段的含义与取值范围。"""

    def reasoning(self, package: dict) -> list[dict]:
        """可解释性：给出"第几步、做了什么"的步骤，供判定包与审计使用。"""
```

**注册表**
```python
MODELS: dict[str, JudgmentModel] = {
    "scorecard_v1":    ScorecardV1(),
    "requirements_v1": RequirementsV1(),
    "formula_v1":      FormulaV1(),
}
DEFAULT_MODEL = "scorecard_v1"        # 老切片没有 model 字段时用它 → 行为与今天完全一致
```

**判定包必含（新增两项，其余字段与今天一致）**
```json
{ "model": "scorecard_v1", "model_version": "1",
  "decision": "…", "severity": "…", "score": 0.65, "basis": [...],
  "required_inputs": [...], "missing_inputs": [...], "signals": {...},
  "reasoning_path": [...], "confidence_status": "unverified", "tier": "audit" }
```
> 现有字段**一个都不删**；只**新增** `model` 与 `model_version`。调用方与契约接口因此不受影响。

## 五、三个模型的契约

### 5.1 `scorecard_v1`（＝今天这套，行为零变化）

| 项 | 内容 |
|---|---|
| 输入 | `inputs` `industry_weights` `industry_map` `thresholds` `signals`（含 `dimension`）`combination_rules`（`all_of`）`exception_rules` `signal_priority` `citations` `score_bands` `fallback` |
| 执行 | ① 行业归类 → ② 动态阈值（基准 + 条件调整）→ ③ 逐个信号判命中 → ④ 例外（调阈值 / 降权 / 直接判）→ ⑤ `all_of` 组合规则优先 → ⑥ 否则打分线 → ⑦ 否则兜底 → ⑧ 否则「无明确结论」 |
| 算法 | `score = Σ(命中信号 → 该类别 × 该维度 的权重)`，命中为 1，例外系数真乘进去 |
| 输出 | 今天的判定包（新增 model/version） |
| 适用 | 证据累积型：多信号各自加分 → 落在若干档位（风控评分卡、核保、术前风险分级、合规清单） |
| 不适用 | 顺序分支、要件逻辑（OR/NOT）、领域公式、概率型结论 |
| 已知限制 | 信号内只有 AND；组合规则只有 `all_of`；命中无部分分；一个信号一个维度；权重表只能按行业类别分 |

### 5.2 `requirements_v1`（要件逻辑，法律最需要）

| 项 | 内容 |
|---|---|
| 输入 | `inputs` `requirements`（要件清单）`rules`（每个结论的要件组合）`exceptions`（排除条件）`fallback` |
| 要件组合的表达 | `all_of`（全部满足）、`any_of`（任一满足）、`none_of`（一个都不满足）、`not`（单个反向）、可**嵌套**（如 `all_of: [A, {any_of: [B, C]}, {not: D}]`） |
| 执行 | 逐条规则求值（短路）→ 命中的规则按**声明顺序**取第一条（可显式给 `priority`）→ 都不中走兜底 |
| 输出 | `decision` `severity` `satisfied_requirements` `failed_requirements` `rule_cited` `reasoning_path` `model` `model_version` |
| 适用 | 要件型判断：合同效力、诉讼时效、主体资格、是否符合某项准入条件 |
| 不适用 | 需要"打分排序"的场景（用它表达权重会很别扭 → 那是 `scorecard_v1` 的活） |
| 说明 | 它**不做加权求和**；结论来自"哪条规则的要件成立"，这更贴近法律人的说法 |

### 5.3 `formula_v1`（领域公式，受限表达式）

| 项 | 内容 |
|---|---|
| 输入 | `inputs` `formulas`（具名公式）`bands`（公式结果 → 结论的分档）`rules` `fallback` |
| 表达式能力 | **白名单算子**：`+ - * / ( )`、`min/max/abs/round`、比较、`and/or/not`、字段名、已定义的公式名；**没有**属性访问、下标、函数定义、导入、字符串操作 |
| 求值方式 | 自己写的小型解析器（**不用 `eval`/`exec`**），带深度与长度上限，报错定位到字符位置 |
| 执行 | 逐条公式求值（可互引，需先做环路检测）→ 结果进 `bands` → 命中区间给结论 |
| 输出 | `decision` `severity` `formula_values` `band_cited` `reasoning_path` `model` `model_version` |
| 适用 | 领域里有明确计算式的判断：剂量按体重与肾功能计算、折现现金流、精算现值、成本收益比 |
| 不适用 | 判断本身没有公式、只有经验权重 → 用 `scorecard_v1` |
| 安全 | 纯函数、无 IO、无随机、无时间依赖（时间必须由字段传入）→ 保证可复现 |

## 六、三条硬约束（写进引擎，任何模型都不得违反）

1. **可解释**：必须能产出 `reasoning_path`；不允许"黑箱给个分数"。
2. **无副作用**：不联网、不写盘、不读全局状态、不用 `eval`/`exec`、不用随机与当前时间。
3. **可复现**：`model` + `model_version` + 输入 + 框架 → 必定得到同一判定包；语义变更必须升 `version`。

## 七、界面与对外契约怎么跟上

- **界面**：权重表、打分线等面板**只在 `scorecard_v1` 下显示**；选了别的模型，界面按该模型的 `input_contract()` 渲染它自己的输入面板；切换模型时**先提示"会按新模型重新校验"**，不静默丢内容。
- **调用说明（契约接口）**：新增 `model` 与 `model_version`，并给出该模型的字段清单与"会收到哪些字段"（`output_contract()`）。
- **审计**：判定记录里写入 `model` 与 `model_version`。
- **切换模型**：切片上一个下拉；老切片缺省 `scorecard_v1`；切换只改声明，不改数据。

## 八、适用边界要写给用户看（对应上一个问题的结论）

界面与文档里明确写出：

```
scorecard_v1  适合：证据累积型（多信号加分 → 分档）
              不适合：顺序分支 / 要件组合(OR·NOT) / 领域公式 / 概率结论
requirements_v1 适合：要件型（全部满足、任一满足、排除条件）
formula_v1      适合：有明确计算式的领域判断
```
> 这样用户**一开始就不会选错模型**；而不是让一个算法硬撑所有判断。

## 九、分四步做，每步都能单独验收

| 步 | 做什么 | 验收标准 | 风险 |
|---|---|---|---|
| **第 0 步** | 纯搬家：`engine.py` + `models/scorecard_v1.py`，行为一行不改 | **同一框架 + 同一数据 → 重构前后判定包逐字段相等**（专门的回归测试） | 极低 |
| **第 1 步** | 加 `framework.model` 与 `model_version`；契约接口与界面按模型渲染；审计记录模型 | 老切片行为不变；契约里出现 model 字段；切模型不丢数据 | 低 |
| **第 2 步** | `requirements_v1`（含嵌套与 `not`） | 一组要件型样例（合同效力/诉讼时效）判定正确；排除条件生效 | 中 |
| **第 3 步** | `formula_v1`（受限表达式 + 环路检测 + 位置化报错） | 医疗剂量与 DCF 两个样例；拒绝危险表达式（属性访问、`eval`、超长） | 中高 |

**我建议先只做第 0 步**：它对用户**完全透明**（判定包一模一样），却把"算法焊死在引擎里"这个根问题解掉，后面三个模型都只是加文件。

## 十、需要你确认

1. 判定模型接口（第四节）这样定，可以吗？
2. 三个模型的边界（第五节：评分卡 / 要件 / 公式）这样分，对吗？要不要**先只做前两个**、公式放最后？
3. 第 0 步的验收方式（**判定包逐字段相等**）你认可吗？我按这个做，你能一眼看出"没改行为"。
4. `framework.model` 这个字段名与"缺省 scorecard_v1"的兼容策略，可以吗？
