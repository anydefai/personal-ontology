# 05 · 界面（前端）

## 1. 结构

```
web/index.html    127 行   外壳：侧栏导航（22 个 data-page）、#view 容器、共享弹窗、BUILD 版本标记
web/app.js      2,380 行   全部日常页面渲染 + 路由分发 + api() + 弹窗/提示
web/pro.js      1,832 行   专业侧（场景切片/实例/预演/交付/判定）页面
web/i18n.js     2,113 行   中→英词条表 + 运行时翻译
web/app.css         8 行   只有一条：.nav 可滚动的布局修复；样式几乎全内联
```

没有构建步骤：浏览器直接加载 `web/*`，`index.html` 里用 `?v=<BUILD>` 做缓存击穿。

## 2. 导航（22 项，两组）

```
我的世界
  总览 dashboard  主体 principals  我 profiles  圈 circles  事 commitments
  地 places       财 assets        识 knowledge
规则与能力
  界 boundaries   器 devices       场景切片 scenario-slices
  场景实例 scenario-instances      场景预演 scenario-preview
  对外交付与反馈 delivery           判定记录 decisions
  模型服务 model-service           智能体接入 agent-integration
  服务监控 service-monitor         智能体授权 agent-access
  显示与语言 display-settings      登录与安全 account-security
  需求反馈 feedback
```

## 3. 页面 → 渲染函数（26 个）

| 页面（data-page） | 函数 | 文件 |
|---|---|---|
| dashboard | `renderDashboard` | app.js |
| principals | `renderCollection("principals")` | app.js |
| profiles | `renderProfiles` | app.js |
| circles | `renderCircles` | app.js |
| commitments | `renderCommitments` | app.js |
| places | `renderPlaces` | app.js |
| assets | `renderAssets` | app.js |
| knowledge | `renderKnowledge` | app.js |
| boundaries | `renderBoundaries` | app.js |
| devices | `renderDevices`（内含「数据来源 · 通讯录」与「代理关系」两张卡片） | app.js |
| scenarios | `renderScenarios` | pro.js |
| scenario-slices | `renderProfessionalSlices` | pro.js |
| scenario-instances | `renderScenarioInstances` / `renderProfessionalInstances` | pro.js |
| scenario-preview | `renderScenarioPreview` / `renderProfessionalPreview` | pro.js |
| delivery | `renderDelivery` | pro.js |
| decisions | `renderDecisions`（追加「授权判定」表） | pro.js / app.js |
| model-service | `renderModelService` | app.js |
| agent-integration / agent-access | `renderAgentIntegration` / `renderAgentAccess` | app.js |
| service-monitor | `renderServiceMonitor` | app.js |
| display-settings / account-security | `renderDisplaySettings` / `renderAccountSecurity` | app.js |
| feedback | `renderFeedback` | app.js |

渲染约定：每个函数 `async function renderX(view)`，自取数据（`api(...)` 或 `load(name)`），
把 HTML 写进 `view.innerHTML`，然后绑定事件。

## 4. 共享组件（改界面时优先复用，别新造）

| 组件 | 位置 | 用途 |
|---|---|---|
| `api(path, opts)` | app.js | 统一 fetch：自动带令牌、解析 `detail.message`、401 抛 `AuthRequired` |
| `load(name)` / `cache` | app.js | 集合级缓存，`cache[name]=null` 即失效 |
| `titleBlock(kicker, title, sub)` | app.js | 页面统一标题区 |
| `toast(msg, isError)` | app.js | 轻提示（右下） |
| `confirmModal({title, body, danger, okText, onOk})` | app.js | **所有确认操作必须用它**，禁止原生 `confirm()` |
| `alertModal(msg, title)` | app.js | 禁止原生 `alert()` |
| `#record-dialog` + `#dialog-content` | index.html | 表单弹窗容器（`.modal`） |
| `esc()` / `displayName()` / `relationName()` | app.js | 转义、实体取名 |
| `renderComingSoon(view, name)` | app.js | 未实现页面的占位（**不许放假数据**） |
| `proModeButtons()` | pro.js | 日常/专业模式切换 |

## 5. 交互铁律（来自真实返工）

```
① 不弹原生对话框：confirm/alert 一律换成 confirmModal/alertModal。
   剩余 6 处原生 confirm 属于已知技术债（结构复杂，需人工整块包裹）。
② 列表默认掩码，查看明文要二次确认，且确认后【真的写入记录】再显示（界面文案不得撒谎）。
③ 危险操作必须点明对象（"删除「身份证号」这一项？"），不能只说"确定吗"。
④ 空状态要给出下一步动作（"还没有导入通讯录 → 去器里导入"），而不是空白。
⑤ 卡片内的控件要紧凑：字号 12px、高度 28px、`flex-wrap`，否则会撑破卡片（曾发生）。
```

## 6. i18n 机制

```
i18n.js 是一张 中→英 的扁平词条表；运行时对所有文本节点与属性做替换。
语言优先级：请求头 X-Display-Language（浏览器侧算好） > data/settings.json 的 display_language > zh
后端消息同样按这个头返回（config.display_language(hint)）。
新增界面文案时：中文直接写，然后【必须】在 i18n.js 补一条英文，否则 test_i18n_coverage 会红。
```

## 7. 版本与缓存

```
index.html 里两处标记：BUILD 20261028A（可见）与 ?v=20261028A（资源参数）
发布流程：改代码 → 更新这两处 → 复制到运行目录 → 用户强刷（⌘⇧R）
排查"我改的地方没生效"：先 curl 首页看 BUILD，再 curl /assets/app.js 看是否含新代码。
```

## 8. 前端自测（没有浏览器自动化，靠静态与约定测试）

```
node tests/test_ui_behavior.js        26 项：关键交互约定（无原生 confirm/alert、有弹窗等）
python3 tests/test_frontend_syntax.py 10 项：node --check 全部 js + 关键字符串存在性
```

**改 app.js 的纪律（血泪）**：先写入临时文件 → `node --check` 通过 → 再覆盖真文件。
曾经"先写盘后编译"，把坏代码写进仓库（靠 git checkout 才救回来）。
