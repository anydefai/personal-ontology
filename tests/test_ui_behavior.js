// 界面行为测试：在 DOM 替身里【真的跑一遍】renderSlices 与 polishPanels。
// 目的：覆盖此前只有肉眼能发现的问题 —— 函数未定义、面板整块消失、面板没被编号、互斥展开失效。
const fs = require("fs"), path = require("path"), vm = require("vm");
const { El, makeDocument } = require("./dom_stub.js");
const ROOT = path.resolve(__dirname, "..");
const src = fs.readFileSync(path.join(ROOT, "web", "pro.js"), "utf8");

const RESULTS = [];
function check(label, cond, detail) {
  console.log((cond ? "  ✔ " : "  ✗ ") + label + (cond ? "" : (detail === undefined ? "" : " — " + detail)));
  RESULTS.push(!!cond);
}

const MODELS = [
  { id: "scorecard_v1", version: "1", label_zh: "评分卡（证据累积）", applicable: "证据累积型判断",
    not_applicable: ["需要顺序分支的判断"], input_contract: { fields: { inputs: "x", signals: "x", industry_weights: "x", thresholds: "x", combination_rules: "x", score_bands: "x", citations: "x" } } },
  { id: "requirements_v1", version: "1", label_zh: "要件逻辑", applicable: "要件型判断",
    not_applicable: ["加权排序"], input_contract: { fields: { inputs: "x", signals: "x", combination_rules: "x", citations: "x" } } },
  { id: "formula_v1", version: "1", label_zh: "领域公式", applicable: "有明确计算式的判断",
    not_applicable: ["只有经验权重"], input_contract: { fields: { inputs: "x", formulas: "x", bands: "x", citations: "x" } } },
];

function buildView() {
  const doc = makeDocument();
  const view = new El("div"); doc.body.appendChild(view);
  return { doc, view };
}

// 复核面板（真实页面由 renderSlices 的模板生成；替身不解析 innerHTML，所以渲染之后手工放进去）
function addReviewPanels(view) {
  const ed = new El("div"); ed.attributes.id = "pro-editor"; view.appendChild(ed);
  [["需要调用方提交的信息", "inputs"], ["不同行业的侧重", "industry_weights"], ["我观察什么", "signals"],
   ["几个观察点一起出现时", "combination_rules"], ["例外情况", "exception_rules"], ["我的依据", "citations"],
   ["打分线", "score_bands"], ["公式", "formulas"], ["分档", "bands"], ["对外调用的边界", "boundaries"]].forEach((pair) => {
    const sec = new El("section"); sec.className = "panel";
    const h = new El("div"); h.className = "panel-title"; const sp = new El("span"); sp.textContent = pair[0];
    h.appendChild(sp); sec.appendChild(h);
    const row = new El("div"); row.className = "pro-row"; sec.appendChild(row);
    ed.appendChild(sec);
  });
  return ed;
}

function makeCtx(doc, { catalogFails }) {
  const ctx = {
    console, setTimeout, clearTimeout, setInterval, clearInterval,
    document: doc, alert: (m) => { throw new Error("alert: " + m); }, confirm: () => true,
    api: async (u) => {
      const s = String(u);
      if (s.indexOf("/v1/judgment-models") >= 0) {
        if (catalogFails) throw new Error("401");
        return { default: MODELS[0].id, models: MODELS };
      }
      if (s.indexOf("/v1/scenario-slices") >= 0) {
        return [{ id: "s.1", status: "confirmed", scenario_definition_id: "d.1",
                  scenario_profile: { kind: "professional" },
                  analysis: { title: "我的切片" },
                  framework: { model: "scorecard_v1",
                               inputs: [{ name: "市盈率", type: "number" }],
                               thresholds: { base: 1.3, adjustments: [] },
                               signals: [{ name: "贵", dimension: "财务", when: { "市盈率": { op: "gt", value: 43.5 } } }],
                               industry_map: { "新能源": "科技" }, industry_weights: { "科技": { "财务": 0.4 } } } }];
      }
      return {};
    },
    esc: (x) => String(x == null ? "" : x).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])),
    fieldLabel: (row, zh, en) => (row && (row[zh] || row[en])) || "",
    load: async (what) => {
      const w = String(what);
      if (w.indexOf("scenario-definitions") >= 0) return [{ id: "d.1", display_name_zh: "测试场景" }];
      if (w.indexOf("scenario-slices") >= 0) {
        return [{ id: "s.1", status: "draft", scenario_definition_id: "d.1",
                  scenario_profile: { kind: "professional" }, analysis: { title: "我的切片" },
                  framework: { model: "scorecard_v1", inputs: [{ name: "市盈率", type: "number" }],
                               thresholds: { base: 1.3, adjustments: [] },
                               signals: [{ name: "贵", dimension: "财务", when: { "市盈率": { op: "gt", value: 43.5 } } }],
                               industry_map: { "新能源": "科技" }, industry_weights: { "科技": { "财务": 0.4 } } } }];
      }
      return [];
    },
    isProSlice: () => true,
    displayName: () => "",
    proModeButtons: () => '<div class="pro-mode-buttons">模式</div>',
    titleBlock: (a, b) => "<h1>" + b + "</h1>",
    hint: (t) => '<div class="panel-caption">' + t + "</div>",
    row: (h) => '<div class="pro-row">' + h + "</div>",
    input: (v, a) => '<input ' + (a || "") + ">",
    del: (w) => '<button data-del="' + w + '">x</button>',
    clone: (o) => JSON.parse(JSON.stringify(o)),
    requestAnimationFrame: (fn) => setTimeout(fn, 0),
  };
  ctx.window = {
    document: doc, addEventListener: () => {}, removeEventListener: () => {},
    location: { href: "http://127.0.0.1:8765/", search: "", hash: "" },
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    requestAnimationFrame: ctx.requestAnimationFrame, matchMedia: () => ({ matches: false, addListener: () => {} }),
    CSS: { escape: (x) => String(x) }, poProSlice: { id: "s.1", framework: {} }, poJudgmentModel: null,
  };
  ctx.localStorage = ctx.window.localStorage;
  ctx.sessionStorage = ctx.window.sessionStorage;
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  return ctx;
}

