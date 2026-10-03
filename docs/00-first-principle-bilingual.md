# 第一性原则：全栈中英双语

> English version: [`00-first-principle-bilingual.en.md`](00-first-principle-bilingual.en.md).

> **本原则优先于其它一切设计取舍。** 任何新增产出，只要缺另一语言版本，就视为**未完成**。

## 1. 原则

系统的**每一个面向用户或维护者的产出**都必须同时存在中文与英文版本，并且在两种语言下
**都是完整、可用、不混杂**的。不只是页面文案，而是：

界面文案、后端消息、数据标签与对象名称、场景分析产出、安装手册、使用手册、
设计文档、变更日志。

## 2. 分层要求与机制

| 层 | 要求 | 机制 | 可执行检查 |
|---|---|---|---|
| **界面文案** | 英文模式下不出现中文字符 | `web/i18n.js` 的 `DICT` + `RULES`（已覆盖五类形态：图标前缀、后缀标记、数值/编号嵌入、英文+中文合并整串、属性） | `tests/test_i18n_coverage.py`（基线不得上升）、`test_i18n_text.py`、`test_i18n_rules.py` |
| **后端消息** | HTTP 错误与提示按请求语言返回 | 消息目录（键 → 中/英），按 `X-Display-Language` 选用 | 待补：`tests/test_messages_bilingual.py` |
| **数据标签 / 对象名称** | 主体、资源类型、动作、字段标签双语 | 元模型成对字段 `*_zh` / `*_en`；读取时按语言取用（`_localize_scene_labels`、`SCOPES_EN`） | `tests/test_label_localization.py` |
| **场景分析产出** | 模型按**分析时**语言产出；已知字段在读取时按当前语言本地化 | 提示词 `{LANG_LABEL}`；读取时 `field_names.default_label(name, language)` | `tests/test_label_localization.py` |
| **文档** | 每份文档都有中英两版 | 同目录兄弟文件 `docs/NN-name.en.md`（现有中文文件**无需改名**）；也接受 `.zh.md`/`.en.md` 成对 | `tests/test_bilingual_coverage.py` |
| **README / 安装手册 / 使用手册** | 中英两版 | `README.en.md` 等兄弟文件（README 已完成） | `tests/test_bilingual_coverage.py` |
| **变更日志** | 每次变更中英双条 | `CHANGELOG.en.md`（**覆盖 2026-10-02 起**；历史条目仅中文并在文件内注明） | `tests/test_bilingual_coverage.py` |

### 例外（明确写出，避免无穷尽）

- **用户自撰内容不翻译**：用户输入的描述、备注、自定义名称按用户所写的语言原样保留。
  系统**生成**的内容必须双语；用户**输入**的内容不强制。
- **代码注释与内部标识符**：属实现细节，不要求双语（但设计文档要求双语）。
- **机器键**（如 `check_in_date`）恒为英文，不翻译——这是既有约定。
- **长文档可分轮翻译，但必须标记**：文件头部写 `BILINGUAL-PARTIAL` 注释说明已完成到哪一节。
  盘点器识别该标记并**仍计入缺口**，避免"文件存在、内容不全"被当作已覆盖。
- **冻结的测试向量与机器数据不翻译**：如 `docs/05` §3.5 的测试向量明文（`测试向量：…`）——
  它是**输入字节**，翻译它会让各实现产出不同密文。此类内容在文档中必须照抄并注明原因。
- **工具产出的清单/索引不翻译**（如 `docs/i18n-pending.md`）：它们是扫描产物、服务于维护者，
  中英各一份反而失去意义。豁免清单见 `tests/test_bilingual_coverage.py` 的 `EXEMPT_DOCS`。

## 3. 实施纪律（血的教训）

1. **验收对象是"服务器实际给出的文件"，不是工作区文件。** 两者之间隔着同步与浏览器缓存两层。
   前端改动的验收必须包含：`curl http://127.0.0.1:8765/assets/... | grep <特征>`。
2. **每次改前端必须升资源版本号**（`web/index.html` 里的 `?v=`）。
   否则浏览器继续用旧文件，表现为"改了看不见"。
3. **不要用自己写的解析器校验**。词典/规则用 Node 真实求值（`window.PO_I18N_EN`），
   不要用括号计数之类的土办法——它不理解正则字符类，会给出错误结论（本项目中已发生两次）。
4. **幂等检查要针对具体产物**。用通用子串做"是否已存在"判断会导致写入被跳过而脚本仍报成功。
5. **定位本地化问题先查语言解析链**：`config.display_language` 的优先级错了，会让所有下游本地化一起失效——逐条补词条全是治症。
6. **报告中文残留在"整行"层面**：DOM 里常把片段合并成一个文本节点，
   按关键词加词条往往对不上整串。

