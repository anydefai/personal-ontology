/* The document sample for method two is used from polishPanels, which lives outside the IIFE, so it must
 * live outside it as well; it only builds strings.
 */
var DOC_SECTIONS = [
    ["不同行业的侧重",
     "# 这一节是【你自己】的行业侧重表：行业 → 类别 → 各维度权重。少了它，分数恒为 0（因为取不到权重）。\n" +
     "# 维度名必须与「我观察什么」里 ｜ 后面的名字逐字一致（下面例子里是 法律 / 交易 / 合规 / 估值 / 经营）。\n" +
     "类别 高法律风险 ｜ 行业 房地产、制造业\n" +
     "权重 高法律风险 ｜ 法律 0.4 · 交易 0.2 · 合规 0.2 · 估值 0.15 · 经营 0.05\n" +
     "类别 科技 ｜ 行业 新能源、互联网\n" +
     "权重 科技 ｜ 法律 0.1 · 交易 0.2 · 合规 0.2 · 估值 0.4 · 经营 0.1"],
    ["判断的基准线",
     "基准 1.2\n不动产权属=有瑕疵 → ×1.3\n对外担保=有未披露 → +0.1\n交易结构=股权收购 → +0.1\n交易结构=资产收购 → -0.1"],
    ["我观察什么",
     "权属瑕疵 = 不动产权属 等于 有瑕疵 ｜ 法律 ｜ 1\n诉讼未决 = 未决诉讼金额占比 大于 5 ｜ 法律 ｜ 0.5\n担保未披露 = 对外担保 等于 有未披露 ｜ 法律 ｜ 1\n对赌缺失 = 业绩对赌条款 等于 无 ｜ 交易 ｜ 1\n数据合规风险 = 数据合规结论 等于 不合规 ｜ 合规 ｜ 1\n估值偏高 = 市盈率 大于 行业平均市盈率 × 基准线 ｜ 估值 ｜ 1\n客户集中度高 = 客户集中度 大于 50 ｜ 经营 ｜ 0.5"],
    ["几个观察点一起出现时",
     "权属瑕疵 且 对赌缺失 → 不建议推进（高）\n担保未披露 且 (数据合规风险 或 估值偏高) → 需补充尽调（中）\n非 对赌缺失 且 权属瑕疵 → 需重新谈价（中）\n诉讼未决 且 权属瑕疵 且 担保未披露 → 风险极高，建议终止（极高）\n估值偏高 且 客户集中度高 → 估值偏高但可控（中）"],
    ["例外情况",
     "权属瑕疵 且 担保未披露 → 法律权重 ×0.5\n诉讼未决 且 数据合规风险 → 基准线 ×1.2\n标的为国资背景=是 → 直接判 需国资审批"],
    ["哪个更重要",
     "担保未披露 > 权属瑕疵 > 诉讼未决 > 对赌缺失 > 估值偏高"],
    ["我的依据",
     "# 一行一条：依据名，或 依据名 → 信号1 且 信号2（后者要这些信号全部命中才附上）\n# 法律判断没有依据就不可信 —— 下面两行是占位，请换成你真实的依据\n《民法典》物权编 → 权属瑕疵\n《公司法》股权转让相关规则 → 对赌缺失 且 权属瑕疵"],
    ["打分线",
     "# 打分线只决定「多少分 → 什么结论」；打分公式是内建的，不用写在这里：\n#   分数 = Σ（命中的信号 → 该类别 × 该维度 的权重 × 该信号的命中分值）\n#   命中分值写在「我观察什么」的第三段（不写＝1）；例外的「权重 ×0.5」在这里生效\n#   取权重的路径是【行业 → 类别 → 各维度权重】，所以下面必须有一项「行业」字段（已给），并在「不同行业的侧重」里做两件事：\n#     ① 加一个类别（例如「高法律风险」），类别名你自己取；② 把该类别映射到行业（写 房地产），再给各维度填权重\n#     例：类别「高法律风险」→ 行业 房地产 ｜ 法律 0.4 · 交易 0.2 · 合规 0.2 · 估值 0.15 · 经营 0.05\n#     维度名必须与「我观察什么」里 ｜ 后面的名字逐字一致（法律 / 交易 / 合规 / 估值 / 经营），写错按 0 分算\n# 下面两个数是占位 —— 请按你的专业判断改成你的数\n打分 0.5 以上 → 法律风险高（高）\n打分 0.3 以下 → 法律风险低（低）\n其余 → 法律风险中（中）"],
    ["需要调用方提交的信息",
     "行业 ｜ 选项 ｜ 房地产、制造业、新能源、互联网、医药、金融\n不动产权属 ｜ 选项 ｜ 清晰、有瑕疵\n未决诉讼金额占比 ｜ 数字\n对外担保 ｜ 选项 ｜ 无、有已披露、有未披露\n业绩对赌条款 ｜ 选项 ｜ 有、无\n数据合规结论 ｜ 选项 ｜ 合规、基本合规、不合规\n市盈率 ｜ 数字\n行业平均市盈率 ｜ 数字\n客户集中度 ｜ 数字\n交易结构 ｜ 选项 ｜ 股权收购、资产收购\n标的为国资背景 ｜ 选项 ｜ 是、否"],
    ["对外调用的边界",
     "金额上限 1000000000\n允许用途 并购尽调、投资决策\n不得转售"],
    ["对外交付时附上的说明",
     "强在哪：把法律要件（权属、诉讼、担保、对赌、数据合规）与估值（市盈率对行业基准）分开判，再合成一个结论；基准线会随尽调发现与交易结构动态调整\n档位：audit\n资历：执业 15 年，并购与公司业务\n有效期：1 天"],
    ["计费（演示）",
     "每次 1200 CNY"]
  ];

function docSample() {
return DOC_SECTIONS.map(function (x) { return "【" + x[0] + "】\n" + x[1]; }).join("\n\n");
}

/* The formula and band panels are used by the renderer below, which lives OUTSIDE the IIFE, so they must
 * live outside it too; they only build strings.
 */
// ── 公式与分档（领域公式模型用）──
// 这两块只有 formula_v1 需要；界面按模型只显示该模型要的输入（见 MODEL_PANEL_FIELDS）。
function formulasPanel(f) {
var rows = (f.formulas && typeof f.formulas === "object") ? f.formulas : {};
var lines = Object.keys(rows).map(function (k) { return k + " = " + rows[k]; }).join("\n");
var bands = (f.bands || f.score_bands || []);
var bandLines = (Array.isArray(bands) ? bands : []).map(function (b) {
  var lo = (b.min === undefined || b.min === null) ? "" : b.min;
  var hi = (b.max === undefined || b.max === null) ? "" : b.max;
  return (lo === "" ? "" : lo + " ") + (hi === "" ? "以上" : "到 " + hi) + " → " + (b.conclusion || "") +
    (b.severity ? "（" + b.severity + "）" : "");
}).join("\n");
return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
  '<div class="panel-title"><span>公式</span></div>' +
  '<div class="panel-caption" style="margin:6px 0 4px">一行一条：名称 = 表达式。可用字段名、其它公式名、' +
    '+ - * / 括号、min/max/abs/round；不能用属性访问或下标（引擎自己解析，不用 eval）。</div>' +
  '<textarea class="input mono" rows="4" style="width:100%" data-formulas placeholder="剂量 = round(体重 * 肾功能系数, 1)">' +
    esc(lines) + "</textarea>" +
  '<div class="panel-title" style="margin-top:12px"><span>分档</span></div>' +
  '<div class="panel-caption" style="margin:6px 0 4px">一行一条：结果区间 → 结论（严重度）。' +
    '例：20 到 80 → 常规剂量（中）／80 以上 → 高剂量（高）</div>' +
  '<textarea class="input mono" rows="4" style="width:100%" data-bands placeholder="20 到 80 → 常规剂量（中）">' +
    esc(bandLines) + "</textarea></section>";
}

/* The contract text helpers below are used by polishPanels, which lives OUTSIDE the IIFE further down,
 * so they must live outside it too; they only rely on the global esc().
 */
  // The contract comes from the API so there is one source of truth; these two turn it into text a person
  // can read or paste into a delivery note.
function contractLines(c) {
  var out = [];
  out.push("调用说明 · " + (c.title || c.slice_id || ""));
  out.push("调用方式：" + ((c.how_to_call || {}).method || "POST") + " " + ((c.how_to_call || {}).path || ""));
  out.push("");
  out.push("需要提供的值（全部必填，少一项不会有结论）：");
  (c.fields || []).forEach(function (f, i) {
    var bits = [f.name, "类型：" + (f.type || "string")];
    if (f.unit) bits.push("单位：" + f.unit);
    if (f.options) bits.push("可选值：" + (f.options || []).join("/"));
    if (f.example) bits.push("示例：" + f.example);
    if (f.note) bits.push(f.note);
    out.push("  " + (i + 1) + ". " + bits.join(" · "));
  });
  out.push("");
  out.push("每次调用还要说明：调用方、本次用途" + (c.max_amount ? "、金额（上限 " + c.max_amount + "）" : "") +
           (c.no_resale_required ? "，并承诺不得转售" : "") + "。");
  if ((c.allowed_purposes || []).length) out.push("允许的用途：" + c.allowed_purposes.join("、"));
  out.push("缺少必填项时：只返回「信息不足，无法判断」并列出缺哪几项。");
  out.push("");
  out.push("你会收到：" + (c.you_will_receive || []).join("、"));
  var ac = c.access || {};
  if (ac.authorization_required) {
    out.push("");
    out.push("注意：这份说明不等于授权 —— " + (ac.contract_vs_authorization || ""));
    out.push("  由谁决定：" + (ac.who_decides || "") + "；" + (ac.how || ""));
    out.push("  身份怎么验：" + (ac.how_identity_is_proven || ""));
  }
  var bill = c.billing || {};
  if (bill.unit_price) out.push("计费（演示）：每次 " + bill.unit_price + " " + (bill.currency || "CNY"));
  return out;
}

function contractHtml(c) {
  return '<div class="panel-caption" style="margin-top:8px">调用说明（可直接发给调用方）：</div>' +
    '<pre class="pro-copy">' + esc(contractLines(c).join("\n")) + "</pre>";
}


/* Visible error net.
 *
 * A synchronous throw inside a click handler (as opposed to a rejected promise) is NOT caught by
 * unhandledrejection, so the interface just looks dead with no message at all. This catches those too,
 * which is what makes a silent "nothing happens" observable.
 */
window.poErrorNet = true;
window.addEventListener("error", function (e) {
  try {
    var where = "";
    if (e && e.filename) { where = " @ " + String(e.filename).split("/").pop() + ":" + (e.lineno || "?"); }
    alert("页面出错：" + ((e && (e.message || (e.error && e.error.message))) || "未知错误") + where);
  } catch (x) {}
});

/* Global helper, deliberately OUTSIDE the IIFE below.
 *
 * The renderers appended near the end of this file sit outside the IIFE (it closes around line 732),
 * so anything they call must be global. This bit me once: "hasFramework is not defined" on the
 * scenario-slice page, because the IIFE-scoped copy was invisible out there.
 */
function poHasFramework(fw) {
  if (!fw || typeof fw !== "object") return false;
  var lists = ["inputs", "signals", "combination_rules", "exception_rules", "signal_priority"];
  for (var i = 0; i < lists.length; i++) { if ((fw[lists[i]] || []).length) return true; }
  if (Object.keys(fw.industry_weights || {}).length) return true;
  if (Object.keys(fw.industry_map || {}).length) return true;
  if (((fw.thresholds || {}).adjustments || []).length) return true;
  return false;
}

/* Professional track: the skill-framework authoring interface (steps 1-4).
 *
 * Relationship to app.js: this file only renders the "professional mode / scenario slice" page,
 * called through window.POPro.renderSlices(view); everything else (evaluation, backtesting)
 * reuses the helpers already defined in app.js (api / load / esc / titleBlock / cache / render).
 *
 * Wording rule: the labels speak the expert's language, not the data schema's. Types are described
 * by what they hold ("a number", "pick one of a few options"), every control carries one example,
 * and anything schema-ish stays out of sight.
 */
