const fs=require("fs"),path=require("path"),vm=require("vm");
const {El,makeDocument}=require(process.cwd()+"/tests/dom_stub.js");
const src=fs.readFileSync(path.join(process.cwd(),"web","pro.js"),"utf8");
const MODELS=[{id:"scorecard_v1",version:"1",label_zh:"评分卡",applicable:"x",not_applicable:[],input_contract:{fields:{inputs:"x",signals:"x",thresholds:"x"}}}];
const doc=makeDocument(); const view=new El("div"); doc.body.appendChild(view);
// 复核面板 + 「加一条」按钮（与真实页面同属性）
let ed=new El("div"); ed.attributes.id="pro-editor"; view.appendChild(ed);
[["我观察什么","signal"],["例外情况","exception"],["我的依据","citation"],["几个观察点一起出现时","rule"],["哪个观察点更重要","priority"],["需要调用方提交的信息","input"]].forEach(function(p){
  const sec=new El("section"); sec.className="panel";
  const h=new El("div"); h.className="panel-title"; const sp=new El("span"); sp.textContent=p[0];
  h.appendChild(sp); sec.appendChild(h);
  const row=new El("div"); row.className="pro-row"; sec.appendChild(row);
  const btn=new El("button"); btn.attributes["data-add"]=p[1]; sec.appendChild(btn);
  ed.appendChild(sec);
});
const ctx={console,setTimeout,clearTimeout,setInterval,clearInterval,document:doc,
  alert:(m)=>{ctx.__alert=String(m);}, confirm:()=>true,
  api:async(u)=>{const s=String(u);
    if(s.indexOf("/v1/judgment-models")>=0) return {default:"scorecard_v1",models:MODELS};
    if(s.indexOf("/v1/scenario-slices")>=0) return [];
    return {};},
  esc:(x)=>String(x==null?"":x),fieldLabel:()=>"",
  load:async(w)=>(String(w).indexOf("scenario-definitions")>=0?[{id:"d.1",display_name_zh:"场景"}]:[]),
  isProSlice:()=>true,displayName:()=>"",proModeButtons:()=>"",titleBlock:(a,b)=>"<h1>"+b+"</h1>",
  hint:(t)=>"<div>"+t+"</div>",row:(h)=>"<div>"+h+"</div>",input:()=>"<input>",del:()=>"",
  clone:(o)=>JSON.parse(JSON.stringify(o)),requestAnimationFrame:(fn)=>setTimeout(fn,0),
  render:()=>{ctx.__rendered=(ctx.__rendered||0)+1;}};
ctx.window={document:doc,addEventListener:()=>{},removeEventListener:()=>{},location:{},
  localStorage:{getItem:()=>null,setItem:()=>{}},sessionStorage:{getItem:()=>null,setItem:()=>{}},
  requestAnimationFrame:ctx.requestAnimationFrame,CSS:{escape:(x)=>x},poProSlice:{id:"s.1",framework:{}}};
ctx.globalThis=ctx; vm.createContext(ctx); vm.runInContext(src,ctx);
(async()=>{
  try { await ctx.window.POPro.renderSlices(view); } catch(e) { console.log("  renderSlices 抛错:", e.message); }
  // 渲染之后再放带按钮的面板（innerHTML 会清空子节点）
  const ed2 = new El("div"); ed2.attributes.id = "pro-editor"; view.appendChild(ed2);
  [["我观察什么","signal"],["例外情况","exception"],["我的依据","citation"],["几个观察点一起出现时","rule"],["哪个观察点更重要","priority"],["需要调用方提交的信息","input"]].forEach(function(p){
    const sec=new El("section"); sec.className="panel";
    const h=new El("div"); h.className="panel-title"; const sp=new El("span"); sp.textContent=p[0];
    h.appendChild(sp); sec.appendChild(h);
    const row=new El("div"); row.className="pro-row"; sec.appendChild(row);
    const btn=new El("button"); btn.attributes["data-add"]=p[1]; sec.appendChild(btn);
    ed2.appendChild(sec);
  });
  ed = ed2;
  // 关键：面板必须在 render 之后再放（替身的 innerHTML 会清空子节点），
  // 然后调用公开的绑定函数 —— 这样才是真的在测那条路。
  try { ctx.window.poBindRowButtons(view); } catch(e) { console.log("  poBindRowButtons 抛错:", e.message); }
  const btns = ed.querySelectorAll("button");
  console.log("  找到按钮:", btns.length, "个；绑定了 onclick 的:", btns.filter(b=>typeof b.onclick==="function").length);
  for (const b of btns) {
    const kind = b.attributes["data-add"] || "?";
    if (typeof b.onclick !== "function") { console.log("   [" + kind + "] 没有绑定 ✗"); continue; }
    ctx.__alert = null;
    try { await b.onclick(); console.log("   [" + kind + "] 点击正常 ✓" + (ctx.__alert ? ("（弹出：" + ctx.__alert.slice(0,60) + "）") : "")); }
    catch (e) { console.log("   [" + kind + "] 点击抛错 ✗:", e.message); }
  }
})();
// 用途：把「加一条 XXX」这条路真的跑一遍（此前的界面行为测试里没有这些按钮，所以这条路从未被测过）。
//   node tests/probe_add_buttons.js
// 期望：每个 data-add 按钮都绑定了 onclick，且点击不抛错。