## 4. 现状盘点（2026-10-02）

| 层 | 状态 |
|---|---|
| 界面文案 | 🟡 机制完备，历史遗漏已补 200+ 条；仍有插值/长句待补（见 `docs/i18n-pending.md`） |
| 数据标签 / 对象名称 | 🟢 已实现（顶层与 segmentation 两处偏好、字段标签、授权范围标签） |
| 场景分析产出 | 🟢 模型按分析语言产出 + 读取时本地化 |
| 后端消息 | 🟢 **完成**：`backend/messages.py` + 异常处理器解析，66 处全部转换 |
| 设计文档（docs/03–09） | 🔴 **未做**：全部仅中文 |
| README / 安装 / 使用手册 | 🔴 **未做**：仅中文 |
| CHANGELOG | 🔴 **未做**：仅中文 |
| 覆盖率防线 | 🟢 `tests/test_bilingual_coverage.py` 统一盘点全栈双语缺口（基线 82，**只允许下降**） |

## 5. 推进顺序（建议）

1. **后端消息目录**（用户最容易撞到：错误提示全是中文）
2. **README 与安装手册双语**（对新用户门槛最高）
3. **设计文档双语**（`docs/03–09` → `.zh.md` / `.en.md` 配对）
4. **CHANGELOG 双语**
5. 补齐各层覆盖率检查，使"缺另一语言"直接导致测试失败

## 6. 与其它文档的关系

- 本文是**第一性原则**，优先于具体设计取舍。
- 各分层机制的实现细节见 `docs/09-scenario-analysis-schema.md`（数据契约）与 `web/i18n.js` 顶部注释（界面翻译机制）。


## 7. 当前缺口（`tests/test_bilingual_coverage.py` 实测）

```
后端消息（含中文的 detail/message）: 0 处 ✓ 已全部转换（66 处）
设计文档缺英文版:                   7 份（docs/06、07、09 已完成）
README 缺英文版:                    0 份 ✓
CHANGELOG 缺英文版:                 1 份
────────────────────────────────────────
总缺口                               8
```

**每次改动后运行该测试**：缺口上升即失败。逐轮把 82 降到 0，本原则即达成。


## 8. 已解决：语言优先级缺陷曾让整个本地化层失效（2026-10-02 第 3 轮）

**症状**：`X-Display-Language: en` 的请求仍返回中文消息；数据标签、授权范围标签的
按语言本地化也全部无效。

**真正根因不在下游，而在这一行**：

```python
# backend/config.py（错误）
def display_language(hint=None):
    return stored_language() or normalize_language(hint) or "zh"
    #      ↑ 落盘的旧设置永远优先 → 请求头被完全忽略
```

前端已在浏览器侧解析好优先级（用户设置或系统语言），并把它放在 `X-Display-Language`
头里；后端却又用落盘设置覆盖了它 → **凡是按请求头本地化的地方一律取到旧语言**。

**修正**：请求头优先，落盘设置只作为无头时的回退。

```python
return normalize_language(hint) or stored_language() or "zh"
```

**验收**（不再只看工作区，直接打后端接口）：

```
POST /v1/login  X-Display-Language: zh → {"detail":"请输入登录密码。"}
POST /v1/login  X-Display-Language: en → {"detail":"Enter the login password."}   ✓
```

**教训（加入第 3 节纪律）**：定位"本地化不生效"要先查**语言解析链**，再查具体词条。
下游逐条修补可能全都在治症——本次前两轮即如此，真正问题是上游一行优先级。

### 期间两次失败尝试（保留供参考）

1. 在 `@app.middleware("http")`（Starlette `BaseHTTPMiddleware`）里设 `contextvars`
   → 端点内不可见（中间件在独立任务里执行端点）。
2. 改为 FastAPI 全局依赖 `dependencies=[Depends(...)]` → 同样不可见。

最终采用的方案：**让 `detail` 携带消息键，由异常处理器按 `request` 解析语言**
（`messages.detail()` + `@app.exception_handler(HTTPException)`）——不必给端点加参数，
且对公开端点有效。


## 9. 盘点器新增指标：契约提醒消息（2026-10-02 第 9 轮发现）

写 `docs/09` 英文版时发现：`backend/analysis_contract.py` 的 `contract_notes[].message`
（**会显示给用户**，见切片页「N 处契约提醒」徽章）目前**只有中文**，约 13 条。
它此前不在任何盘点范围内，因此属于**新计入的债**，不是回退。

**已解决（第 10 轮）**：`note()` 改为只携带**消息键（即 code）+ 参数**，中文/英文文本放回
`backend/messages.py`；`note()` 在创建时写入中文 `message`（兼容未本地化的读取路径），
`_localize_scene_labels()` 在读取时按显示语言替换 `message`。实测英文含参数渲染正确。