(function () {
  "use strict";

  var state = null;          // the framework being edited

  // Query helper, hoisted to the top of the IIFE: collect() used it before its own local
  // declaration, so var hoisting made it undefined and every add-row button threw
  // "q is not a function".
  var q = function (a) { return document.querySelectorAll(a); };

  // Published for handlers outside the IIFE: clear the editor state and redraw.
  // Needed after parsing or duplicating, otherwise the editor keeps the old empty state.
  // The redraw is delegated to the existing hook, which is assigned by the time this runs.
  window.poReloadSlice = function () {
    // What this replaces called window.poRefreshSlice, which no code ever assigned, so refreshing
    // silently did nothing and step three kept showing the old empty state.
    // render() is the page renderer (declared outside this IIFE); typeof keeps this safe either way.
    if (window.poReloading) { return; }
    window.poReloading = true;
    try {
      cache["scenario-slices"] = null;   // the review button clears the cache too; without this step three re-renders from stale data
      state = null;
      if (typeof render === "function") { render(); }
      else if (typeof window.poRefreshSlice === "function") { window.poRefreshSlice(); }
    } finally { window.poReloading = false; }
  };
  var defId = null;          // current scenario-definition id
  var sliceId = null;        // the slice currently selected (personal asset)
  var lastDraft = "";        // description used for the last draft

  // Expert wording to internal type: only the left-hand wording ever reaches the screen.
  var TYPES = [
    ["string", "一句描述或名称", "例如「标的行业」「管辖地」这样的一句话"],
    ["number", "一个数字", "例如 45、8 亿；只填数字，单位自己统一"],
    ["enum", "从几个选项里选一个", "例如「高 / 中 / 低」，把可选值写出来"],
    ["bool", "是 / 否", "例如「是否取得控制权」，只有两种情况"],
    ["multi", "多项选择", "例如「适用行业」，可以同时选好几个"],
    ["money", "金额", "例如「交易金额」；8 亿写成 800000000，单位自己统一"]
  ];
  var TYPE_LABEL = {};
  var TYPE_HINT = {};
  TYPES.forEach(function (t) { TYPE_LABEL[t[0]] = t[1]; TYPE_HINT[t[0]] = t[2]; });
  var INT_TYPE = { string: "string", number: "number", enum: "enum", bool: "bool", multi: "multi", money: "number" };

  var OPS = [["gt", "大于"], ["gte", "不小于"], ["lt", "小于"], ["lte", "不大于"],
             ["eq", "等于"], ["neq", "不等于"], ["in", "属于"], ["not_in", "不属于"], ["contains", "包含"]];
  var OP_LABEL = {}; OPS.forEach(function (o) { OP_LABEL[o[0]] = o[1]; });

  // NOTE: kept on window on purpose - the renderers near the end of this file live OUTSIDE the
  // IIFE, so an IIFE-scoped variable would be undefined there (this broke the page once).

  var EX_KINDS = [["reduce_weight", "降低某个维度的重要性"], ["adjust_threshold", "调整基准线"],
                  ["force_conclusion", "直接给出结论"]];

  // A framework counts as configured only when some part has content (all-empty means not configured yet).
  function hasFramework(fw) {
    if (!fw || typeof fw !== "object") return false;
    var lists = ["inputs", "signals", "combination_rules", "exception_rules", "signal_priority"];
    for (var i = 0; i < lists.length; i++) { if ((fw[lists[i]] || []).length) return true; }
    if (Object.keys(fw.industry_weights || {}).length) return true;
    if (Object.keys(fw.industry_map || {}).length) return true;
    if (((fw.thresholds || {}).adjustments || []).length) return true;
    return false;
  }


  function clone(o) { return JSON.parse(JSON.stringify(o || {})); }

  function emptyFramework() {
    return { framework_version: "V1", inputs: [], industry_map: {}, industry_weights: {},
             thresholds: { base: 1.0, adjustments: [] }, signals: [], combination_rules: [],
             exception_rules: [], signal_priority: [], adjustment_log: [] };
  }

  function ensureShape(fw) {
    var f = clone(fw || {});
    if (!Array.isArray(f.inputs)) f.inputs = [];
    if (!f.industry_map || typeof f.industry_map !== "object") f.industry_map = {};
    if (!f.industry_weights || typeof f.industry_weights !== "object") f.industry_weights = {};
    if (!f.thresholds || typeof f.thresholds !== "object") f.thresholds = { base: 1.0, adjustments: [] };
    if (!Array.isArray(f.thresholds.adjustments)) f.thresholds.adjustments = [];
    ["signals", "combination_rules", "exception_rules", "signal_priority", "adjustment_log"].forEach(function (k) {
      if (!Array.isArray(f[k])) f[k] = [];
    });
    if (typeof f.thresholds.base !== "number") f.thresholds.base = 1.0;
    return f;
  }

  function row(html) { return '<div class="pro-row">' + html + "</div>"; }
  function hint(text) { return '<div class="panel-caption" style="margin:0 0 8px">' + text + "</div>"; }
  function input(value, attrs) {
    return '<input class="input" ' + (attrs || "") + ' value="' + esc(value == null ? "" : String(value)) + '">';
  }
  function del(what) { return '<button class="button" data-del="' + what + '">删除</button>'; }

  // -- Delivery note: what a caller sees about who made this judgment --
  function deliveryPanel(d) {
    d = d || {};
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>对外交付时附上的说明</span></div>' +
      hint('调用方拿到判定包时会看到下面这些。它们不参与判断，只说明这是谁的专业判断') +
      row('<span class="field-label" style="min-width:120px">我的专业洞察</span>' +
        input(d.insight, 'data-dlv-insight style="min-width:420px" placeholder="这套判断强在哪，例如：普通判断只看市盈率，本判断还看行业周期与监管环境"')) +
      row('<span class="field-label" style="min-width:120px">我的资历</span>' +
        input(d.owner_credentials, 'data-dlv-cred style="min-width:420px" placeholder="例如：执业 15 年，并购领域，主导过 80 多起并购案"')) +
      row('<span class="field-label" style="min-width:120px">默认交付层级</span>' +
        '<select class="select" data-dlv-tier>' +
          [["audit","审计层（完整判定包）"],["professional","专业层（结论+证据+推理路径）"],
           ["standard","标准层（结论+证据）"],["basic","基础层（只有结论）"]].map(function (x) {
            return '<option value="' + x[0] + '"' + ((d.default_tier || "audit") === x[0] ? " selected" : "") + ">" + x[1] + "</option>";
          }).join("") + "</select>" +
        '<span class="muted">调用方没有单独指定时，按这一层交付</span>') +
      row('<span class="field-label" style="min-width:120px">有效期，单位天</span>' +
        input(d.valid_days == null ? 1 : d.valid_days, 'data-dlv-days type="number" step="1" placeholder="1"') +
        '<span class="muted">判定包会带上到期时间；签名需要密钥对，尚未实现</span>') +
      '</section>';
      row('<span class="field-label" style="min-width:120px">计费方式</span>' +
        '<select class="select" data-price-mode>' +
          [["per_call", "按次"], ["monthly", "包月"]].map(function (x) {
            return '<option value="' + x[0] + '"' + (((d.pricing || {}).mode || "per_call") === x[0] ? " selected" : "") + ">" + x[1] + "</option>";
          }).join("") + "</select>" +
        '<span class="muted">按次或包月；具体价格由你设定</span>') +
      ["basic", "standard", "professional", "audit"].map(function (t) {
        var label = { basic: "基础层", standard: "标准层", professional: "专业层", audit: "审计层" }[t];
        var price = ((d.pricing || {}).tiers || {})[t];
        return row('<span class="field-label" style="min-width:120px">' + label + '</span>' +
          input(price, 'data-price-tier="' + t + '" type="number" step="any" placeholder="单价，留空表示未定价"') +
          '<span class="muted">元</span>');
      }).join("")
  }

  // -- 0 / Boundaries for outside calls (layer one: may it be called at all) --
  function boundariesPanel(b) {
    b = b || {};
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>对外调用的边界</span></div>' +
      hint('这一组管的是"别人能不能调用你的判断"，与上面的判断内容无关。三项都必须填，缺一项就不会放行。') +
      row('<span class="field-label" style="min-width:96px">金额上限</span>' +
        input(b.max_amount, 'data-bnd-amount type="number" step="any" placeholder="例如 1000000000（10 亿）"') +
        '<span class="muted">超过上限不会拒绝，而是先请你本人确认</span>') +
      row('<span class="field-label" style="min-width:96px">允许用途</span>' +
        input((b.allowed_scenarios || []).join("、"), 'data-bnd-scenarios placeholder="用、分开，例如：并购尽调、投资决策"') +
        '<span class="muted">不在这个范围内的用途一律拒绝</span>') +
      row('<span class="field-label" style="min-width:96px">保密要求</span>' +
        input(b.confidentiality, 'data-bnd-conf placeholder="例如：调用方不得转售结论"') +
        '<span class="muted">调用方每次都必须承诺不得转售，否则拒绝</span>') +
      '</section>';
  }

  // ── 1 · 我要知道的信息 ──
  function inputsPanel(f) {
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>我要知道的信息</span></div>' +
      hint('每次做判断之前都要先问清楚的信息，一条一行。') +
      hint('调用这条判断的人必须提供下面这些值；少任何一项，判定会返回「信息不足，无法判断」。') +
      f.inputs.map(function (i, n) {
        var t = (i.type === "number" && i.__money) ? "money" : (i.type || "string");
        return row('<div style="min-width:150px">' + input(i.name, 'data-in-name="' + n + '" placeholder="叫什么，例如：标的行业"') + "</div>" +
          '<div style="min-width:220px">' +
        '<span class="badge" data-in-type-label="' + n + '">' + esc(TYPE_LABEL[(i.type || "string")] || i.type || "一句描述或名称") + '</span> ' +
        '<a href="#" data-in-type-edit="' + n + '" style="font-size:12px">改</a>' +
        '<select class="select" data-in-type="' + n + '" style="display:none;margin-top:4px">' +
            TYPES.map(function (x) { return '<option value="' + x[0] + '"' + (t === x[0] ? " selected" : "") + ">" + x[1] + "</option>"; }).join("") +
          "</select></div>" +
          '<div style="min-width:240px">' +
            ((t === "enum" || t === "multi")
              ? input((i.values || []).join("、"), 'data-in-values="' + n + '" placeholder="可选项，用、分开，例如：高、中、低"')
              : '<span class="muted">' + TYPE_HINT[t] + "</span>") +
          "</div>" + del("input:" + n));
      }).join("") +
      '<div style="margin-top:8px"><button class="button" data-add="input">＋ 加一条信息</button>' +
      '<span class="panel-caption" style="margin-left:8px">不确定类型没关系：上面那张草稿通常已经替你填好了，核对即可。</span></div></section>';
  }

  // ── 2 · 不同行业的侧重 ──
  function weightsPanel(f) {
    var cats = Object.keys(f.industry_weights);
      // Always offer one editable row: entering weights must not depend on the add button working.
      if (!cats.length) cats = ["新类别1"];
    var dims = {};
    // Dimensions come from the signals, which is where they are authored; the weights table only adds
    // extra ones. Deriving them from the table alone made an empty table claim there were none.
    (f.signals || []).forEach(function (sg) { if (sg && sg.dimension) dims[sg.dimension] = 1; });
    cats.forEach(function (c) { Object.keys(f.industry_weights[c] || {}).forEach(function (d) { dims[d] = 1; }); });
    var dimList = Object.keys(dims);
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>不同行业的侧重</span></div>' +
      hint('同样是并购，科技公司更看技术、传统制造更看财务。这里一行一个【类别】（行业组，名字你自己取，例如「高法律风险」）；调用方提交的是【行业】（例如 房地产），系统按下面的映射把行业归到你建的类别上，再用该类别的权重打分。') +
      (cats.length ? '<div class="pro-grid" style="grid-template-columns:1.2fr repeat(' + Math.max(dimList.length, 1) + ',1fr) 0.6fr">' +
        "<div>类别（行业组）</div>" + (dimList.length ? dimList.map(function (d) { return "<div>" + esc(d) + "</div>"; }).join("") : "<div>侧重</div>") + "<div></div>" +
        cats.map(function (c, n) {
          return "<div>" + input(c, 'data-w-cat="' + n + '"') + "</div>" +
            (dimList.length ? dimList.map(function (d) {
              return "<div>" + input((f.industry_weights[c] || {})[d], 'data-w-val="' + n + ":" + esc(d) + '"') + "</div>";
            }).join("") : "<div>" + input("", 'data-w-val="' + n + ':weight"') + "</div>") +
            "<div>" + del("weights:" + n) + "</div>";
        }).join("") + "</div>" : hint("还没有类别。")) +
        (dimList.length ? "" : '<div class="panel-caption" style="margin-top:8px">这张表按「维度」分列，而你的信号还没标维度：请到上面【我观察什么】，在信号那一行的末尾加上 ｜ 维度名（例如 ｜ 财务），保存后回到这里就会出现对应的列。</div>') +
      '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">' +
      '<div style="margin-top:12px">' +
        '<details style="margin-top:10px"><summary class="panel-caption" style="cursor:pointer">可选：只有当调用方提交的行业写法与你建的类别不一致时才需要填这里</summary><div style="margin-top:6px">' +
        hint('一行一条：数据里的写法 → 上表里的类别。写法一致就不用填。') +
        '<textarea class="input mono" data-im-lines rows="3" style="width:100%" placeholder="数据里的写法 → 表里的类别">' +
        Object.keys(f.industry_map || {}).map(function (k) { return esc(k) + " → " + esc(f.industry_map[k]); }).join("\n") +
        '</textarea></div></details>' +
      '<button class="button" data-add="weight-cat">＋ 加一个类别（行业组）</button>' +
      '<button class="button" data-add="weight-dim">＋ 加一个侧重维度</button>' +
      '<span class="panel-caption" style="margin:0">数值加起来是 1 就行；没把握就先平均。</span></div></section>';
  }

  // ── 3 · 判断的基准线 ──
  function thresholdsPanel(f) {
    var th = f.thresholds || {};
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>判断的基准线</span></div>' +
      hint('先定一条基准线，再说明什么情况下把它调高或调低。例如：基准 1.3，行业处于上升期就上调 0.15；右边也可以写 ×1.2 表示乘法。') +
      row('<span class="field-label" style="min-width:96px">基准线</span>' +
        input(th.base, 'data-th-base type="number" step="any" placeholder="例如 1.3"') +
        '<span class="muted">这就是你心里那条线，通常是一个倍数</span>') +
      (th.adjustments || []).map(function (a, n) {
        var cond = a.condition || {}; var k = Object.keys(cond)[0] || "";
        return row(input(k, 'data-th-field="' + n + '" placeholder="什么情况下：字段名"') +
          input(cond[k], 'data-th-value="' + n + '" placeholder="这个字段是什么值"') +
          input(a.delta, 'data-th-delta="' + n + '" placeholder="调高或调低多少，例如 0.15" type="number" step="any"') +
          input(a.reason, 'data-th-reason="' + n + '" placeholder="为什么这么调（会记进调整记录）"') +
          del("threshold:" + n));
      }).join("") +
      '<button class="button" data-add="threshold">＋ 加一条调整</button></section>';
  }

  // ── 4 · 我观察什么 ──
  function signalsPanel(f) {
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>我观察什么</span></div>' +
      hint('一条观察点就是一句判断，例如「市盈率高于行业平均乘以基准线」。可以引用上面算出的基准线，不用自己算。') +
      (f.signals || []).map(function (s, n) {
        var when = s.when || {}; var field = Object.keys(when)[0] || "";
        var spec = when[field] || {};
        var ref = (typeof spec.value === "object" && spec.value !== null) ? String(spec.value.ref || "") : "";
        var useThreshold = (typeof spec.value === "object" && spec.value !== null && spec.value.times === "threshold");
        var plain = useThreshold ? "" : (typeof spec.value === "object" ? JSON.stringify(spec.value) : spec.value);
        return row('<div style="min-width:160px">' + input(s.name, 'data-sig-name="' + n + '" placeholder="观察点叫什么，例如：估值偏高信号"') + "</div>" +
          '<div style="min-width:150px">' + input(field, 'data-sig-field="' + n + '" placeholder="看哪个字段"') + "</div>" +
          '<div style="min-width:110px"><select class="select" data-sig-op="' + n + '">' +
            OPS.map(function (o) { return '<option value="' + o[0] + '"' + (spec.op === o[0] ? " selected" : "") + ">" + o[1] + "</option>"; }).join("") +
          "</select></div>" +
          '<div style="min-width:170px">' + input(plain, 'data-sig-value="' + n + '" placeholder="比什么值"') + "</div>" +
          // 命中分值：留空即 1（与今天一致）；0–1 之间表示「这条只是部分证据」。
          '<div style="min-width:104px">' + input(s.score_value == null || s.score_value === 1 ? "" : s.score_value, 'data-sig-score="' + n + '" placeholder="分值(默认1)"') + "</div>" +
          '<label class="pro-check" style="min-width:200px"><input type="checkbox" data-sig-ref-use="' + n + '"' + (useThreshold ? " checked" : "") + '>× 基准线</label>' +
          '<div style="min-width:150px">' + input(ref, 'data-sig-ref="' + n + '" placeholder="若勾选：乘以哪个字段"') + "</div>" +
          del("signal:" + n));
      }).join("") +
      '<button class="button" data-add="signal">＋ 加一个观察点</button></section>';
  }

  // ── 5 · 几个观察点一起出现时 ──
  function rulesPanel(f) {
    var names = f.signals.map(function (s) { return s.name; });
    function checks(selected, attr, n) {
      return names.map(function (nm) {
        var on = (selected || []).indexOf(nm) >= 0;
        return '<label class="pro-check"><input type="checkbox" ' + attr + '="' + n + '" value="' + esc(nm) + '"' + (on ? " checked" : "") + ">" + esc(nm) + "</label>";
      }).join("") || '<span class="muted">先在上面加观察点</span>';
    }
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>几个观察点一起出现时</span></div>' +
      hint('勾选必须同时成立的观察点，再写下你的结论和严重程度。例如三个不利信号叠加，就判估值偏高，严重程度高。') +
      (f.combination_rules || []).map(function (r, n) {
        return row('<div class="pro-checks" style="min-width:260px">' + checks(r.all_of, "data-cr-sig", n) + "</div>" +
          input(r.conclusion, 'data-cr-conc="' + n + '" placeholder="我的结论"') +
          '<select class="select" data-cr-sev="' + n + '">' +
            ["低", "中", "高", "极高"].map(function (s) { return '<option' + (r.severity === s ? " selected" : "") + ">" + s + "</option>"; }).join("") +
          "</select>" + del("rule:" + n));
      }).join("") +
      '<button class="button" data-add="rule">＋ 加一条组合判断</button></section>';
  }

  // ── 6 · 例外情况 ──
  function exceptionsPanel(f) {
    var names = f.signals.map(function (s) { return s.name; });
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>例外情况</span></div>' +
      hint('专业判断里最难的部分：什么情况下，上面那套常规判断要被改写。只填你选的那一类需要的。') +
      (f.exception_rules || []).map(function (r, n) {
        var cond = r.condition || {}; var ov = r.override || {};
        var sigs = cond.all_signals || []; var kind = ov.kind || "adjust_threshold";
        var extra = "";
        if (kind === "reduce_weight") {
          extra = input(ov.target, 'data-ex-target="' + n + '" placeholder="降低哪个维度的重要性"') +
                  input(ov.factor, 'data-ex-factor="' + n + '" placeholder="降多少：0.5 表示降一半"');
        } else if (kind === "adjust_threshold") {
          extra = input(ov.factor, 'data-ex-factor="' + n + '" placeholder="基准线乘多少：1.2 表示上浮 20%"');
        } else {
          extra = input(ov.conclusion, 'data-ex-conc="' + n + '" placeholder="直接给出的结论"');
        }
        return row('<div class="pro-checks" style="min-width:240px">' + names.map(function (nm) {
            return '<label class="pro-check"><input type="checkbox" data-ex-sig="' + n + '" value="' + esc(nm) + '"' + (sigs.indexOf(nm) >= 0 ? " checked" : "") + ">" + esc(nm) + "</label>";
          }).join("") + "</div>" +
          '<select class="select" data-ex-kind="' + n + '">' +
            EX_KINDS.map(function (k) { return '<option value="' + k[0] + '"' + (kind === k[0] ? " selected" : "") + ">" + k[1] + "</option>"; }).join("") +
          "</select>" + extra +
          input(r.reason, 'data-ex-reason="' + n + '" placeholder="为什么（会记进调整记录）"') + del("exception:" + n));
      }).join("") +
      '<button class="button" data-add="exception">＋ 加一条例外</button></section>';
  }

  // ── 7 · 哪个观察点更重要 + 调整记录 ──
  function tailPanels(f) {
    var names = f.signals.map(function (s) { return s.name; });
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>哪个观察点更重要</span></div>' +
      hint('数字越小越重要（1 最重要）。几条判断同时成立时，先听更重要的那个。') +
      (f.signal_priority || []).map(function (p, n) {
        return row('<select class="select" data-pr-sig="' + n + '">' + names.map(function (nm) {
            return '<option' + (p.signal === nm ? " selected" : "") + ">" + esc(nm) + "</option>";
          }).join("") + "</select>" + input(p.priority, 'data-pr-val="' + n + '" type="number" placeholder="重要程度，1 最重要"') + del("priority:" + n));
      }).join("") +
      '<button class="button" data-add="priority">＋ 排一下重要性</button></section>' +
      '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>我的调整记录</span></div>' +
      hint('每改一处就记下理由。这是你的经验沉淀，也是调用方判断这套框架可信度的依据。') +
      (f.adjustment_log || []).map(function (a, n) {
        return row(input(a.step, 'data-log-step="' + n + '" placeholder="我改了什么"') +
          input(a.reason, 'data-log-reason="' + n + '" placeholder="为什么这么改"') + del("log:" + n));
      }).join("") +
      (f.adjustment_log || []).length ? "" : hint("还没有记录。") +
      '<button class="button" data-add="log">＋ 记一条调整</button></section>';
  }

  // 判定模型目录：界面与调用说明都从这里取（模型不写在引擎里）。
  async function loadModelCatalog() {
    try { var d = await api("/v1/judgment-models"); return (d && d.models) || []; }
    catch (e) { return []; }
  }

  // Bind the add/remove/type-change buttons. Extracted into a function so it can be published and
  // exercised by the probe (tests/probe_add_buttons.js) instead of only by eye.
  function bindRowButtons(view) {
      view.querySelectorAll("[data-add]").forEach(function (b) {
        b.onclick = function () {
          var kind = b.dataset.add;
          // Capture everything the user has typed before appending. collect() reads the DOM, so it must run
          // first; if it fails we report and abort rather than silently discarding their input.
          try {
            state = collect();
          } catch (e) {
            alert("读取当前输入出错，已中止本次操作（你的输入没有被丢弃）：" + (e && e.message ? e.message : e));
            return;
          }
          if (kind === "input") state.inputs.push({ name: "", type: "string" });
          else if (kind === "weight-cat") {
            var dims = {};
            Object.keys(state.industry_weights).forEach(function (c) {
              Object.keys(state.industry_weights[c] || {}).forEach(function (d) { dims[d] = 1; });
            });
            var blank = {};
            Object.keys(dims).forEach(function (d) { blank[d] = 0; });
            if (!Object.keys(blank).length) blank["侧重"] = 0;
            state.industry_weights["新行业" + (Object.keys(state.industry_weights).length + 1)] = blank;
          }
          else if (kind === "weight-dim") Object.keys(state.industry_weights).forEach(function (c) {
            var w = state.industry_weights[c]; w["维度" + (Object.keys(w).length + 1)] = 0;
          });
          else if (kind === "threshold") state.thresholds.adjustments.push({ condition: {}, delta: 0, reason: "" });
          else if (kind === "signal") state.signals.push({ name: "", when: {} });
          else if (kind === "rule") state.combination_rules.push({ all_of: [], conclusion: "", severity: "中" });
          else if (kind === "exception") state.exception_rules.push({ condition: { all_signals: [] }, override: { kind: "adjust_threshold" }, reason: "" });
          else if (kind === "priority") state.signal_priority.push({ signal: state.signals[0] ? state.signals[0].name : "", priority: state.signal_priority.length + 1 });
          else if (kind === "citation") state.citations = (state.citations || []).concat([{ text: "", signals: [] }]);
          else if (kind === "log") state.adjustment_log.push({ step: "", reason: "" });
          render();
        };
      });
      view.querySelectorAll("[data-del]").forEach(function (b) {
        b.onclick = function () {
          try { state = collect(); } catch (e) {}
          var parts = b.dataset.del.split(":"), what = parts[0], n = parseInt(parts[1], 10);
          if (what === "input") state.inputs.splice(n, 1);
          else if (what === "weights") delete state.industry_weights[Object.keys(state.industry_weights)[n]];
          else if (what === "threshold") state.thresholds.adjustments.splice(n, 1);
          else if (what === "signal") state.signals.splice(n, 1);
          else if (what === "rule") state.combination_rules.splice(n, 1);
          else if (what === "exception") state.exception_rules.splice(n, 1);
          else if (what === "priority") state.signal_priority.splice(n, 1);
          else if (what === "citation") state.citations.splice(n, 1);
          else if (what === "log") state.adjustment_log.splice(n, 1);
          render();
        };
      });
  }
  window.poBindRowButtons = bindRowButtons;   // published: handlers outside the IIFE, and the probe

  async function renderSlices(view) {
    var models = await loadModelCatalog();
    var pickModel = window.poJudgmentModel || "scorecard_v1";
    var pickedModel = (models || []).filter(function (x) { return x.id === pickModel; })[0] || (models || [])[0];
    var pickedContract = (pickedModel && pickedModel.input_contract) ? pickedModel.input_contract : null;
    window.poModelFields = (pickedContract && pickedContract.fields) ? Object.keys(pickedContract.fields) : null;
    var defs = await load("scenario-definitions");
    if (!defId || !defs.some(function (d) { return d.id === defId; })) defId = defs[0] ? defs[0].id : null;
    // Idempotent migration: move the personal asset still sitting on a shared scenario definition onto my slice.
    try {
      var mv = await api("/v1/scenario-slices/migrate-from-definitions", { method: "POST", body: "{}" });
      if (mv && mv.count) { cache["scenario-slices"] = null; cache["scenario-definitions"] = null; defs = await load("scenario-definitions"); }
    } catch (e) { /* a failed migration must not block the page */ }
    var def = defs.filter(function (d) { return d.id === defId; })[0] || null;
    var allSlices = await load("scenario-slices");
    var mine = allSlices.filter(function (x) {
      return (x.scenario_profile || {}).kind === "professional" && x.scenario_definition_id === defId;
    });
    var principals = [];
    try { principals = (await api("/v1/principals")) || []; } catch (e) { principals = []; }
    if (!Array.isArray(principals)) principals = principals.items || [];
    var approvedAgents = [];
    var approvedAgents = [], agentsErr = "";
    try { approvedAgents = ((await api("/v1/agents")) || {}).approved || []; }
    catch (e) { approvedAgents = []; agentsErr = (e && (e.message || (e.detail && e.detail.message))) || "读取失败"; }
    window.poAgentsError = agentsErr;   // 读失败别伪装成"没有程序"
    window.poPrincipals = principals;          // 发布给 IIFE 之外/别的渲染函数用（避免跨作用域引用）
    window.poApprovedAgents = approvedAgents;
    var pend = null;
    try { pend = sessionStorage.getItem("poProPickSlice"); } catch (e) { pend = null; }
    if (pend) {
      try { sessionStorage.removeItem("poProPickSlice"); } catch (e) {}
      if (mine.some(function (x) { return x.id === pend; })) sliceId = pend;
    }
    if (!sliceId || !mine.some(function (x) { return x.id === sliceId; })) sliceId = mine[0] ? mine[0].id : null;
    window.poCurrentSliceId = sliceId || "";   // published for handlers that live outside the IIFE
    // 未归属切片：所属场景已被删除（或从未归属）—— 不该消失，应当能捞回来
    var defIds = defs.map(function (d) { return d.id; });
    var orphans = allSlices.filter(function (x) {
      return (x.scenario_profile || {}).kind === "professional"
        && (!x.scenario_definition_id || defIds.indexOf(x.scenario_definition_id) < 0);
    });
    var slice = mine.filter(function (x) { return x.id === sliceId; })[0] || null;
    if (!state || state.__slice !== sliceId) {
      // Only reload from the server when switching slices. Overwriting unconditionally wiped anything the
      // add/remove buttons had just put into state, which made those buttons look dead.
      if (!state || state.__slice !== sliceId) {
        state = ensureShape(slice && slice.framework ? slice.framework : emptyFramework());
        state.__slice = sliceId;
      }
      state.__slice = sliceId;
    }
    var opts = defs.map(function (d) {
      return '<option value="' + esc(d.id) + '"' + (d.id === defId ? " selected" : "") + ">" +
        esc(fieldLabel(d, "display_name_zh", "display_name_en")) + "</option>";
    }).join("");
    var nameOfSlice = function (x) { return (x.analysis && x.analysis.title) || x.original_text || x.id; };
    var sliceOpts = mine.map(function (x) {
      var st = x.framework
        ? ("已有框架" + (x.confidence_status && x.confidence_status !== "unverified" ? " · 置信度 " + x.confidence_status : ""))
        : "尚未配置框架";
      return '<option value="' + esc(x.id) + '"' + (x.id === sliceId ? " selected" : "") + ">" +
        esc((x.analysis && x.analysis.title) || x.original_text || x.id) + "（" + st + "）</option>";
    }).join("");
    view.innerHTML = proModeButtons() +
      titleBlock("SKILL FRAMEWORK", "技能框架", "先用一段话讲清你的判断方式，让模型起草；再逐条改成你自己的说法。改的过程就是这套框架的价值所在。") +
      '<section class="panel" style="padding:16px;margin-bottom:12px">' +
        '<div class="panel-title"><span>第一步 · 先选场景，再选我的切片</span></div>' +
        '<div class="panel-caption" style="margin:6px 0 10px">场景是<strong>可共享的模板</strong>，不含你的判断；切片是<strong>你的个人判断资产</strong>，同一个场景可以建多条（例如互联网版、制造业版）</div>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center">' +
          '<span class="field-label" style="min-width:56px">场景</span>' +
          '<select class="select" id="pro-def" style="max-width:300px">' + (opts || '<option value="">还没有专业场景</option>') + "</select>" +
          '<input class="input" id="pro-new-name" style="max-width:220px" placeholder="新场景叫什么">' +
          '<button class="button" id="pro-new">＋ 新建场景</button>' +
          (def && !def.is_builtin ? '<button class="button" id="pro-rename">改名</button><button class="button" id="pro-del-def">删除场景</button>' : "") +
        "</div>" +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding-top:10px;border-top:1px solid #e6e9ef">' +
          '<span class="field-label" style="min-width:56px">我的切片</span>' +
          (mine.length ? '<select class="select" id="pro-slice" style="max-width:360px">' + sliceOpts + "</select>"
                       : '<span class="badge">还没有我的切片</span>') +
          '<input class="input" id="pro-new-slice" style="max-width:200px" placeholder="新切片叫什么，例如：互联网版">' +
          '<button class="button primary" id="pro-add-slice">＋ 新建我的切片</button>' +
          '<button class="button" id="pro-dup-slice">⧉ 另存为新切片</button>' +
        "</div>" +
        (slice
          ? '<div class="panel-caption" style="margin:10px 0 0">当前切片：<strong>' +
            esc((slice.analysis && slice.analysis.title) || slice.original_text || slice.id) + "</strong> · 置信度 " +
            esc(slice.confidence_status || "未验证") + " · 保存与起草都写在这条切片上</div>"
          : '<div class="panel-caption" style="margin:10px 0 0">先新建一条「我的切片」，框架保存在切片上</div>') +
        "</section>" +
      sliceTable(mine, sliceId, nameOfSlice) +
      orphanPanel(orphans, defs, nameOfSlice) +
      (function (m) {
        // 拿不到模型目录时（例如会话失效）不能把整块藏掉 —— 用内置的默认模型信息兜住，
        // 并明确提示「目录没读到」，让用户知道该重新登录，而不是以为功能没了。
        var offline = false;
        // 内置清单：模型是代码，不经部署不会变，所以这份兜底是准的。
        // 目录接口拿不到时（例如会话失效）也让你看到全部模型，而不是只剩一个。
        var FALLBACK_MODELS = [
          { id: "scorecard_v1", version: "1", label_zh: "评分卡（证据累积）",
            applicable: "证据累积型：把若干可观察信号按重要性加权，累积成总分再落到档位（风控评分卡、核保、术前风险分级、合规清单）。",
            not_applicable: ["需要顺序分支的判断", "要件组合（任一满足／排除条件／嵌套）", "领域公式（剂量、折现现金流）", "概率型结论"] },
          { id: "requirements_v1", version: "1", label_zh: "要件逻辑（成立就用它）",
            applicable: "要件型：每条结论对应一个要件表达式，成立即用该结论（合同效力、诉讼时效、主体资格、准入条件）。",
            not_applicable: ["需要按重要性加权排序的判断", "领域公式型", "概率型结论"] },
          { id: "formula_v1", version: "1", label_zh: "领域公式（核心是一个计算式）",
            applicable: "有明确计算式的判断：剂量（体重×肾功能）、折现现金流、精算现值、成本收益比。",
            not_applicable: ["只有经验权重的判断", "只有要件是否成立的判断", "概率型结论"] }
        ];
        if (!m || !(models && models.length)) {
          offline = true;
          models = FALLBACK_MODELS;
          m = models[0];
        }
        // 当前模型：切片自己带的 model 优先（老切片没有此字段 → 默认模型）
        if (!window.poJudgmentModel) { window.poJudgmentModel = (state.model || m.id); }
// 目录拿不到或为空时，下拉里也要有兜底的默认模型 —— 不能给出一个空的选择框。
var opts = (models && models.length ? models : [m]).map(function (x) {
  return '<option value="' + esc(x.id) + '"' + (x.id === window.poJudgmentModel ? " selected" : "") + ">" + esc(x.label_zh || x.id) + "</option>";
}).join("");
        // 每个模型的说明存到全局：切换处理在另一个作用域里（拿不到这里的 models），
        // 曾经因此报过 Uncaught ReferenceError: models is not defined。
        window.poModelTitle = {};
        (models && models.length ? models : [m]).forEach(function (x) {
          window.poModelTitle[x.id] = "判定模型 · " + (x.label_zh || x.id) + " v" + (x.version || "1");
        });
        window.poModelDesc = {};
        (models && models.length ? models : [m]).forEach(function (x) {
          var li = (x.not_applicable || []).map(function (y) { return "<li>" + esc(y) + "</li>"; }).join("");
          window.poModelDesc[x.id] = '<div class="panel-caption"><strong>适合：</strong>' + esc(x.applicable || "—") + "</div>" +
            (li ? '<div class="panel-caption" style="margin-top:4px"><strong>不适合：</strong><ul style="margin:4px 0 0 18px">' + li + "</ul></div>" : "");
        });
        var na = (m.not_applicable || []).map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("");
        return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
          '<div class="panel-title"><span id="pro-model-title">判定模型 · ' + esc(m.label_zh || m.id) + " v" + esc(m.version || "1") + "</span></div>" +
          '<div class="panel-caption" style="margin:6px 0 8px">这条切片的结论由哪个模型算出。模型不写在引擎里，' +
          (offline ? '<div class="panel-caption" style="color:#d9534f;margin:0 0 6px">模型清单一共三个，已内置显示（登录后还能读到每个模型的完整说明）。</div>' : "") +
          "每个模型自带适用边界；调用说明与判定记录里都会记下它用了哪个模型、哪个版本。</div>" +
          '<div style="margin:6px 0 8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">' +
          '<span class="field-label" style="min-width:56px">判定模型</span>' +
          '<select class="select" id="pro-model" style="max-width:340px">' + opts + "</select>" +
          '<span class="panel-caption" id="pro-model-note" style="margin:0">切到别的模型会按新模型重新校验；已填内容不会丢。</span>' +
          "</div>" +
          '<div id="pro-model-desc">' +
            '<div class="panel-caption"><strong>适合：</strong>' + esc(m.applicable || "—") + "</div>" +
            (na ? '<div class="panel-caption" style="margin-top:4px"><strong>不适合：</strong><ul style="margin:4px 0 0 18px">' + na + "</ul></div>" : "") +
          "</div>" +
          "</section>";
      })(models[0]) +
      '<section class="panel" style="padding:16px;margin-bottom:12px">' +
        '<div class="panel-title" id="pro-step2"><span>第二步 · 创建切片模型（三种方式，选一种）</span></div>' +
        '<div class="panel-caption" style="margin:6px 0 10px">三种方式改的是同一份框架，选一种即可，随时可以换。</div>' +
        '<div class="panel-title" style="margin-top:8px"><span>方式一 · 模型起草框架</span></div><div class="panel-caption" style="margin:2px 0 6px">用平时说话的方式讲你的判断，模型起草后你再到下面逐条核对</div><textarea class="input" id="pro-desc" rows="4" style="width:100%;margin-top:10px" placeholder="用平时说话的方式讲就行，例如：我判断并购估值会先分行业，不同行业看重的点不一样……"></textarea>' +
        '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
          '<button class="button primary" id="pro-gen">让模型起草框架</button>' +
          '' +
          '<span class="panel-caption" style="margin:0" id="pro-hint">下面各部分可以先不管，等草稿出来再逐条核对着改。</span>' +
        "</div></section>" +
      docImportPanel() +
      lineImportPanel() +
      '<div class="panel-title" id="pro-step3" style="margin:14px 0 8px"><span>第三步 · 核对与微调</span></div>' +
        '<div id="pro-editor">' +
        boundariesPanel((slice && slice.boundaries) || {}) +
        deliveryPanel(slice || {}) +
        inputsPanel(state) + weightsPanel(state) + thresholdsPanel(state) + signalsPanel(state) +
        rulesPanel(state) + exceptionsPanel(state) + citationsPanel(state) +
        scoreBandsPanel(state) + formulasPanel(state) + billingPanel(state) + tailPanels(state) +
      "</div>";
    bind(view);
    polishPanels(view);
    // Override the handlers bound earlier: saving and drafting write to my slice.
    view.querySelectorAll("[data-confirm-slice]").forEach(function (b) {
      b.onclick = function () { window.poEnableFor = b.dataset.confirmSlice; render(); };
    });
    view.querySelectorAll("[data-in-type-edit]").forEach(function (a) {
      a.onclick = function (ev) {
        ev.preventDefault();
        var n = a.dataset.inTypeEdit;
        var sel = view.querySelector('[data-in-type="' + n + '"]');
        var lab = view.querySelector('[data-in-type-label="' + n + '"]');
        var collapse = function () {
          if (sel) sel.style.display = "none";
          if (lab) lab.style.display = "";
          a.textContent = "改";
        };
        if (sel && sel.style.display !== "none") { collapse(); return; }   // second click collapses it
        if (sel) { sel.style.display = ""; sel.focus(); }
        if (lab) lab.style.display = "none";
        a.textContent = "收起";
        if (sel) sel.onchange = function () {
          if (lab) lab.textContent = TYPE_LABEL[sel.value] || sel.value;
          collapse();
          var vals = view.querySelector('[data-in-values="' + n + '"]');
          if (vals) vals.style.display = (sel.value === "enum" || sel.value === "multi") ? "" : "none";
        };
        // Clicking elsewhere also collapses it (the delay lets a click inside the dropdown land first).
        if (sel) sel.onblur = function () { setTimeout(collapse, 200); };
      };
    });
    view.querySelectorAll("[data-cancel-enable]").forEach(function (b) {
      b.onclick = function () { window.poEnableFor = null; render(); };
    });
    view.querySelectorAll("[data-do-enable]").forEach(function (b) {
      b.onclick = async function () {
        var g = view.querySelector("[data-enable-grantor]"), a = view.querySelector("[data-enable-agent]");
        if (!g || !g.value) { alert("请先选择授权方。"); return; }
        if (!a || !a.value) { alert("请先选择被授权方（已批准的本机程序）。"); return; }
        var agent = (approvedAgents || []).filter(function (x) { return x.key === a.value; })[0] || {};
        var agentName = String(agent.name || a.value);
        // The program needs a matching principal for the rule to reference (a mirror; its name must equal the program's).
        var mirrorId = null;
        try {
          var all = (await api("/v1/principals")) || [];
          if (!Array.isArray(all)) all = all.items || [];
          var hit = all.filter(function (x) { return String(x.display_name_zh || "") === agentName; })[0];
          if (hit) { mirrorId = hit.id; }
          else {
            var made = await api("/v1/principals", { method: "POST",
              body: JSON.stringify({ display_name_zh: agentName, display_name_en: agentName, principal_type: "agent" }) });   // a program is an agent, not a person
            mirrorId = (made || {}).id;
          }
        } catch (err) {
          alert("为该程序建立对应主体失败：" + (err && err.message ? err.message : err));
          return;
        }
        if (!mirrorId) { alert("没有拿到该程序的对应主体，已中止。"); return; }
        try {
          var out = await api("/v1/scenario-slices/" + encodeURIComponent(window.poEnableFor) + "/enable",
            { method: "POST", body: JSON.stringify({ grantor_id: g.value, grantee_id: mirrorId }) });
          window.poEnableFor = null; cache["scenario-slices"] = null; render();
          alert("已启用，并授权给「" + agentName + "」\n授权规则：" + ((out && out.authorization_id) || "已生成"));
        } catch (err) {
          alert("启用失败：" + (err && err.message ? err.message : err));
        }
      };
    });
    // Re-render on type or exception-kind change so only the needed inputs show.
    view.querySelectorAll("[data-in-type]").forEach(function (s) { s.onchange = function () { state = collect(); render(); }; });
    view.querySelectorAll("[data-ex-kind]").forEach(function (s) { s.onchange = function () { state = collect(); render(); }; });
    view.querySelectorAll("[data-save-framework]").forEach(function (b) {
      b.onclick = async function () {
        if (!sliceId) { alert("请先点上面的「＋ 新建我的切片」建一条切片，框架保存在切片上。"); return; }
        if (slice && slice.status === "confirmed" &&
            !confirm("这条切片已启用，改动会影响对外调用。确定保存吗？")) return;
        // Anything still sitting in the line boxes gets imported and saved here, so nothing is lost silently.
        var lineTexts = {};
          var importedFw = null;   // framework returned by a successful line import (panels are stale)
        view.querySelectorAll("[data-line-part]").forEach(function (ta) {
          if (ta.value.trim()) lineTexts[ta.dataset.linePart] = ta.value;
        });
        if (Object.keys(lineTexts).length) {
          var imp = await api("/v1/scenario-slices/" + encodeURIComponent(sliceId) + "/import-lines",
            { method: "POST", body: JSON.stringify({ texts: lineTexts, save: true }) });
          if (imp && imp.framework) {
            importedFw = ensureShape(imp.framework);
              state = importedFw; state.__slice = sliceId;
            var bad = [];
            Object.keys(imp.report || {}).forEach(function (kk) {
              (imp.report[kk].errors || []).forEach(function (e) { bad.push("第 " + e.line + " 行：" + e.reason); });
            });
            if (bad.length) alert("有几行没看懂，已跳过：\n" + bad.join("\n"));
          }
        }

        if (!sliceId) { alert("请先新建一条「我的切片」，框架保存在切片上。"); return; }
          // Use the imported result when there is one: collect() would read the not-yet-re-rendered
          // panels and overwrite the framework that was just saved with an empty one.
          var f = importedFw || collect();
          // Never silently drop input: if the industry-mapping box contains lines we could not read, say so.
          var imBox = view.querySelector("[data-im-lines]");
          if (imBox && (imBox.value || "").trim()) {
            var badIm = [], looksTable = false;
            (imBox.value || "").split("\n").forEach(function (ln) {
              var t = ln.trim(); if (!t || t.charAt(0) === "#") return;
              if (t.indexOf("|") >= 0) looksTable = true;
              if (t.split(/→|->/).length < 2) badIm.push(t);
            });
            if (looksTable) {
              alert("「我的行业归类」里像是粘贴了一张表格。\n权重请填在上面的「不同行业的侧重」表格里；\n这里只填对应关系，例如：行业名 → 类别名");
            } else if (badIm.length) {
              alert("「我的行业归类」里有 " + badIm.length + " 行没看懂（缺少 →）：\n" +
                    badIm.slice(0, 5).join("\n") + "\n正确的写法：行业名 → 类别名");
            }
          }
        var bndRaw = ((view.querySelector("[data-bnd-amount]") || {}).value || "").trim();
        var bnd = {
          max_amount: bndRaw === "" ? null : Number(bndRaw),
          allowed_scenarios: ((view.querySelector("[data-bnd-scenarios]") || {}).value || "")
            .split(/[、,，]/).map(function (x) { return x.trim(); }).filter(Boolean),
          confidentiality: ((view.querySelector("[data-bnd-conf]") || {}).value || "").trim(),
          default_tier: ((view.querySelector("[data-dlv-tier]") || {}).value || "audit"),
          pricing: (function () {
            var tiers = {};
            view.querySelectorAll("[data-price-tier]").forEach(function (el) {
              var v = parseFloat(el.value); if (!isNaN(v)) tiers[el.dataset.priceTier] = v;
            });
            return { mode: ((view.querySelector("[data-price-mode]") || {}).value || "per_call"), tiers: tiers };
          })()
        };
        var dvDays = ((view.querySelector("[data-dlv-days]") || {}).value || "").trim();
        await api("/v1/scenario-slices/" + encodeURIComponent(sliceId), { method: "PATCH", body: JSON.stringify({
          framework: f, boundaries: bnd,
          insight: ((view.querySelector("[data-dlv-insight]") || {}).value || "").trim(),
          owner_credentials: ((view.querySelector("[data-dlv-cred]") || {}).value || "").trim(),
          valid_days: dvDays === "" ? 1 : Number(dvDays) }) });
        cache["scenario-slices"] = null; state = null; render();
      };
    });
    var genBtn = view.querySelector("#pro-gen");
    if (genBtn) genBtn.onclick = async function () {
      if (!sliceId) { var h = view.querySelector("#pro-hint"); if (h) h.textContent = "请先新建一条「我的切片」"; return; }
      var desc = (view.querySelector("#pro-desc") || {}).value || "";
      var h2 = view.querySelector("#pro-hint"); if (h2) h2.textContent = "正在让模型起草…（大约十几秒）";
      var out = await api("/v1/scenario-slices/" + encodeURIComponent(sliceId) + "/draft", { method: "POST", body: JSON.stringify({ description: desc }) });
      if (out && out.framework) { state = ensureShape(out.framework); state.__slice = sliceId; render(); }
      else if (h2) { h2.textContent = "起草失败：" + ((out && (out.detail || out.error)) || "请检查模型服务"); }
    };
    view.querySelectorAll("[data-pick-slice]").forEach(function (b) {
      b.onclick = function () {
        sliceId = b.dataset.pickSlice;
        render();
        // Jump to step 3 so the panels the user came to edit are in view.
        requestAnimationFrame(function () {
          var ed = document.getElementById("pro-step3");
          if (ed && ed.scrollIntoView) ed.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      };
    });
    view.querySelectorAll("[data-drop-slice]").forEach(function (b) {
      b.onclick = async function () {
        if (!confirm("删除这条切片？它的框架、定价与调整记录都会一并删除。")) return;
        await api("/v1/scenario-slices/" + encodeURIComponent(b.dataset.dropSlice), { method: "DELETE" });
        cache["scenario-slices"] = null;
        if (sliceId === b.dataset.dropSlice) { sliceId = null; state = null; }
        render();
      };
    });
  // NOTE: [data-confirm-slice] is bound ONCE above (it must open the grantee picker first).
  // A second binding here used to overwrite it and PATCH status directly, so the picker never appeared.
    view.querySelectorAll("[data-unconfirm-slice]").forEach(function (b) {
      b.onclick = async function () {
        await api("/v1/scenario-slices/" + encodeURIComponent(b.dataset.unconfirmSlice),
          { method: "PATCH", body: JSON.stringify({ status: "analyzed" }) });
        cache["scenario-slices"] = null; render();
      };
    });
    view.querySelectorAll("[data-orphan-attach]").forEach(function (b) {
      b.onclick = async function () {
        var sid = b.dataset.orphanAttach;
        var target = (view.querySelector('[data-orphan-target="' + sid + '"]') || {}).value;
        if (!target) { alert("请先选择要挂到哪个场景。"); return; }
        await api("/v1/scenario-slices/" + encodeURIComponent(sid), { method: "PATCH",
          body: JSON.stringify({ scenario_definition_id: target }) });
        cache["scenario-slices"] = null; render();
      };
    });
    view.querySelectorAll("[data-orphan-del]").forEach(function (b) {
      b.onclick = async function () {
        if (!confirm("删除这条未归属切片？它的框架与定价会一并删除。")) return;
        await api("/v1/scenario-slices/" + encodeURIComponent(b.dataset.orphanDel), { method: "DELETE" });
        cache["scenario-slices"] = null; render();
      };
    });

    var doImport = async function (save) {
      var h = view.querySelector("#line-report");
      if (!sliceId) { alert("请先新建或选择一条「我的切片」，框架保存在切片上。"); return; }
      var texts = {};
      view.querySelectorAll("[data-line-part]").forEach(function (ta) {
        if (ta.value.trim()) texts[ta.dataset.linePart] = ta.value;
      });
      if (!Object.keys(texts).length) { var h0 = view.querySelector("#line-report"); if (h0) h0.textContent = "先在上面任意一个框里写几行。"; return; }
      var out = null;
      try {
        out = await api("/v1/scenario-slices/" + encodeURIComponent(sliceId) + "/import-lines",
          { method: "POST", body: JSON.stringify({ texts: texts, save: !!save }) });
      } catch (err) {
        if (h) h.textContent = "导入失败：" + (err && err.message ? err.message : err);
        alert("导入失败：" + (err && err.message ? err.message : err));
        return;
      }
      h = view.querySelector("#line-report");
      if (out && out.framework) {
        state = ensureShape(out.framework); state.__slice = sliceId;
        var bad = [];
        Object.keys(out.report || {}).forEach(function (k) {
          (out.report[k].errors || []).forEach(function (e) { bad.push("第 " + e.line + " 行：" + e.reason); });
        });
        if (save) { cache["scenario-slices"] = null; render(); if (bad.length) alert("已保存，但有几行没看懂：\n" + bad.join("\n")); return; }
        render();
        var h2 = view.querySelector("#line-report");
        if (h2) h2.textContent = bad.length ? ("已导入，但有 " + bad.length + " 行没看懂：" + bad.join("；")) : "已导入，下面面板里可以看到";
      } else if (h) { h.textContent = "导入失败：" + ((out && (out.detail || out.error)) || "请检查内容"); }
    };

    var sliceSel = view.querySelector("#pro-slice");
    if (sliceSel) sliceSel.onchange = function () { sliceId = sliceSel.value; state = null; render(); };
    var addSlice = view.querySelector("#pro-add-slice");
    if (addSlice) addSlice.onclick = async function () {
      if (!defId) { alert("请先新建或选择一个场景（切片必须挂在某个场景下）。"); return; }
      var name = ((view.querySelector("#pro-new-slice") || {}).value || "").trim() || "我的切片";
      var out = await api("/v1/scenario-slices", { method: "POST", body: JSON.stringify({
        original_text: name, status: "analyzed", scenario_definition_id: defId,
        scenario_profile: { kind: "professional" }, analysis: { title: name },
        updated_at: new Date().toISOString() }) });
      if (out && out.id) { cache["scenario-slices"] = null; sliceId = out.id; state = null; render(); }
      else alert("新建切片失败：" + ((out && (out.detail || out.error)) || "请稍后重试"));
    };
        var dupSlice = view.querySelector("#pro-dup-slice");
        if (dupSlice) dupSlice.onclick = async function () {
          if (!sliceId) { alert("先在上面选中一条我的切片，再另存为。"); return; }
          var okDup = confirm("把当前切片另存为一条新切片？\n\n会复制：判定模型与全部参数（权重、阈值、信号、规则、公式）、对外边界、交付、计费。\n不会复制：授权规则、判定记录。\n副本是草稿且未验证，需要你重新确认启用。");
          if (!okDup) { return; }
          var out = await api("/v1/scenario-slices/" + encodeURIComponent(sliceId) + "/duplicate", { method: "POST", body: "{}" });
          var made = out && (out.scenario || out);
          if (made && made.id) { cache["scenario-slices"] = null; sliceId = made.id; state = null; render(); }
          else alert("另存为失败：" + ((out && (out.detail || out.error)) || "请稍后重试"));
        };
  }
  function collect() {
    var f = ensureShape({ framework_version: state.framework_version, industry_map: clone(state.industry_map) });
    // Fields that have no panel inputs (they come from the line boxes) must be carried over,
    // otherwise ensureShape blanks them out and every save silently discards them.
    // 声明这条切片用哪个判定模型（模型不写在引擎里；缺省即评分卡）。
    f.model = window.poJudgmentModel || "scorecard_v1";

    // 领域公式模型：公式（名称 = 表达式）与分档（区间 → 结论）各一行一条
    var fTa = document.querySelector("[data-formulas]");
    if (fTa) {
      var fmap = {};
      (fTa.value || "").split("\n").forEach(function (line) {
        var t = line.trim(); if (!t || t.charAt(0) === "#") { return; }
        var i = t.indexOf("=");
        if (i <= 0) { throw new Error("公式要写成「名称 = 表达式」：" + t); }
        fmap[t.slice(0, i).trim()] = t.slice(i + 1).trim();
      });
      if (Object.keys(fmap).length) { f.formulas = fmap; } else { delete f.formulas; }
    }
    var bTa = document.querySelector("[data-bands]");
    if (bTa) {
      var list = [];
      (bTa.value || "").split("\n").forEach(function (line) {
        var t = line.trim(); if (!t || t.charAt(0) === "#") { return; }
        var arrow = t.indexOf("→");
        if (arrow < 0) { throw new Error("分档要写成「区间 → 结论」：" + t); }
        var left = t.slice(0, arrow).trim(), right = t.slice(arrow + 1).trim();
        var sev = "中", m2 = right.match(/[（(](低|中|高|极高)[）)]\s*$/);
        if (m2) { sev = m2[1]; right = right.slice(0, m2.index).trim(); }
        var band = { conclusion: right, severity: sev };
        var mm = left.match(/^(\d+(?:\.\d+)?)\s*(?:到|-|~)\s*(\d+(?:\.\d+)?)$/);
        if (mm) { band.min = parseFloat(mm[1]); band.max = parseFloat(mm[2]); }
        else {
          var m3 = left.match(/^(\d+(?:\.\d+)?)\s*以上$/);
          if (m3) { band.min = parseFloat(m3[1]); }
          else {
            var m4 = left.match(/^(\d+(?:\.\d+)?)\s*以下$/);
            if (m4) { band.max = parseFloat(m4[1]); }
            else { throw new Error("分档区间看不懂（写 20 到 80 或 80 以上 或 20 以下）：" + left); }
          }
        }
        list.push(band);
      });
      if (list.length) { f.bands = list; } else { delete f.bands; }
    }
    ["citations", "score_bands", "fallback", "source", "billing"].forEach(function (key) {
      var kept = (state && state[key] !== undefined) ? state[key] : f[key];
      if (kept !== undefined) f[key] = clone(kept);
    });
    // When these two tables are on screen, their contents win; the line boxes still work and edit the same data.
    if (document.querySelector("[data-cit-text]") || document.querySelector("[data-sb-conc]")) {
      var cit = [];
      q("[data-cit-text]").forEach(function (el, n) {
        var text = el.value.trim(); if (!text) return;
        var sigs = [];
        q('[data-cit-sig="' + n + '"]').forEach(function (c) { if (c.checked) sigs.push(c.value); });
        cit.push({ text: text, signals: sigs });
      });
      f.citations = cit;
      var num = function (v) { var x = parseFloat(v); return isNaN(x) ? null : x; };
      var bandsOut = {};
      var hs = document.querySelector('[data-sb-min]'), ls = document.querySelector('[data-sb-max]');
      var hc = document.querySelector('[data-sb-conc="high"]'), lc = document.querySelector('[data-sb-conc="low"]');
      var mc = document.querySelector('[data-sb-conc="mid"]');
      if (hs && hc) bandsOut.high = { min: num(hs.value), conclusion: hc.value.trim(),
                                      severity: (document.querySelector('[data-sb-sev="high"]') || {}).value || "中" };
      if (ls && lc) bandsOut.low = { max: num(ls.value), conclusion: lc.value.trim(),
                                     severity: (document.querySelector('[data-sb-sev="low"]') || {}).value || "低" };
      if (mc) bandsOut.mid = { conclusion: mc.value.trim(),
                               severity: (document.querySelector('[data-sb-sev="mid"]') || {}).value || "中" };
      f.score_bands = bandsOut;
    }
    if (document.querySelector("[data-bill-price]")) {
      var bp = document.querySelector("[data-bill-price]");
      var raw = (bp.value || "").trim();
      var bc = document.querySelector("[data-bill-currency]");
      if (raw === "") { delete f.billing; }
      else {
        var pv = parseFloat(raw);
        if (isNaN(pv)) { throw new Error("每次调用的价格不是数字：" + raw); }
        f.billing = { unit_price: pv, currency: (bc && bc.value) || "CNY" };
      }
    }
    f.inputs = [];
    q("[data-in-name]").forEach(function (el) {
      var n = el.dataset.inName, name = el.value.trim(); if (!name) return;
      var chosen = (document.querySelector('[data-in-type="' + n + '"]') || {}).value || "string";
      var type = INT_TYPE[chosen] || "string";
      var item = { name: name, type: type };
      if (chosen === "money") item.__money = true;
      if (type === "enum" || chosen === "multi") {
        var vals = ((document.querySelector('[data-in-values="' + n + '"]') || {}).value || "")
          .split(/[、,，]/).map(function (x) { return x.trim(); }).filter(Boolean);
        if (vals.length) item.values = vals;
      }
      f.inputs.push(item);
    });
    f.industry_weights = {};
    f.industry_map = {};
    // The weights table's own row names are industries: treat them as usable as-is, so the mapping box is only
    // needed when the data spells an industry differently from the table row.
    try {
      var mapFromState = state && state.industry_weights ? state.industry_weights : {};
      Object.keys(mapFromState).forEach(function (cat) { if (cat) f.industry_map[cat] = cat; });
    } catch (e) {}
    var imEl = document.querySelector("[data-im-lines]");
    if (imEl) {
      (imEl.value || "").split("\n").forEach(function (ln) {
        var t = ln.trim(); if (!t || t.charAt(0) === "#") return;
        var parts = t.split(/→|->/);
        if (parts.length >= 2 && parts[0].trim() && parts[1].trim()) {
          f.industry_map[parts[0].trim()] = parts[1].trim();
        }
      });
    }
    q("[data-w-cat]").forEach(function (el, i) {
      var name = el.value.trim(); if (!name) return;
      var w = {};
      q('[data-w-val^="' + i + ':"]').forEach(function (v) {
        var dim = v.dataset.wVal.split(":")[1]; var num = parseFloat(v.value);
        if (dim && !isNaN(num)) w[dim] = num;
      });
      f.industry_weights[name] = w;
    });
    f.thresholds = { base: parseFloat((document.querySelector("[data-th-base]") || {}).value) || 1.0, adjustments: [] };
    q("[data-th-field]").forEach(function (el) {
      var n = el.dataset.thField, field = el.value.trim(); if (!field) return;
      var value = (document.querySelector('[data-th-value="' + n + '"]') || {}).value || "";
      var delta = parseFloat((document.querySelector('[data-th-delta="' + n + '"]') || {}).value);
      var reason = (document.querySelector('[data-th-reason="' + n + '"]') || {}).value || "";
      var cond = {}; cond[field] = /^-?\d+(\.\d+)?$/.test(value) ? Number(value) : value;
      f.thresholds.adjustments.push({ condition: cond, delta: isNaN(delta) ? 0 : delta, reason: reason });
    });
    f.signals = [];
    var prevSignals = (state && state.signals) || [];
    q("[data-sig-name]").forEach(function (el, sigIndex) {
      var n = el.dataset.sigName, name = el.value.trim();
      var field = ((document.querySelector('[data-sig-field="' + n + '"]') || {}).value || "").trim();
      if (!name || !field) return;
      var op = (document.querySelector('[data-sig-op="' + n + '"]') || {}).value || "eq";
      var useRefEl = document.querySelector('[data-sig-ref-use="' + n + '"]');
      var useRef = !!(useRefEl && useRefEl.checked);
      var raw = ((document.querySelector('[data-sig-value="' + n + '"]') || {}).value || "").trim();
      var refField = ((document.querySelector('[data-sig-ref="' + n + '"]') || {}).value || "").trim();
      var val;
      if (useRef && refField) val = { ref: refField, times: "threshold" };
      else { try { val = JSON.parse(raw); } catch (e) { val = /^-?\d+(\.\d+)?$/.test(raw) ? Number(raw) : raw; } }
      var when = {}; when[field] = { op: op, value: val };
      // 命中分值：留空＝1；写 0–1 之间的数表示部分命中；写别的会明确报错并中止保存。
      var svRaw = ((document.querySelector('[data-sig-score="' + n + '"]') || {}).value || "").trim();
      var sv = 1;
      if (svRaw !== "") {
        sv = parseFloat(svRaw);
        if (isNaN(sv) || sv < 0 || sv > 1) { throw new Error("「" + name + "」的命中分值要在 0 到 1 之间：" + svRaw); }
      }
      var sig = { name: name, when: when };
      // Keep fields this row already had: the line box stores a dimension per signal and rebuilding
      // the object from scratch dropped it on every save.
      var prev = prevSignals[sigIndex];
      if (prev && typeof prev === "object") {
        Object.keys(prev).forEach(function (k) { if (!(k in sig)) sig[k] = prev[k]; });
      }
      sig.score_value = sv;   // 显式写入：清空输入即回到 1，不会被上一轮的旧分值盖回来
      f.signals.push(sig);
    });
    f.combination_rules = [];
    var crSeen = {}; q("[data-cr-conc]").forEach(function (el) { crSeen[el.dataset.crConc] = 1; });
    Object.keys(crSeen).forEach(function (n) {
      var sigs = []; q('[data-cr-sig="' + n + '"]').forEach(function (c) { if (c.checked) sigs.push(c.value); });
      var conc = ((document.querySelector('[data-cr-conc="' + n + '"]') || {}).value || "").trim();
      if (!sigs.length || !conc) return;
      f.combination_rules.push({ all_of: sigs, conclusion: conc,
        severity: (document.querySelector('[data-cr-sev="' + n + '"]') || {}).value || "中" });
    });
    f.exception_rules = [];
    var exSeen = {}; q("[data-ex-kind]").forEach(function (el) { exSeen[el.dataset.exKind] = 1; });
    Object.keys(exSeen).forEach(function (n) {
      var sigs = []; q('[data-ex-sig="' + n + '"]').forEach(function (c) { if (c.checked) sigs.push(c.value); });
      var kind = (document.querySelector('[data-ex-kind="' + n + '"]') || {}).value || "adjust_threshold";
      var ov = { kind: kind };
      var target = ((document.querySelector('[data-ex-target="' + n + '"]') || {}).value || "").trim();
      var factor = parseFloat((document.querySelector('[data-ex-factor="' + n + '"]') || {}).value);
      var conc = ((document.querySelector('[data-ex-conc="' + n + '"]') || {}).value || "").trim();
      if (target) ov.target = target;
      if (!isNaN(factor)) ov.factor = factor;
      if (conc) ov.conclusion = conc;
      f.exception_rules.push({ condition: { all_signals: sigs }, override: ov,
        reason: ((document.querySelector('[data-ex-reason="' + n + '"]') || {}).value || "") });
    });
    f.signal_priority = [];
    q("[data-pr-val]").forEach(function (el) {
      var n = el.dataset.prVal;
      var sig = (document.querySelector('[data-pr-sig="' + n + '"]') || {}).value;
      var p = parseInt(el.value, 10);
      if (sig && !isNaN(p)) f.signal_priority.push({ signal: sig, priority: p });
    });
    f.adjustment_log = [];
    q("[data-log-step]").forEach(function (el) {
      var n = el.dataset.logStep, step = el.value.trim(); if (!step) return;
      f.adjustment_log.push({ step: step, reason: ((document.querySelector('[data-log-reason="' + n + '"]') || {}).value || "") });
    });
    delete f.__defId;
    return f;
  }

  function bind(view) {
    var host = view;
    host.querySelectorAll("[data-pro-mode]").forEach(function (b) {
      b.onclick = function () { professionalMode = b.dataset.proMode === "professional"; try { localStorage.setItem("po.professionalMode", professionalMode ? "1" : "0"); } catch (e) {} render(); };
    });
    var sel = host.querySelector("#pro-def");
    if (sel) sel.onchange = function () { defId = sel.value; state = null; render(); };
    var newName = host.querySelector("#pro-new-name");
    var newBtn = host.querySelector("#pro-new");
    if (newBtn) newBtn.onclick = async function () {
      var name = (newName && newName.value || "").trim();
      if (!name) { alert("请先填写新场景的名称。"); return; }
      var packs = await load("domain-packs");
      var packId = (packs && packs[0] && packs[0].id) || "legal.cn";
      var newId = "custom." + Date.now().toString(36);
      var out = await api("/v1/scenario-definitions", { method: "POST", body: JSON.stringify({
        id: newId, display_name_zh: name, display_name_en: name,
        domain_pack_ids: [packId], definition_version: "1", is_builtin: false }) });
      if (out && out.id) { cache["scenario-definitions"] = null; defId = out.id; state = null; render(); }
      else alert("新建失败：" + ((out && (out.detail || out.error)) || "请稍后重试"));
    };
    var renameBtn = host.querySelector("#pro-rename");
    if (renameBtn) renameBtn.onclick = async function () {
      var name = (newName && newName.value || "").trim();
      if (!name) { alert("把新名称填在左边的输入框里，再点改名。"); return; }
      await api("/v1/scenario-definitions/" + encodeURIComponent(defId), { method: "PATCH",
        body: JSON.stringify({ display_name_zh: name, display_name_en: name }) });
      cache["scenario-definitions"] = null; render();
    };
    var delBtn = host.querySelector("#pro-del-def");
    if (delBtn) delBtn.onclick = async function () {
      if (!confirm("删除这个场景？它下面的切片与判断不会一并删除。")) return;
      await api("/v1/scenario-definitions/" + encodeURIComponent(defId), { method: "DELETE" });
      cache["scenario-definitions"] = null; defId = null; state = null; render();
    };
    host.querySelectorAll("[data-add]").forEach(function (b) {
      b.onclick = function () {
        var kind = b.dataset.add;
        // Capture everything the user has typed before appending. collect() reads the DOM, so it must run
        // first; if it fails we report and abort rather than silently discarding their input.
        try {
          state = collect();
        } catch (e) {
          alert("读取当前输入出错，已中止本次操作（你的输入没有被丢弃）：" + (e && e.message ? e.message : e));
          return;
        }
        if (kind === "input") state.inputs.push({ name: "", type: "string" });
        else if (kind === "weight-cat") {
          var dims = {};
          Object.keys(state.industry_weights).forEach(function (c) {
            Object.keys(state.industry_weights[c] || {}).forEach(function (d) { dims[d] = 1; });
          });
          var blank = {};
          Object.keys(dims).forEach(function (d) { blank[d] = 0; });
          if (!Object.keys(blank).length) blank["侧重"] = 0;
          state.industry_weights["新行业" + (Object.keys(state.industry_weights).length + 1)] = blank;
        }
        else if (kind === "weight-dim") Object.keys(state.industry_weights).forEach(function (c) {
          var w = state.industry_weights[c]; w["维度" + (Object.keys(w).length + 1)] = 0;
        });
        else if (kind === "threshold") state.thresholds.adjustments.push({ condition: {}, delta: 0, reason: "" });
        else if (kind === "signal") state.signals.push({ name: "", when: {} });
        else if (kind === "rule") state.combination_rules.push({ all_of: [], conclusion: "", severity: "中" });
        else if (kind === "exception") state.exception_rules.push({ condition: { all_signals: [] }, override: { kind: "adjust_threshold" }, reason: "" });
        else if (kind === "priority") state.signal_priority.push({ signal: state.signals[0] ? state.signals[0].name : "", priority: state.signal_priority.length + 1 });
        else if (kind === "citation") state.citations = (state.citations || []).concat([{ text: "", signals: [] }]);
        else if (kind === "log") state.adjustment_log.push({ step: "", reason: "" });
        render();
      };
    });
    host.querySelectorAll("[data-del]").forEach(function (b) {
      b.onclick = function () {
        try { state = collect(); } catch (e) {}
        var parts = b.dataset.del.split(":"), what = parts[0], n = parseInt(parts[1], 10);
        if (what === "input") state.inputs.splice(n, 1);
        else if (what === "weights") delete state.industry_weights[Object.keys(state.industry_weights)[n]];
        else if (what === "threshold") state.thresholds.adjustments.splice(n, 1);
        else if (what === "signal") state.signals.splice(n, 1);
        else if (what === "rule") state.combination_rules.splice(n, 1);
        else if (what === "exception") state.exception_rules.splice(n, 1);
        else if (what === "priority") state.signal_priority.splice(n, 1);
        else if (what === "citation") state.citations.splice(n, 1);
        else if (what === "log") state.adjustment_log.splice(n, 1);
        render();
      };
    });
    // Re-render on type or exception-kind change so only the needed inputs show.
    host.querySelectorAll("[data-in-type]").forEach(function (s) { s.onchange = function () { state = collect(); render(); }; });
    host.querySelectorAll("[data-ex-kind]").forEach(function (s) { s.onchange = function () { state = collect(); render(); }; });
    var gen = host.querySelector("#pro-gen");
    if (gen) gen.onclick = async function () {
      var desc = (host.querySelector("#pro-desc") || {}).value || "";
      lastDraft = desc;
      var h = host.querySelector("#pro-hint"); if (h) h.textContent = "正在让模型起草…（大约十几秒）";
      var out = await api("/v1/scenario-definitions/" + encodeURIComponent(defId) + "/draft", { method: "POST", body: JSON.stringify({ description: desc }) });
      if (out && out.framework) { state = ensureShape(out.framework); state.__defId = defId; render(); }
      else if (h) { h.textContent = "起草失败：" + ((out && (out.detail || out.error)) || "请检查模型服务"); }
    };
    var saveAll = host.querySelectorAll("[data-save-framework]");
    saveAll.forEach(function (btn) { btn.onclick = async function () {
      var f = collect();
      var bndRaw = ((host.querySelector("[data-bnd-amount]") || {}).value || "").trim();
      var bnd = {
        max_amount: bndRaw === "" ? null : Number(bndRaw),
        allowed_scenarios: ((host.querySelector("[data-bnd-scenarios]") || {}).value || "")
          .split(/[、,，]/).map(function (x) { return x.trim(); }).filter(Boolean),
        confidentiality: ((host.querySelector("[data-bnd-conf]") || {}).value || "").trim(),
        default_tier: ((host.querySelector("[data-dlv-tier]") || {}).value || "audit"),
        pricing: (function () {
          var tiers = {};
          host.querySelectorAll("[data-price-tier]").forEach(function (el) {
            var v = parseFloat(el.value);
            if (!isNaN(v)) tiers[el.dataset.priceTier] = v;
          });
          return { mode: ((host.querySelector("[data-price-mode]") || {}).value || "per_call"), tiers: tiers };
        })()
      };
      var dvDays = ((host.querySelector("[data-dlv-days]") || {}).value || "").trim();
      await api("/v1/scenario-definitions/" + encodeURIComponent(defId), { method: "PATCH", body: JSON.stringify({
        framework: f, boundaries: bnd,
        insight: ((host.querySelector("[data-dlv-insight]") || {}).value || "").trim(),
        owner_credentials: ((host.querySelector("[data-dlv-cred]") || {}).value || "").trim(),
        valid_days: dvDays === "" ? 1 : Number(dvDays) }) });
      cache["scenario-definitions"] = null; state = null; render();
    }; });
    // The tier chosen next to the save button goes into boundaries (no backend change needed).
    var tierSel = host.querySelector("[data-dlv-tier]");
    if (tierSel) tierSel.onchange = function () { state.__tier = tierSel.value; };
  }

  // ── Billing (demonstration only) ──
// The price is always typed by the owner; the software never invents one. The meter simply counts the audit
// records of external judgments for this slice, so no separate billing table exists yet.
function billingPanel(f) {
  var bill = f.billing || {};
  return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
    '<div class="panel-title"><span>计费（演示）</span></div>' +
    hint('每次调用多少钱由你填；留空表示暂不计费。金额只是按"调用次数 × 单价"估算，尚未接真实支付。') +
    row('<span class="pro-band">每次调用</span>' +
        input(bill.unit_price === 0 || bill.unit_price ? bill.unit_price : "", 'data-bill-price placeholder="例如 200"') +
        '<select class="select" data-bill-currency>' +
          ["CNY", "USD"].map(function (c) {
            return "<option" + ((bill.currency || "CNY") === c ? " selected" : "") + ">" + c + "</option>";
          }).join("") +
        "</select>" +
        '<span class="muted">元 / 次</span>') +
    '</section>';
  bindRowButtons(view);   // bind add/remove/type-change buttons on every render
}

// ── Table editors for citations (part 7) and score bands (part 8) ──
// These two used to be editable only line by line; these panels match the others so they can be reviewed here.
function citationsPanel(f) {
  var list = f.citations || [];
  var names = (f.signals || []).map(function (x) { return x.name; });
  var checks = function (selected, n) {
    return names.map(function (nm) {
      var on = (selected || []).indexOf(nm) >= 0;
      return '<label class="pro-check"><input type="checkbox" data-cit-sig="' + n + '" value="' + esc(nm) + '"' +
             (on ? " checked" : "") + ">" + esc(nm) + "</label>";
    }).join("") || '<span class="muted">先在上面加观察点</span>';
  };
  return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
    '<div class="panel-title"><span>我的依据</span></div>' +
    hint('一行一条依据：写依据名；如果这条依据只在某些观察点都成立时才适用，就把它们勾上。') +
    list.map(function (c, n) {
      return row('<div class="pro-checks" style="min-width:260px">' + checks(c.signals, n) + "</div>" +
        input(c.text, 'data-cit-text="' + n + '" placeholder="依据名，例如：某法第二十六条"') +
        del("citation:" + n));
    }).join("") +
    '<button class="button" data-add="citation">＋ 加一条依据</button></section>';
}

function scoreBandsPanel(f) {
  var bands = f.score_bands || {};
  var rowFor = function (key, label, field, value) {
    var b = bands[key] || {};
    return row('<span class="pro-band">' + label + "</span>" +
      (field ? input(value, 'data-sb-' + field + ' placeholder="0.5"') : "") +
      input(b.conclusion || "", 'data-sb-conc="' + key + '" placeholder="结论"') +
      '<select class="select" data-sb-sev="' + key + '">' +
        ["低", "中", "高", "极高"].map(function (x) {
          return "<option" + (b.severity === x ? " selected" : "") + ">" + x + "</option>";
        }).join("") +
      "</select>");
  };
  return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
    '<div class="panel-title"><span>打分线</span></div>' +
    hint('分数 = 命中的观察点各取其维度的权重之和。这里定分数怎么变成结论。') +
    rowFor("high", "打分", "min", (bands.high || {}).min) +
    rowFor("low", "打分", "max", (bands.low || {}).max) +
    rowFor("mid", "其余", null, null) +
    '</section>';
}

window.POPro = { renderSlices: renderSlices, polishPanels: polishPanels };
})();


  // -- Unassigned slices: their scenario was deleted, so they must be recoverable --
  // -- Line-based entry: one line per item, with the format shown inline --
  function docImportPanel() {
  return '<section class="panel" id="pro-doc" style="padding:16px;margin-bottom:12px">' +
    '<div class="panel-title"><span>方式二 · 一次性写入（整篇贴进来）</span></div>' +
    '<div class="panel-caption">整篇一次写完、一次提交。用【小节标题】分段，标题下面一行一条，语法与下面的逐行输入完全相同。</div>' +
    '<div class="panel-caption">样例里的名字与数字都是占位，请全部换成你自己的；计费留空即不计费。</div>' +
    '<textarea class="input mono" rows="16" style="width:100%;margin-top:8px" data-doc-input ' +
      'placeholder="点下面的【填入样例】看整篇长什么样，再照着改"></textarea>' +
    '<div style="margin-top:8px;display:flex;gap:6px;align-items:center;flex-wrap:wrap">' +
      '<button class="button" data-doc-sample>填入样例</button>' +
      '<button class="button primary" data-doc-parse>提交解析</button>' +
      '<button class="button" data-doc-clear>清空</button>' +
      '<span class="panel-caption" id="doc-report"></span>' +
    "</div></section>";
}

function lineImportPanel() {
    var parts = [
      ["inputs", "我要知道的信息", "名称 ｜ 数字 / 文字 / 选项 ｜ 甲、乙 / 是-否 / 多项 ｜ 甲、乙", "市盈率 ｜ 数字\n现金流状况 ｜ 选项 ｜ 健康、紧张、危机"],
      ["thresholds", "判断的基准线", "基准 1.3　以及　条件=值 → 调整量", "基准 1.3\n监管环境=收紧 → -0.10"],
      ["signals", "我观察什么", "信号名 = 字段 大于/小于/等于/属于/包含 值（可写「字段 × 基准线」）", "团队流失高 = 核心团队流失风险 等于 高"],
      ["rules", "几个观察点一起出现时", "信号 且 信号 → 结论（严重度）", "团队流失高 且 现金流危机 → 估值偏高（高）"],
      ["exceptions", "例外情况", "条件 且 条件 → 某维度权重 ×0.5 / 基准线 ×1.2 / 直接判 结论", "技术已专利化 且 技术壁垒极高 → 团队流失权重 ×0.5"],
      ["priority", "哪个更重要", "更重要的 > 次重要的（> 两边留空格）", "现金流危机 > 团队流失高"],
      ["citations", "我的依据", "依据名　或　依据名 → 信号1 且 信号2（全部命中才附上）", "反垄断法第二十六条 → 团队流失高 且 现金流危机\n证券法第七十八条"],
      ["score", "打分线（分数怎么变成结论）", "打分 X 以上 → 结论（严重度）／打分 X 以下 → …／其余 → …", "打分 0.5 以上 → 估值偏高（高）\n打分 0.3 以下 → 估值合理（低）\n其余 → 估值中性（中）"]
    ];
    return '<section class="panel" id="pro-lines" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>方式三 · 逐行写入（8 个框，一行一条）</span></div>' +
      '<div class="panel-caption" style="margin:6px 0 10px">每个框里一行写一条，中文短语即可，不用写 JSON。写错的行只会单独报出来，不影响其它行<br><strong>两种方式随时可以混用</strong>：先让模型起草再用这里逐条改，或只写几条、剩下的让模型补</div>' +
      parts.map(function (p, i) {
        return '<div style="margin-top:10px">' +
          '<div class="field-label">' + p[1] + '</div>' +
          '<div class="panel-caption" style="margin:2px 0 4px">格式：' + esc(p[2]) + '</div>' +
          '<textarea class="input mono" rows="3" style="width:100%" data-line-part="' + p[0] + '" placeholder="' + esc(p[3]) + '"></textarea>' +
          '</div>';
      }).join("") +
      '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
        '<button class="button primary" data-save-framework>保存</button>' +
        '<span class="panel-caption" style="margin:0">保存会先把上面的内容变成下面面板里的内容，再存进这条切片；有看不懂的行会弹出来告诉你第几行</span>' +
        '<span class="panel-caption" style="margin:0" id="line-report"></span>' +
      '</div></section>';
  }


  function orphanPanel(orphans, defs, nameOf) {
    if (!orphans.length) return "";
    var options = defs.map(function (d) {
      return '<option value="' + esc(d.id) + '">' + esc(fieldLabel(d, "display_name_zh", "display_name_en")) + "</option>";
    }).join("");
    var rows = orphans.map(function (x) {
      var conf = x.confidence_status && x.confidence_status !== "unverified" ? x.confidence_status : "未验证";
      var action = defs.length
        ? '<select class="select" data-orphan-target="' + esc(x.id) + '" style="max-width:180px">' + options + "</select>" +
          '<button class="button primary" data-orphan-attach="' + esc(x.id) + '">挂过去</button>'
        : '<span class="muted">先建一个场景才能挂</span>';
      return "<tr><td>" + esc(nameOf(x)) + "</td>" +
        "<td>" + (poHasFramework(x) ? "已有框架" : '<span class="muted">尚未配置</span>') + "</td>" +
        "<td>" + esc(conf) + "</td>" +
        '<td style="text-align:right;white-space:nowrap">' + action +
        ' <button class="button" data-orphan-del="' + esc(x.id) + '">删除</button></td></tr>';
    }).join("");
    return '<section class="panel collection-panel" style="margin-top:12px">' +
      '<div class="collection-toolbar"><span class="record-count"><span>未归属切片</span> ' + orphans.length +
      ' <span>条</span></span><span class="toolbar-spacer"></span>' +
      '<span class="panel-caption" style="margin:0">这些切片所属的场景已被删除 —— 数据还在，挂回一个场景就能继续用</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>名称</th><th>框架</th><th>置信度</th><th style="text-align:right">操作</th></tr></thead>' +
      "<tbody>" + rows + "</tbody></table></div></section>";
  }


  // -- My slices: the draft-like list for the selected scenario (professional side) --
  function sliceTable(mine, currentId, nameOf) {
    if (!mine.length) {
      return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
        '<div class="panel-title"><span>我的切片</span></div>' +
        '<div class="panel-caption" style="margin:6px 0 0">这个场景还没有我的切片。你在上面点「＋ 新建我的切片」开始一条；' +
        '场景只是可共享的模板，判断存在切片里</div></section>';
    }
    var rows = mine.map(function (x) {
      var b = x.boundaries || {}, pr = b.pricing || {}, tiers = pr.tiers || {};
      var priced = Object.keys(tiers).length;
      var conf = x.confidence_status && x.confidence_status !== "unverified" ? x.confidence_status : "未验证";
      return '<tr>' +
        '<td>' + esc(nameOf(x)) + (x.id === currentId ? ' <span class="badge">当前</span>' : "") +
        (x.status === "confirmed" ? ' <span class="badge">已启用</span>' : ' <span class="muted">草稿</span>') + "</td>" +
        "<td>" + (poHasFramework(x) ? "已有框架" : '<span class="muted">尚未配置</span>') + "</td>" +
        "<td>" + esc(conf) + "</td>" +
        "<td>" + (priced ? ("已设 " + priced + " 项") : '<span class="muted">未设</span>') + "</td>" +
        '<td style="text-align:right;white-space:nowrap">' +
          '<button class="button" data-pick-slice="' + esc(x.id) + '">核对与微调</button> ' +
          (x.status === "confirmed"
            ? '<button class="button" data-unconfirm-slice="' + esc(x.id) + '">退回草稿</button> '
            : '<button class="button primary" data-confirm-slice="' + esc(x.id) + '">确认并启用…</button> ') +
          (window.poEnableFor === x.id ? granteePicker(window.poPrincipals || [], window.poApprovedAgents || []) : "") +
          '<button class="button" data-drop-slice="' + esc(x.id) + '">删除</button>' +
        "</td></tr>";
    }).join("");
    return '<section class="panel collection-panel">' +
      '<div class="collection-toolbar"><span class="record-count"><span>我的切片</span> ' + mine.length +
      ' <span>条</span></span><span class="toolbar-spacer"></span>' +
      '<span class="panel-caption" style="margin:0">草稿就在这里：一条切片 = 一套你的判断</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>名称</th><th>框架</th><th>置信度</th><th>定价</th><th style="text-align:right">操作</th></tr></thead>' +
      "<tbody>" + rows + "</tbody></table></div></section>";
  }

// Safety net: any unhandled failure from an API call now surfaces to the user instead of
// leaving the interface apparently doing nothing (which made earlier bugs look like no-ops).
window.addEventListener("unhandledrejection", function (e) {
  var r = e.reason;
  var msg = (r && (r.message || r.detail || r.error)) || r || "未知错误";
  // Also write it to the console with the stack: the alert alone made these errors impossible to
  // diagnose (the page showed a message while the console stayed empty).
  console.error("操作失败：", r, (r && r.stack) || "");
  alert("操作失败：" + msg + "\n\n" + String((r && r.stack) || "").slice(0, 700));
});

// -- Choose who may call this slice: the grantor (you) and the grantee (the caller) must both be principals --
function granteePicker(principals, agents) {
  var people = principals || [];
  var programs = agents || [];
  if (!people.length) {
    return '<div class="panel-caption" style="margin-top:6px">还没有主体。请先到「主体」菜单建一个「本人」（类型选 person），它是授权方。</div>';
  }
  var popts = people.map(function (pp) {
    return '<option value="' + esc(pp.id) + '">' + esc(pp.display_name_zh || pp.id) + "</option>";
  }).join("");
  if (!programs.length) {
    return '<div class="panel-caption" style="margin-top:6px">授权方 <select class="select" data-enable-grantor>' + popts + '</select>' +
      '<br>还没有【已批准的本机程序】。正确的顺序是：让调用方先连一次 → 它会出现在「本机程序」页等待批准 → ' +
      '你在那里批准并勾选 judgment 范围 → 它才会出现在这里供你选择。' +
      '<div style="margin-top:6px"><button class="button" data-cancel-enable>取消</button></div></div>';
  }
  var aopts = programs.map(function (a) {
    var sc = (a.scopes || []).indexOf("judgment") >= 0 ? "（已含 judgment）" : "（缺 judgment 范围，需先批准）";
    return '<option value="' + esc(a.key) + '">' + esc(a.name || a.key) + " " + sc + "</option>";
  }).join("");
  return '<div class="panel-caption" style="margin-top:6px;display:flex;gap:6px;align-items:center;flex-wrap:wrap">' +
    '<span>授权方</span><select class="select" data-enable-grantor>' + popts + "</select>" +
    '<span>被授权方（已批准的本机程序）</span><select class="select" data-enable-agent>' + aopts + "</select>" +
    '<button class="button primary" data-do-enable>确认启用</button>' +
    '<button class="button" data-cancel-enable>取消</button></div>';
}

// -- Post-render polish: fold each editor panel and build a sticky index beside it. DOM-only, so it cannot
//    disturb the panel templates (and it is guarded so a second render never double-wraps). --
function polishPanels(view) {
  var ed = view.querySelector("#pro-editor");
  if (!ed || ed.dataset.polished === "1") return;
  ed.dataset.polished = "1";
  var sections = Array.prototype.slice.call(ed.children).filter(function (el) {
    return el.classList && el.classList.contains("panel");
  });
  if (!sections.length) return;
  // Two audiences: my own judgment model, and what the caller must supply and obey. Grouping the panels by
  // audience answers at a glance which parts are written for the caller.
  var isCallerPanel = function (title) {
    if (title.indexOf("计费") >= 0) { return true; }
    return title.indexOf("对外") >= 0 || title.indexOf("我要知道的信息") >= 0;
  };
  // Method two: fill in the sample, parse it, or clear it. The panel lives in the view, not inside the editor.
  // 判定模型选择：切换前确认（不同模型支持的字段不同），选择记在 window.poJudgmentModel。
  var modelSel = view.querySelector("#pro-model");
  if (modelSel && !modelSel.dataset.wired) {
    modelSel.dataset.wired = "1";
    modelSel.onchange = function () {
      var pick = modelSel.value, cur = window.poJudgmentModel || "";
      if (pick === cur) { return; }
      var okSwitch = confirm("切到「" + pick + "」后，判定按新模型重算。\n已填内容不会丢；" +
        "但有些字段可能不再参与判定（例如权重表只对评分卡有意义）。\n\n确定切换吗？");
      if (!okSwitch) { modelSel.value = cur; return; }
      window.poJudgmentModel = pick;
      // 就地更新下面那段说明（重画整页会弄丢你正在填的内容）。
      var desc = view.querySelector("#pro-model-desc");
      var descHtml = (window.poModelDesc || {})[pick];
      if (desc && descHtml) { desc.innerHTML = descHtml; }
      // 标题也要跟着变（只更新说明会让标题停在旧模型上）。
      var titleEl = view.querySelector("#pro-model-title");
      var titleText = (window.poModelTitle || {})[pick];
      if (titleEl && titleText) { titleEl.textContent = titleText; }
      var note = view.querySelector("#pro-model-note");
      if (note) { note.textContent = "已切到 " + pick + "；保存后这条切片就会按它判定。"; }
    };
  }

  var docPanel = view.querySelector("#pro-doc");
  if (docPanel && !docPanel.dataset.wired) {
    docPanel.dataset.wired = "1";
    var docTa = docPanel.querySelector("[data-doc-input]");
    var docRep = docPanel.querySelector("#doc-report");
    var btnSample = docPanel.querySelector("[data-doc-sample]");
    var btnClear = docPanel.querySelector("[data-doc-clear]");
    var btnParse = docPanel.querySelector("[data-doc-parse]");
    if (!docTa || !btnSample || !btnClear || !btnParse) { return; }   // 结构不全就跳过绑定，不抛错
    btnSample.onclick = function () {
      docTa.value = docSample();
      docRep.textContent = "样例已填入，请改成你自己的内容。";
    };
    btnClear.onclick = function () {
      docTa.value = ""; docRep.textContent = "";
    };
    btnParse.onclick = async function () {
      var sel = document.querySelector("#pro-slice");
      var sid = (sel && sel.value) || window.poCurrentSliceId || "";
      if (!sid) {
        var nSlices = document.querySelectorAll("[data-pick-slice]").length;
        alert("还不能解析：页面上没有当前切片。\n\n诊断：场景=" + (window.poCurrentDefId || "(未选)") +
          "，场景下的切片数=" + nSlices + "，下拉框值=\"" + ((sel && sel.value) || "") + "\"。\n" +
          (nSlices ? "请在下拉框里选中一条我的切片再试。" : "这个场景下还没有你的切片，请先在第一步新建。"));
        return;
      }
      if (!docTa.value.trim()) { docRep.textContent = "先把整篇贴进上面的框里（或点【填入样例】）。"; return; }
      docRep.textContent = "解析中…";
      var parsed = null;
      try {
        parsed = await api("/v1/scenario-slices/" + encodeURIComponent(sid) + "/import-lines",
          { method: "POST", body: JSON.stringify({ document: docTa.value, save: true }) });
      } catch (err) {
        docRep.textContent = ""; alert("解析失败：" + (err && err.message ? err.message : err)); return;
      }
      var reportLines = [];
      var rep = (parsed && parsed.report) || {};
      Object.keys(rep).forEach(function (kk) {
        var n = rep[kk].imported || 0, errs = rep[kk].errors || [];
        reportLines.push("【" + kk + "】导入 " + n + " 条" + (errs.length ? ("，有 " + errs.length + " 行有问题") : ""));
        errs.forEach(function (e) { reportLines.push("   第 " + e.line + " 行：" + e.text + " → " + e.reason); });
      });
      ((parsed && parsed.split_errors) || []).forEach(function (e) {
        reportLines.push("   第 " + e.line + " 行：" + e.text + " → " + e.reason);
      });
      docRep.textContent = reportLines.length ? reportLines.join("\n") : "没有解析到内容，请检查小节标题。";
      docRep.style.whiteSpace = "pre-wrap";
      // Reload the slice the way the review button does, otherwise step three stays empty.
      {   // no condition needed: reaching here means the parse already succeeded
        if (typeof window.poReloadSlice === "function") { window.poReloadSlice(); }
        else if (typeof window.poRefreshSlice === "function") { window.poRefreshSlice(); }
        var ed = document.querySelector("#pro-editor");
        if (ed && ed.scrollIntoView) { try { ed.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (e) {} }
      }   // NOTE: this handler lives outside the IIFE; it only calls the published hook
    };
  }

  var toc = document.createElement("div");
  toc.className = "pro-toc";

  var groups = [
    { title: "我的判断模型",
      caption: "这一组是你自己的判断依据，只有你看得到；调用方看不到，也不受它约束。",
      cls: "pro-group-model", host: null, tocBox: null },
    { title: "对外调用与交付（写给调用方）",
      caption: "这一组是调用方看得到、必须遵守的：要传什么值、不许做什么、交付时附上什么说明。",
      cls: "pro-group-caller", host: null, tocBox: null }
  ];
  groups.forEach(function (g) {
    g.host = document.createElement("section");
    g.host.className = "pro-group " + g.cls;
    var h = document.createElement("div");
    h.className = "panel-title";
    h.innerHTML = "<span>" + esc(g.title) + "</span>";
    var c = document.createElement("div");
    c.className = "panel-caption";
    c.textContent = g.caption;
    g.host.appendChild(h);
    g.host.appendChild(c);
    g.tocBox = document.createElement("div");
    g.tocBox.className = "pro-toc-group";
    var tl = document.createElement("div");
    tl.className = "pro-toc-title";
    tl.textContent = g.title;
    g.tocBox.appendChild(tl);
    toc.appendChild(g.tocBox);
  });
  sections.forEach(function (sec) {
    var t = sec.querySelector(".panel-title");
    var title = t ? t.textContent.trim() : "面板";
    var count = sec.querySelectorAll("[data-del]").length;
    // No folding: every panel stays visible. The left index still scrolls to them, and the view
    // counts in the index come from the same place as before.
    if (title.indexOf("几个观察点一起出现时") >= 0 || title.indexOf("例外情况") >= 0 ||
        title.indexOf("我的依据") >= 0) { sec.classList.add("pro-rules"); }
    // D/E: put the call contract next to the delivery note, and compose the two into one pasteable page.
    if (title.indexOf("对外交付时附上的说明") >= 0 && !sec.querySelector("[data-contract-btn]")) {
      var bar = document.createElement("div");
      bar.className = "pro-contract-bar";
      bar.innerHTML = '<button class="button" data-contract-btn="view">查看调用说明</button>' +
                      '<button class="button primary" data-contract-btn="compose">生成交付说明（含调用说明）</button>' +
                      '<span class="panel-caption" data-contract-note></span>';
      sec.appendChild(bar);
      var box = document.createElement("div");
      sec.appendChild(box);
      bar.querySelectorAll("[data-contract-btn]").forEach(function (btn) {
        btn.onclick = async function () {
          var note = bar.querySelector("[data-contract-note]");
          var sel = document.querySelector("#pro-slice");
          var sid = (sel && sel.value) || window.poCurrentSliceId || "";
          if (!sid) {
            var nSlices = document.querySelectorAll("[data-pick-slice]").length;
            alert("还不能解析：页面上没有当前切片。\n\n诊断：场景=" + (window.poCurrentDefId || "(未选)") +
              "，场景下的切片数=" + nSlices + "，下拉框值=\"" + ((sel && sel.value) || "") + "\"。\n" +
              (nSlices ? "请在下拉框里选中一条我的切片再试。" : "这个场景下还没有你的切片，请先在第一步新建。"));
            return;
          }
          note.textContent = "读取中…";
          var c = null;
          try { c = await api("/v1/scenario-slices/" + encodeURIComponent(sid) + "/contract"); }
          catch (e) { note.textContent = ""; alert("取调用说明失败：" + (e && e.message ? e.message : e)); return; }
          note.textContent = "";
          if (btn.dataset.contractBtn === "view") {
            box.innerHTML = contractHtml(c);
            return;
          }
          // compose: the owner's own delivery note first, then the call contract
          var fwk = (window.poProSlice && window.poProSlice.framework) || {};
          var dv = fwk.delivery || {};
          var head = [];
          head.push("交付说明 · " + (c.title || sid));
          if (dv.insight) head.push("这套判断强在哪：" + dv.insight);
          if (dv.owner_credentials) head.push("出具人资历：" + dv.owner_credentials);
          if (dv.default_tier) head.push("交付档位：" + dv.default_tier);
          if (dv.valid_days) head.push("有效期：" + dv.valid_days + " 天");
          head.push("");
          box.innerHTML = '<div class="panel-caption" style="margin-top:8px">交付说明（你自己的话 ＋ 调用说明）：</div>' +
            '<pre class="pro-copy">' + esc(head.concat(contractLines(c)).join("\n")) + "</pre>";
        };
      });
    }
    // 按模型显示：只留该模型 input_contract().fields 里提到的字段对应的面板，
    // 加上所有模型共用的那几个（调用方信息、依据、兜底、对外边界/交付/计费、模型自身、调整记录）。
    var PANEL_FIELD = {
      "不同行业的侧重": "industry_weights", "判断的基准线": "thresholds", "我观察什么": "signals",
      "几个观察点一起出现时": "combination_rules", "例外情况": "exception_rules",
      "哪个观察点更重要": "signal_priority", "打分线": "score_bands",
      "公式": "formulas", "分档": "bands"
    };
    var SHARED_PANELS = ["需要调用方提交的信息", "我要知道的信息", "我的依据", "对外调用", "对外交付",
                         "计费", "判定模型", "我的调整记录", "兜底"];
    if (window.poModelFields && window.poModelFields.length) {
      var shared = SHARED_PANELS.some(function (x) { return title.indexOf(x) >= 0; });
      var need = PANEL_FIELD[title];
      if (!shared && need && window.poModelFields.indexOf(need) < 0) { sec.style.display = "none"; }
    }
    // 给这个面板里的每一条编号（1、2、3……），让面板与左侧索引里的"· N 条"一眼对得上。
    // 这段曾在 b4e2d7f 被我连同折叠代码一起删掉过，直到界面行为测试（tests/test_ui_behavior.js）
    // 断言"面板条目被编号"才被发现。以后动这一带要跑那个测试。
    Array.prototype.slice.call(sec.querySelectorAll(".pro-row")).forEach(function (r, i) {
      if (r.querySelector(".pro-num")) { return; }
      var badge = document.createElement("span");
      badge.className = "pro-num";
      badge.textContent = String(i + 1);
      r.insertBefore(badge, r.firstChild);
    });
    var g = groups[isCallerPanel(title) ? 1 : 0];
    g.host.appendChild(sec);
    var link = document.createElement("a");
    link.href = "#";
    link.textContent = title + (count ? " · " + count : "");
    link.onclick = function (ev) {
      ev.preventDefault();
      if (sec.scrollIntoView) sec.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    g.tocBox.appendChild(link);
  });
  groups.forEach(function (g) { ed.appendChild(g.host); });
  var wrap = document.createElement("div");
  wrap.className = "pro-editor-wrap";
  ed.parentNode.insertBefore(wrap, ed);
  wrap.appendChild(toc);
  wrap.appendChild(ed);
}