function textOf(view) {
  let out = view.innerHTML || "";
  view.querySelectorAll("*").forEach((e) => { out += " " + (e.innerHTML || "") + " " + (e.textContent || ""); });
  return out;
}

(async () => {
  // ① 加载不抛错（抓 xxx is not defined 这类）
  let doc = makeDocument();
  let ctx = makeCtx(doc, { catalogFails: false });
  let err = null;
  try { vm.runInContext(src, ctx); } catch (e) { err = e; }
  check("pro.js 能在 DOM 替身里加载（不抛错）", !err, err && err.message);
  if (err) { process.exit(1); }

  // ② renderSlices 真跑一遍：三种方式、第二步标题、判定模型面板都要出现
  const v1 = buildView();
  ctx = makeCtx(v1.doc, { catalogFails: false });
  const c1 = ctx;
  vm.runInContext(src, ctx);
  ctx.window.poProSlice = { id: "s.1", framework: {} };
  try { await ctx.window.POPro.renderSlices(v1.view); check("renderSlices 能跑完（不抛错）", true); }
  catch (e) { check("renderSlices 能跑完（不抛错）", false, e.message); }
  const t1 = textOf(v1.view);
  check("页面上出现三种生成方式", /方式一/.test(t1) && /方式二/.test(t1) && /方式三/.test(t1));
  check("页面上出现第二步标题", /第二步/.test(t1));
  check("页面上出现判定模型面板（含下拉）", /判定模型/.test(t1) && /pro-model/.test(t1));
  check("第一步有「另存为新切片」按钮（DOM 级）", /另存为新切片/.test(t1) && /pro-dup-slice/.test(t1), "没找到按钮");
  // 这个 bug 真的报错过：切换模型时 Uncaught ReferenceError: models is not defined
  // —— 切换处理在另一个作用域，拿不到 renderSlices 的局部变量 models。
  // 现在渲染时把每个模型的说明放进 window.poModelDesc，切换时直接取。
  const descMap = (c1.window && c1.window.poModelDesc) || {};
  check("渲染后 window.poModelDesc 里有三个模型（切换时直接取，不依赖局部变量）",
        Object.keys(descMap).length >= 3 && /适合/.test(descMap["requirements_v1"] || ""),
        "键：" + Object.keys(descMap).join(","));
  check("切换处理不再引用局部变量 models（防同类作用域报错）",
        !/var pickedModel = \(models/.test(src.slice(src.indexOf("pro-model"))), "仍在引用 models");
  check("切换处理用的是 descHtml（来自全局说明表）", /desc\.innerHTML = descHtml/.test(src), "没找到");
  // The user reported that parsing right after creating a slice said to select one first.
  // The cause was that parsing read window.poProSlice, which the real page never assigns and only this stub set,
  // instead of the page's own sliceId, so this assertion keeps it from regressing.
  // 那段解析处理在 IIFE 之外，看不到 IIFE 内的 sliceId（改回读局部变量会 ReferenceError），
  // 所以渲染时把当前切片 id 发布到 window.poCurrentSliceId —— 这条断言它真的被发布了。
  check("渲染时把当前切片 id 发布到 window.poCurrentSliceId（DOM 级，切换后解析才不会误报未选切片）",
        (c1.window && c1.window.poCurrentSliceId) === "s.1", "实际值：" + String(c1.window && c1.window.poCurrentSliceId));
  check("解析处理读 window.poCurrentSliceId，且不再读从未赋值的 window.poProSlice",
        !/window\.poProSlice && window\.poProSlice\.id/.test(src) && /var sid = window\.poCurrentSliceId \|\| ""/.test(src),
        "读取来源不对");
  // 标题同样不能停在旧模型上（用户报过："判定模型 · 评分卡（证据累积） v1"不跟着切换变）
  const titleMap = (c1.window && c1.window.poModelTitle) || {};
  check("渲染后标题表里有三个模型", Object.keys(titleMap).length >= 3, "键：" + Object.keys(titleMap).join(","));
  check("切换处理会同时更新标题", /titleEl\.textContent = titleText/.test(src), "没找到");
  // 切换模型时说明必须跟着变；且不能靠重画整页（那会弄丢用户正在填的内容）
  check("说明块有 id 且切换时会被就地更新（源码级）",
        /id="pro-model-desc"/.test(src) && /desc\.innerHTML = /.test(src), "没有就地更新逻辑");
  check("过时文案「目前只有这一个模型」已删除", !/目前只有这一个模型/.test(src), "还留着过时文案");
  // 说明：我实测过 —— 草稿与已确认两种状态下 renderSlices 都没渲染出信号输入行（只有面板标题），
  // 说明编辑区走的是另一条路径，所以这一条仍是源码级。真正覆盖"分值输入被渲染出来"的是
  // tests/test_professional_render.py 里直接调用 signalsPanel 的两条断言。
  check("信号行里有命中分值输入（源码级）", /data-sig-score/.test(src), "源码里没有 data-sig-score");
  check("保存时会读分值并校验范围（源码级）", /sig\.score_value = sv/.test(src) && /命中分值要在 0 到 1 之间/.test(src));
  check("「判断的基准线」提示里说明了 × 表示乘法", /表示乘法/.test(t1), "没找到乘法说明");

  // ③ 目录接口失败（例如会话 401）时，判定模型面板【不能消失】
  const v2 = buildView();
  ctx = makeCtx(v2.doc, { catalogFails: true });
  vm.runInContext(src, ctx);
  ctx.window.poProSlice = { id: "s.1", framework: {} };
  try { await ctx.window.POPro.renderSlices(v2.view); } catch (e) {}
  const t2 = textOf(v2.view);
  check("目录 401 时判定模型面板仍在（不整块消失）", /判定模型/.test(t2), "没找到");
  check("并给出明确提示（内置清单 + 登录后读完整说明）", /内置显示/.test(t2), "没找到提示");
  // 替身不解析 innerHTML，所以直接看渲染出来的字符串里有没有选项
  const hasSelect = /id="pro-model"/.test(t2);
  const optionCount = (t2.match(/<option value="[^"]*"[^>]*>/g) || []).length;
  // 目录拿不到时也必须是【三个】模型，而不是只剩默认那一个（用户报过这个问题）
  check("目录 401 时下拉里仍是三个模型（不是只剩一个）", hasSelect && optionCount >= 3,
        "选择框 " + (hasSelect ? "有" : "没有") + " · 选项 " + optionCount + " 个");

  // ④ polishPanels 能跑完并给条目编号（面板会被搬到分组容器里，所以在 view 里找）
  const v3 = buildView();
  ctx = makeCtx(v3.doc, { catalogFails: false });
  vm.runInContext(src, ctx);
  ctx.window.poProSlice = { id: "s.1", framework: {} };
  try { await ctx.window.POPro.renderSlices(v3.view); } catch (e) {}
  addReviewPanels(v3.view);                     // 渲染之后再放（替身的 innerHTML 会清空子节点）
  try { ctx.window.POPro.polishPanels(v3.view); check("polishPanels 能跑完（不抛错）", true); }
  catch (e) { check("polishPanels 能跑完（不抛错）", false, e.message); }
  const nums = v3.view.querySelectorAll(".pro-num");
  check("面板条目被编号（至少 1 个）", nums.length >= 1, "编号 " + nums.length + " 个");
  // 替身不支持后代选择器（.pro-toc a），所以检查目录容器本身与它的子项
  const toc = v3.view.querySelector(".pro-toc");
  check("左侧目录生成了（且里面有条目）", !!toc && toc.children.length >= 1,
        toc ? ("子项 " + toc.children.length + " 个") : "没有 .pro-toc");

  const ok = RESULTS.filter(Boolean).length;
  console.log("\n===== " + ok + "/" + RESULTS.length + " 项通过 =====");
  process.exit(ok === RESULTS.length ? 0 : 1);
})();
