/* 专业判断侧：技能框架的建模界面（第一步~第四步）。
 *
 * 与 app.js 的关系：本文件只做「专业模式 · 场景切片」这一页，
 * 通过 window.POPro.renderSlices(view) 被 app.js 调用；其余能力（判定、回测）
 * 复用 app.js 里已有的函数（api / load / esc / titleBlock / cache / render 等）。
 *
 * 编辑方式：先把框架读进内存，改动写回内存；保存时按内存重建 framework 并 PATCH。
 */
(function () {
  "use strict";

  var state = null;          // 当前编辑中的框架
  var defId = null;          // 当前场景定义 id
  var lastDraft = "";        // 上次生成草稿用的描述

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
  function input(value, attrs) {
    return '<input class="input" ' + (attrs || "") + ' value="' + esc(value == null ? "" : String(value)) + '">';
  }
  function del(what) { return '<button class="button" data-del="' + what + '">删除</button>'; }

  function inputsPanel(f) {
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">1 · 输入定义</div>' +
      '<div class="panel-caption">判定时要提供的字段。类型选 enum 时，用逗号分隔枚举值。</div>' +
      f.inputs.map(function (i, n) {
        return row(input(i.name, 'data-in-name="' + n + '" placeholder="字段名"') +
          '<select class="select" data-in-type="' + n + '">' +
            ["string", "number", "enum"].map(function (t) {
              return '<option value="' + t + '"' + (i.type === t ? " selected" : "") + ">" + t + "</option>";
            }).join("") + "</select>" +
          input((i.values || []).join(","), 'data-in-values="' + n + '" placeholder="枚举值，逗号分隔"') +
          del("input:" + n) + "</div>");
      }).join("") +
      '<button class="button" data-add="input">＋ 加一个字段</button></section>';
  }

  function weightsPanel(f) {
    var cats = Object.keys(f.industry_weights);
    var dims = {};
    cats.forEach(function (c) { Object.keys(f.industry_weights[c] || {}).forEach(function (d) { dims[d] = 1; }); });
    var dimList = Object.keys(dims);
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">2 · 行业权重表</div>' +
      '<div class="panel-caption">每个行业类别一行；数值没把握就留均分，之后随时能改。</div>' +
      (cats.length ? '<div class="pro-grid" style="grid-template-columns:1.2fr repeat(' + Math.max(dimList.length, 1) + ',1fr) 0.6fr">' +
        "<div>类别</div>" + (dimList.length ? dimList.map(function (d) { return "<div>" + esc(d) + "</div>"; }).join("") : "<div>维度</div>") + "<div></div>" +
        cats.map(function (c, n) {
          return "<div>" + input(c, 'data-w-cat="' + n + '"') + "</div>" +
            (dimList.length ? dimList.map(function (d) {
              return "<div>" + input((f.industry_weights[c] || {})[d], 'data-w-val="' + n + ":" + esc(d) + '"') + "</div>";
            }).join("") : "<div>" + input("", 'data-w-val="' + n + ':weight"') + "</div>") +
            "<div>" + del("weights:" + n) + "</div>";
        }).join("") + "</div>" : '<div class="panel-caption">还没有行业类别。</div>') +
      '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">' +
      '<button class="button" data-add="weight-cat">＋ 加一个类别</button>' +
      '<button class="button" data-add="weight-dim">＋ 加一个权重维度</button></div></section>';
  }

  function thresholdsPanel(f) {
    var th = f.thresholds || {};
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">3 · 动态阈值</div>' +
      '<div class="panel-caption">基准倍数加上按条件调整的量；每项都能写理由（会进调整记录）。</div>' +
      row('<span class="field-label" style="min-width:80px">基准</span>' + input(th.base, 'data-th-base type="number" step="any"')) +
      (th.adjustments || []).map(function (a, n) {
        var cond = a.condition || {}; var k = Object.keys(cond)[0] || "";
        return row(input(k, 'data-th-field="' + n + '" placeholder="条件字段"') +
          input(cond[k], 'data-th-value="' + n + '" placeholder="值"') +
          input(a.delta, 'data-th-delta="' + n + '" placeholder="增减" type="number" step="any"') +
          input(a.reason, 'data-th-reason="' + n + '" placeholder="理由"') +
          del("threshold:" + n));
      }).join("") +
      '<button class="button" data-add="threshold">＋ 加一条阈值调整</button></section>';
  }

  function rulesPanel(f) {
    var names = f.signals.map(function (s) { return s.name; });
    function checks(selected, attr, n) {
      return names.map(function (nm) {
        var on = (selected || []).indexOf(nm) >= 0;
        return '<label class="pro-check"><input type="checkbox" ' + attr + '="' + n + '" value="' + esc(nm) + '"' + (on ? " checked" : "") + ">" + esc(nm) + "</label>";
      }).join("") || '<span class="muted">（先定义信号）</span>';
    }
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">4 · 风险交叉验证（组合规则）</div>' +
      '<div class="panel-caption">勾选要同时成立的信号，再写结论与严重度。</div>' +
      (f.combination_rules || []).map(function (r, n) {
        return row('<div class="pro-checks">' + checks(r.all_of, "data-cr-sig", n) + "</div>" +
          input(r.conclusion, 'data-cr-conc="' + n + '" placeholder="结论"') +
          '<select class="select" data-cr-sev="' + n + '">' +
            ["低", "中", "高", "极高"].map(function (s) { return '<option' + (r.severity === s ? " selected" : "") + ">" + s + "</option>"; }).join("") +
          "</select>" + del("rule:" + n));
      }).join("") +
      '<button class="button" data-add="rule">＋ 加一条组合规则</button></section>' +
      '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">5 · 信号</div>' +
      '<div class="panel-caption">信号 = 一条布尔判断；可以引用"与动态阈值比较"。</div>' +
      (f.signals || []).map(function (s, n) {
        var when = s.when || {}; var field = Object.keys(when)[0] || "";
        var spec = when[field] || {};
        return row(input(s.name, 'data-sig-name="' + n + '" placeholder="信号名"') +
          input(field, 'data-sig-field="' + n + '" placeholder="字段"') +
          '<select class="select" data-sig-op="' + n + '">' +
            ["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "contains"].map(function (o) {
              return '<option value="' + o + '"' + (spec.op === o ? " selected" : "") + ">" + o + "</option>";
            }).join("") + "</select>" +
          input(typeof spec.value === "object" ? JSON.stringify(spec.value) : spec.value, 'data-sig-value="' + n + '" placeholder="值 / 或 {\"ref\":\"字段\",\"times\":\"threshold\"}"') +
          del("signal:" + n));
      }).join("") +
      '<button class="button" data-add="signal">＋ 加一个信号</button></section>';
  }

  function exceptionsPanel(f) {
    var names = f.signals.map(function (s) { return s.name; });
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">6 · 例外规则</div>' +
      '<div class="panel-caption">专业判断里最难的部分：什么情况下改写上面的常规判断。</div>' +
      (f.exception_rules || []).map(function (r, n) {
        var cond = r.condition || {}; var ov = r.override || {};
        var sigs = cond.all_signals || [];
        return row('<div class="pro-checks">' + names.map(function (nm) {
            return '<label class="pro-check"><input type="checkbox" data-ex-sig="' + n + '" value="' + esc(nm) + '"' + (sigs.indexOf(nm) >= 0 ? " checked" : "") + ">" + esc(nm) + "</label>";
          }).join("") + "</div>" +
          '<select class="select" data-ex-kind="' + n + '">' +
            [["reduce_weight", "降权"], ["adjust_threshold", "调阈值"], ["force_conclusion", "直接判定"]].map(function (k) {
              return '<option value="' + k[0] + '"' + (ov.kind === k[0] ? " selected" : "") + ">" + k[1] + "</option>";
            }).join("") + "</select>" +
          input(ov.target, 'data-ex-target="' + n + '" placeholder="目标字段/信号"') +
          input(ov.factor, 'data-ex-factor="' + n + '" placeholder="系数"') +
          input(ov.conclusion, 'data-ex-conc="' + n + '" placeholder="直接判定的结论"') +
          input(r.reason, 'data-ex-reason="' + n + '" placeholder="理由"') + del("exception:" + n));
      }).join("") +
      '<button class="button" data-add="exception">＋ 加一条例外规则</button></section>' +
      '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">7 · 信号优先级</div>' +
      '<div class="panel-caption">数字越小越重要；高优先级可用于裁决组合规则。</div>' +
      (f.signal_priority || []).map(function (p, n) {
        return row('<select class="select" data-pr-sig="' + n + '">' + names.map(function (nm) {
            return '<option' + (p.signal === nm ? " selected" : "") + ">" + esc(nm) + "</option>";
          }).join("") + "</select>" + input(p.priority, 'data-pr-val="' + n + '" type="number"') + del("priority:" + n));
      }).join("") +
      '<button class="button" data-add="priority">＋ 加一条优先级</button></section>';
  }

  function adjustLogPanel(f) {
    var log = f.adjustment_log || [];
    return '<section class="panel" style="padding:16px;margin-bottom:12px">' +
      '<div class="panel-title">调整记录（第三步 · 专业性的来源）</div>' +
      '<div class="panel-caption">每处改动都记下理由；这是你的经验沉淀，也是调用方判断可信度的依据。</div>' +
      (log.length ? log.map(function (a, n) {
        return row(input(a.step, 'data-log-step="' + n + '" placeholder="改了什么"') +
          input(a.reason, 'data-log-reason="' + n + '" placeholder="为什么"') + del("log:" + n));
      }).join("") : '<div class="panel-caption">还没有记录。上面每处改动都可以在保存前记一条。</div>') +
      '<button class="button" data-add="log">＋ 记一条调整</button></section>';
  }

  async function renderSlices(view) {
    var defs = await load("scenario-definitions");
    if (!defId || !defs.some(function (d) { return d.id === defId; })) defId = defs[0] ? defs[0].id : null;
    var def = defs.filter(function (d) { return d.id === defId; })[0] || null;
    if (!state || state.__defId !== defId) {
      state = ensureShape(def && def.framework ? def.framework : emptyFramework());
      state.__defId = defId;
    }
    var opts = defs.map(function (d) {
      return '<option value="' + esc(d.id) + '"' + (d.id === defId ? " selected" : "") + ">" +
        esc(fieldLabel(d, "display_name_zh", "display_name_en")) + "</option>";
    }).join("");
    view.innerHTML = proModeButtons() +
      titleBlock("SKILL FRAMEWORK", "技能框架", "先用一段话描述你的判断方式，让模型起草；再逐项改成你自己的——第三步的调整才是专业性所在。") +
      '<section class="panel" style="padding:16px;margin-bottom:12px">' +
        '<div class="panel-title">第一步 · 选场景并描述</div>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0">' +
          '<select class="select" id="pro-def" style="max-width:320px">' + (opts || '<option value="">暂无专业场景</option>') + "</select>" +
          '<span class="badge">' + (def && def.framework ? "已有框架" : "尚未配置框架") + "</span>" +
        "</div>" +
        '<textarea class="input" id="pro-desc" rows="4" style="width:100%" placeholder="例如：我判断并购估值会先分行业，不同行业权重不同；再按行业周期和监管环境调整阈值……"></textarea>' +
        '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">' +
          '<button class="button primary" id="pro-gen">生成框架草稿</button>' +
          '<button class="button" id="pro-save">保存框架</button>' +
          '<span class="panel-caption" style="margin:0" id="pro-hint"></span>' +
        "</div></section>" +
      "<div id=\x22pro-editor\x22>" +
        inputsPanel(state) + weightsPanel(state) + thresholdsPanel(state) +
        rulesPanel(state) + exceptionsPanel(state) + adjustLogPanel(state) +
      "</div>";
    bind(view);
  }

  function collect() {
    var f = ensureShape({ framework_version: state.framework_version, industry_map: clone(state.industry_map) });
    var q = function (a) { return document.querySelectorAll(a); };
    f.inputs = [];
    q("[data-in-name]").forEach(function (el) {
      var n = el.dataset.inName, name = el.value.trim(); if (!name) return;
      var type = (document.querySelector('[data-in-type="' + n + '"]') || {}).value || "string";
      var vals = ((document.querySelector('[data-in-values="' + n + '"]') || {}).value || "").split(",").map(function (x) { return x.trim(); }).filter(Boolean);
      var item = { name: name, type: type }; if (type === "enum" && vals.length) item.values = vals;
      f.inputs.push(item);
    });
    f.industry_weights = {};
    var cats = q("[data-w-cat]");
    cats.forEach(function (el, i) {
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
      var n = el.dataset.sigName, name = el.value.trim(), field = ((document.querySelector('[data-sig-field="' + n + '"]') || {}).value || "").trim();
      if (!name || !field) return;
      var op = (document.querySelector('[data-sig-op="' + n + '"]') || {}).value || "eq";
      var raw = (document.querySelector('[data-sig-value="' + n + '"]') || {}).value || "";
      var val; try { val = JSON.parse(raw); } catch (e) { val = /^-?\d+(\.\d+)?$/.test(raw) ? Number(raw) : raw; }
      var when = {}; when[field] = { op: op, value: val };
      f.signals.push({ name: name, when: when });
    });
    f.combination_rules = [];
    var crSeen = {};
    q("[data-cr-conc]").forEach(function (el) { crSeen[el.dataset.crConc] = 1; });
    Object.keys(crSeen).forEach(function (n) {
      var sigs = [];
      q('[data-cr-sig="' + n + '"]').forEach(function (c) { if (c.checked) sigs.push(c.value); });
      var conc = ((document.querySelector('[data-cr-conc="' + n + '"]') || {}).value || "").trim();
      if (!sigs.length || !conc) return;
      f.combination_rules.push({ all_of: sigs, conclusion: conc,
        severity: (document.querySelector('[data-cr-sev="' + n + '"]') || {}).value || "中" });
    });
    f.exception_rules = [];
    var exSeen = {}; q("[data-ex-kind]").forEach(function (el) { exSeen[el.dataset.exKind] = 1; });
    Object.keys(exSeen).forEach(function (n) {
      var sigs = [];
      q('[data-ex-sig="' + n + '"]').forEach(function (c) { if (c.checked) sigs.push(c.value); });
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
      var n = el.dataset.logStep, step = el.value.trim();
      if (!step) return;
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
    host.querySelectorAll("[data-add]").forEach(function (b) {
      b.onclick = function () {
        var kind = b.dataset.add;
        if (kind === "input") state.inputs.push({ name: "", type: "string" });
        else if (kind === "weight-cat") state.industry_weights["新类别" + (Object.keys(state.industry_weights).length + 1)] = { weight: 0.25 };
        else if (kind === "weight-dim") Object.keys(state.industry_weights).forEach(function (c) {
          var w = state.industry_weights[c]; if (!("weight" in w) || Object.keys(w).length === 1) w["维度" + (Object.keys(w).length + 1)] = 0;
        });
        else if (kind === "threshold") state.thresholds.adjustments.push({ condition: {}, delta: 0, reason: "" });
        else if (kind === "signal") state.signals.push({ name: "", when: {} });
        else if (kind === "rule") state.combination_rules.push({ all_of: [], conclusion: "", severity: "中" });
        else if (kind === "exception") state.exception_rules.push({ condition: { all_signals: [] }, override: { kind: "adjust_threshold" }, reason: "" });
        else if (kind === "priority") state.signal_priority.push({ signal: state.signals[0] ? state.signals[0].name : "", priority: state.signal_priority.length + 1 });
        else if (kind === "log") state.adjustment_log.push({ step: "", reason: "" });
        state = collect(); render();
      };
    });
    host.querySelectorAll("[data-del]").forEach(function (b) {
      b.onclick = function () {
        state = collect();
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
    var gen = host.querySelector("#pro-gen");
    if (gen) gen.onclick = async function () {
      var desc = (host.querySelector("#pro-desc") || {}).value || "";
      lastDraft = desc;
      var hint = host.querySelector("#pro-hint"); if (hint) hint.textContent = "正在让模型起草…";
      var out = await api("/v1/scenario-definitions/" + encodeURIComponent(defId) + "/draft", { method: "POST", body: JSON.stringify({ description: desc }) });
      if (out && out.framework) { state = ensureShape(out.framework); state.__defId = defId; render(); }
      else if (hint) { hint.textContent = "生成失败：" + esc((out && (out.detail || out.error)) || "请检查模型服务"); }
    };
    var save = host.querySelector("#pro-save");
    if (save) save.onclick = async function () {
      var f = collect();
      await api("/v1/scenario-definitions/" + encodeURIComponent(defId), { method: "PATCH", body: JSON.stringify({ framework: f }) });
      cache["scenario-definitions"] = null; state = null; render();
    };
    var hint = host.querySelector("#pro-hint");
    if (hint && lastDraft) hint.textContent = "";
  }

  window.POPro = { renderSlices: renderSlices };
})();
