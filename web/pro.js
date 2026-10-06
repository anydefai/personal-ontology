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
      f.inputs.map(function (i, n) {
        var t = (i.type === "number" && i.__money) ? "money" : (i.type || "string");
        return row('<div style="min-width:150px">' + input(i.name, 'data-in-name="' + n + '" placeholder="叫什么，例如：标的行业"') + "</div>" +
          '<div style="min-width:220px"><select class="select" data-in-type="' + n + '">' +
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
      if (!cats.length) cats = ["新行业1"];
    var dims = {};
    cats.forEach(function (c) { Object.keys(f.industry_weights[c] || {}).forEach(function (d) { dims[d] = 1; }); });
    var dimList = Object.keys(dims);
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>不同行业的侧重</span></div>' +
      hint('同样是并购，科技公司更看技术、传统制造更看财务。一行一个行业。') +
      (cats.length ? '<div class="pro-grid" style="grid-template-columns:1.2fr repeat(' + Math.max(dimList.length, 1) + ',1fr) 0.6fr">' +
        "<div>行业</div>" + (dimList.length ? dimList.map(function (d) { return "<div>" + esc(d) + "</div>"; }).join("") : "<div>侧重</div>") + "<div></div>" +
        cats.map(function (c, n) {
          return "<div>" + input(c, 'data-w-cat="' + n + '"') + "</div>" +
            (dimList.length ? dimList.map(function (d) {
              return "<div>" + input((f.industry_weights[c] || {})[d], 'data-w-val="' + n + ":" + esc(d) + '"') + "</div>";
            }).join("") : "<div>" + input("", 'data-w-val="' + n + ':weight"') + "</div>") +
            "<div>" + del("weights:" + n) + "</div>";
        }).join("") + "</div>" : hint("还没有行业。")) +
        (dimList.length ? "" : '<div class="panel-caption" style="margin-top:8px">这张表要先有「维度」才能填：请到上面【我观察什么】在每个信号末尾加上 ｜ 维度名（例如 ｜ 财务），保存后回到这里，就会出现对应的列。</div>') +
      '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">' +
      '<div style="margin-top:12px">' +
        '<details style="margin-top:10px"><summary class="panel-caption" style="cursor:pointer">可选：只有当数据里的写法与上表的行业不一致时才需要填这里</summary><div style="margin-top:6px">' +
        hint('一行一条：数据里的写法 → 上表里的行业。写法一致就不用填。') +
        '<textarea class="input mono" data-im-lines rows="3" style="width:100%" placeholder="数据里的写法 → 表里的行业">' +
        Object.keys(f.industry_map || {}).map(function (k) { return esc(k) + " → " + esc(f.industry_map[k]); }).join("\n") +
        '</textarea></div></details>' +
      '<button class="button" data-add="weight-cat">＋ 加一个行业</button>' +
      '<button class="button" data-add="weight-dim">＋ 加一个侧重维度</button>' +
      '<span class="panel-caption" style="margin:0">数值加起来是 1 就行；没把握就先平均。</span></div></section>';
  }

  // ── 3 · 判断的基准线 ──
  function thresholdsPanel(f) {
    var th = f.thresholds || {};
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>判断的基准线</span></div>' +
      hint('先定一条基准线，再说明什么情况下把它调高或调低。例如：基准 1.3，行业处于上升期就上调 0.15。') +
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

  async function renderSlices(view) {
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
    var pend = null;
    try { pend = sessionStorage.getItem("poProPickSlice"); } catch (e) { pend = null; }
    if (pend) {
      try { sessionStorage.removeItem("poProPickSlice"); } catch (e) {}
      if (mine.some(function (x) { return x.id === pend; })) sliceId = pend;
    }
    if (!sliceId || !mine.some(function (x) { return x.id === sliceId; })) sliceId = mine[0] ? mine[0].id : null;
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
        "</div>" +
        (slice
          ? '<div class="panel-caption" style="margin:10px 0 0">当前切片：<strong>' +
            esc((slice.analysis && slice.analysis.title) || slice.original_text || slice.id) + "</strong> · 置信度 " +
            esc(slice.confidence_status || "未验证") + " · 保存与起草都写在这条切片上</div>"
          : '<div class="panel-caption" style="margin:10px 0 0">先新建一条「我的切片」，框架保存在切片上</div>') +
        '<div class="panel-title" style="margin-top:8px"><span>方式一 · 让模型起草</span></div><div class="panel-caption" style="margin:2px 0 6px">用平时说话的方式讲你的判断，模型起草后你再到下面逐条核对</div><textarea class="input" id="pro-desc" rows="4" style="width:100%;margin-top:10px" placeholder="用平时说话的方式讲就行，例如：我判断并购估值会先分行业，不同行业看重的点不一样……"></textarea>' +
        '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
          '<button class="button primary" id="pro-gen">让模型起草框架</button>' +
          '' +
          '<span class="panel-caption" style="margin:0" id="pro-hint">下面各部分可以先不管，等草稿出来再逐条核对着改。</span>' +
        "</div></section>" +
      sliceTable(mine, sliceId, nameOfSlice) +
      orphanPanel(orphans, defs, nameOfSlice) +
      lineImportPanel() +
      '<div class="panel-title" style="margin:14px 0 8px"><span>第三步 · 核对与微调</span></div>' +
        '<div id="pro-editor">' +
        boundariesPanel((slice && slice.boundaries) || {}) +
        deliveryPanel(slice || {}) +
        inputsPanel(state) + weightsPanel(state) + thresholdsPanel(state) + signalsPanel(state) +
        rulesPanel(state) + exceptionsPanel(state) + tailPanels(state) +
      "</div>";
    bind(view);
    // Override the handlers bound earlier: saving and drafting write to my slice.
    view.querySelectorAll("[data-confirm-slice]").forEach(function (b) {
      b.onclick = function () { window.poEnableFor = b.dataset.confirmSlice; render(); };
    });
    view.querySelectorAll("[data-cancel-enable]").forEach(function (b) {
      b.onclick = function () { window.poEnableFor = null; render(); };
    });
    view.querySelectorAll("[data-do-enable]").forEach(function (b) {
      b.onclick = async function () {
        var g = view.querySelector("[data-enable-grantor]"), e = view.querySelector("[data-enable-grantee]");
        if (!g || !e || !g.value || !e.value) { alert("请先选择授权方与被授权方。"); return; }
        try {
          var out = await api("/v1/scenario-slices/" + encodeURIComponent(window.poEnableFor) + "/enable",
            { method: "POST", body: JSON.stringify({ grantor_id: g.value, grantee_id: e.value }) });
          window.poEnableFor = null; cache["scenario-slices"] = null; render();
          alert("已启用并生成授权规则：" + ((out && out.authorization_id) || "已生成"));
        } catch (err) {
          alert("启用失败：" + (err && err.message ? err.message : err));
        }
      };
    });
    // The add/remove/type-change handlers used to live only in the old host-based renderer, so the
    // buttons were dead in the live path. Same handlers, bound against view.
    view.querySelectorAll("[data-add]").forEach(function (b) {
      b.onclick = function () {
        var kind = b.dataset.add;
        // Capture this panel's typed values only. The previous version called the full collect() inside a
        // try/catch that swallowed failures, so a collect() error silently discarded what the user had typed.
        try {
          var typed = {};
          view.querySelectorAll("[data-w-cat]").forEach(function (el, i) {
            var key = (el.value || "").trim() || ("行业" + (i + 1));
            typed[key] = typed[key] || {};
            view.querySelectorAll('[data-w-val^="' + i + ':"]').forEach(function (v) {
              var dim = String(v.dataset.wVal || "").split(":")[1];
              var num = parseFloat(v.value);
              if (dim && !isNaN(num)) typed[key][dim] = num;
            });
          });
          if (Object.keys(typed).length) state.industry_weights = typed;
        } catch (e) {
          alert("读取权重表出错，已中止本次操作（你的输入没有被丢弃）：" + (e && e.message ? e.message : e));
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
        else if (what === "log") state.adjustment_log.splice(n, 1);
        render();
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
      b.onclick = function () { sliceId = b.dataset.pickSlice; state = null; render(); };
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
    view.querySelectorAll("[data-confirm-slice]").forEach(function (b) {
      b.onclick = async function () {
        await api("/v1/scenario-slices/" + encodeURIComponent(b.dataset.confirmSlice),
          { method: "PATCH", body: JSON.stringify({ status: "confirmed" }) });
        cache["scenario-slices"] = null; render();
      };
    });
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
  }
  function collect() {
    var f = ensureShape({ framework_version: state.framework_version, industry_map: clone(state.industry_map) });
    var q = function (a) { return document.querySelectorAll(a); };
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
    q("[data-sig-name]").forEach(function (el) {
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
      f.signals.push({ name: name, when: when });
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
        // Capture this panel's typed values only. The previous version called the full collect() inside a
        // try/catch that swallowed failures, so a collect() error silently discarded what the user had typed.
        try {
          var typed = {};
          view.querySelectorAll("[data-w-cat]").forEach(function (el, i) {
            var key = (el.value || "").trim() || ("行业" + (i + 1));
            typed[key] = typed[key] || {};
            view.querySelectorAll('[data-w-val^="' + i + ':"]').forEach(function (v) {
              var dim = String(v.dataset.wVal || "").split(":")[1];
              var num = parseFloat(v.value);
              if (dim && !isNaN(num)) typed[key][dim] = num;
            });
          });
          if (Object.keys(typed).length) state.industry_weights = typed;
        } catch (e) {
          alert("读取权重表出错，已中止本次操作（你的输入没有被丢弃）：" + (e && e.message ? e.message : e));
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

  window.POPro = { renderSlices: renderSlices };
})();


  // -- Unassigned slices: their scenario was deleted, so they must be recoverable --
  // -- Line-based entry: one line per item, with the format shown inline --
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
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title"><span>方式二 · 一行一条自己写</span></div>' +
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
          '<button class="button" data-pick-slice="' + esc(x.id) + '">选中</button> ' +
          (x.status === "confirmed"
            ? '<button class="button" data-unconfirm-slice="' + esc(x.id) + '">退回草稿</button> '
            : '<button class="button primary" data-confirm-slice="' + esc(x.id) + '">确认并启用…</button> ') +
          (window.poEnableFor === x.id ? granteePicker(principals) : "") +
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
  alert("操作失败：" + msg);
});

// -- Choose who may call this slice: the grantor (you) and the grantee (the caller) must both be principals --
function granteePicker(principals) {
  var list = principals || [];
  if (!list.length) {
    return '<div class="panel-caption" style="margin-top:6px">还没有主体。请先到「主体」菜单建两个：本人 与 调用方（例如 法智AI），类型选 person</div>';
  }
  var options = list.map(function (pp) {
    return '<option value="' + esc(pp.id) + '">' + esc(pp.display_name_zh || pp.id) + "</option>";
  }).join("");
  return '<div class="panel-caption" style="margin-top:6px;display:flex;gap:6px;align-items:center;flex-wrap:wrap">' +
    '<span>授权方</span><select class="select" data-enable-grantor>' + options + "</select>" +
    '<span>被授权方（调用方）</span><select class="select" data-enable-grantee>' + options + "</select>" +
    '<button class="button primary" data-do-enable>确认启用</button>' +
    '<button class="button" data-cancel-enable>取消</button></div>';
}
