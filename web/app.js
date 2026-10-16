const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const sessionKey = "po.session";
let currentPage = "dashboard";
let cache = {};
let activeScenario = null;
let activeInstanceId = null;
const labels = {
  "knowledge-entries": {title:"判断条目",singular:"判断条目",subtitle:"专业判断的条目：前提、结论、例外、依据",id:"entry_id",readonly:false,cols:[["conclusion","结论"],["basis","依据"],["review_state","状态"]]},
  "scenario-definitions": {title:"场景定义",singular:"场景定义",subtitle:"可复用的专业任务骨架",id:"scenario_definition_id",readonly:false,cols:[["display_name_zh","名称"],["version","版本"]]},
  "domain-packs": {title:"领域包",singular:"领域包",subtitle:"行业词表与追问模板",id:"pack_id",readonly:false,cols:[["display_name_zh","名称"],["version","版本"]]},
  "profiles": {title:"个人资料", subtitle:"实名、证件、联系方式等敏感信息的存放处。字段随时可增删改，界面默认只显示掩码。"},
  "scenario-instances": {title:"场景实例",subtitle:"统一维护由场景切片确认写入本体的可复用实例。"},
  "account-security": {title:"登录与安全",subtitle:"管理登录密码、锁定状态与加密容器。"},
  "display-settings": {title:"显示与语言",subtitle:"选择界面与模型产出使用的语言。"},
  "agent-access": {title:"智能体授权",subtitle:"哪些本机程序可以读取本体，以及能读多少。"},
  "scenario-preview": {title:"场景预演",subtitle:"用模拟输入演习场景实例，检查必填信息和约束匹配情况。预演不会执行真实动作。"},
  principals: {title:"主体", singular:"主体", subtitle:"主体是规则中的“谁”，可以是个人、助手、群组、角色或组织。父级主体可用于继承授权。", id:"principal_id", fields:[f("display_name_zh","怎么称呼这个主体？","text",true,"例如：林素、家庭成员、日程助手","给它起一个你能认出的名字。"),f("principal_type","它属于哪一类？","select",true,[{value:"person",label:"个人",help:"一个真实的人，例如：林素"},{value:"agent",label:"智能体",help:"AI 智能体或自动化程序"},{value:"group",label:"群组",help:"家庭、项目组或团队"},{value:"role",label:"角色",help:"一类身份，例如管理员、访客"},{value:"org",label:"组织",help:"公司、机构或其他组织"},{value:"service",label:"服务",help:"一个对外提供能力的服务或平台"}],"选择最符合它身份的类别。"),f("display_name_en","英文名称（可选）","text",false,"例如 Lin Su"),f("parent_id","所属主体（可选）","entity",false,"principals","例如把家庭成员归入“我的家庭”。留空表示没有上级。")], cols:[["display_name_zh","名称"],["principal_type","类别"],["parent_id","所属主体"]]},
  "model-service": {title:"模型服务",singular:"模型服务",subtitle:"配置场景切片和自然语言解析使用的模型服务。密钥只提交到本机后端并加密保存在本机。",readonly:true},
  "agent-integration": {title:"智能体接入",subtitle:"通过本机 MCP 服务，让支持 MCP 的智能体查询治理目录并检查授权。"},
  "service-monitor": {title:"服务监控",subtitle:"查看本机控制台、治理后端、模型配置和智能体连接状态。"},
  decisions: {title:"判定记录",singular:"判定记录",subtitle:"查看授权引擎的历史结果、判定依据与决策时间。记录为只读。",id:"decision_id",readonly:true,cols:[["decision_id","判定 ID"],["phase","阶段"],["result_id","结果"],["reason_key","原因"],["timestamp","时间"]]}
};
function f(name,label,type="text",required=false,extra="",help=""){return {name,label,type,required,extra,help}}
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function pretty(value){if(Array.isArray(value))return value.join(", ");if(value&&typeof value==="object")return JSON.stringify(value);return value??"—"}
class AuthRequired extends Error{
  constructor(code){super(code==="ontology_uninitialized"?"尚未设置登录密码":"需要登录");this.code=code}
}
function apiDetail(payload,fallback){const detail=payload?.detail;if(typeof detail==="string")return detail;if(detail&&typeof detail.message==="string")return detail.message;if(typeof payload?.error==="string")return payload.error;return fallback}
function api(path, options={}){
  const token=sessionStorage.getItem(sessionKey);
  return fetch(path,{...options,headers:{...(options.body?{"Content-Type":"application/json"}:{}),...(token?{Authorization:`Bearer ${token}`} :{}),"X-Display-Language":displayLanguage,...(options.headers||{})}}).then(async response=>{
    const text=await response.text();let payload=null;try{payload=text?JSON.parse(text):null}catch{payload=text}
    if(response.status===401||response.status===409){
      const code=(payload?.detail&&typeof payload.detail==="object"?payload.detail.error:payload?.error)||"";
      if(code==="ontology_uninitialized"||code==="login_required"){
        sessionStorage.removeItem(sessionKey);authMode=code==="ontology_uninitialized"?"setup":"login";
        throw new AuthRequired(code);
      }
    }
    if(!response.ok){throw new Error(apiDetail(payload,payload?.report||response.statusText))}
    return payload;
  });
}
function toast(message,error=false){const el=document.createElement("div");el.className=`toast${error?" error":""}`;el.textContent=message;$("#toast-region").append(el);setTimeout(()=>el.remove(),3500)}
let authMode="login";
async function serviceHealth(){try{const health=await fetch("/health").then(r=>r.json());setDisplayLanguage(health.display_language||systemLanguage());applyI18n();return health}catch{return {offline:true}}}
let displayLanguage="zh";
function systemLanguage(){const locales=[...(navigator.languages||[]),navigator.language||""];for(const item of locales){const text=String(item||"").toLowerCase();if(text.startsWith("zh")||text.includes("chinese"))return "zh";if(text.startsWith("en")||text.includes("english"))return "en"}return "zh"}
function setDisplayLanguage(value){displayLanguage=normalizeLanguage(value)||systemLanguage();window.displayLanguage=displayLanguage}
function normalizeLanguage(value){const text=String(value||"").trim().toLowerCase();if(!text)return "";if(text.startsWith("zh")||text.includes("chinese"))return "zh";if(text.startsWith("en")||text.includes("english"))return "en";return ""}
function fieldLabel(row,zhKey,enKey){if(!row)return"";return displayLanguage==="en"?(row[enKey]||row[zhKey]):(row[zhKey]||row[enKey])}
function passwordScore(value){let score=0;if(value.length>=8)score++;if(value.length>=12)score++;if(/[a-z]/.test(value)&&/[A-Z]/.test(value))score++;if(/\d/.test(value))score++;if(/[^A-Za-z0-9]/.test(value))score++;return Math.min(score,5)}
function renderAuth(view,health={}){
  const offline=health.offline===true;
  const setup=authMode==="setup";
  view.innerHTML=`<div class="token-required"><div class="brand-mark" style="margin:auto"><span style="font-size:20px;color:var(--green)">◇</span></div>
   <h2>${offline?"本机服务未运行":setup?"设置登录密码":"本体已锁定"}</h2>
   <p>${offline?"治理后端没有响应。请到「配置与监控 → 服务监控」启动它，然后刷新页面。":setup?"这个密码用于登录控制台，同时加密你的本体数据。忘记密码将无法恢复数据。":"输入登录密码以解锁场景、规则与判定记录。"}</p>
   ${offline?`<button class="button primary" onclick="location.reload()">重新检测</button>`:`
   <form id="auth-form" autocomplete="off">
     <label class="field-label" for="auth-password">${setup?"密码":"登录密码"}</label>
     <input class="input" id="auth-password" type="password" autocomplete="${setup?"new-password":"current-password"}" placeholder="${setup?"至少 8 位，含 3 类字符":"输入登录密码"}">
     ${setup?`<label class="field-label" for="auth-password2" style="margin-top:10px">再输入一次</label>
     <input class="input" id="auth-password2" type="password" autocomplete="new-password">
     <p class="form-hint" id="auth-meter">强度 ░░░░░ · 推荐用 5 个不相关的词；常见口令会被拒绝。</p>
     <label class="field" style="display:flex;gap:8px;align-items:flex-start;margin-top:10px;font-size:12px;color:#526057"><input type="checkbox" id="auth-ack">我知道忘记密码后数据无法恢复</label>`:""}
     <div style="margin-top:14px"><button class="button primary" type="submit" style="width:100%">${setup?"创建并加密":"登录"}</button></div>
     <div id="auth-error" class="form-error"></div>
   </form>`}
  </div>`;
  if(offline)return;
  $("#auth-form").onsubmit=async e=>{
    e.preventDefault();
    const error=$("#auth-error");error.textContent="";
    const password=$("#auth-password").value;
    if(setup){
      if(password!==$("#auth-password2").value){error.textContent="两次输入的密码不一致。";return}
      if($("#auth-ack").checked!==true){error.textContent="请先确认已知悉忘记密码的后果。";return}
    }
    try{
      const result=await api(setup?"/v1/setup":"/v1/login",{method:"POST",body:JSON.stringify({password})});
      sessionStorage.setItem(sessionKey,result.token||"");
      cache={};currentPage="dashboard";toast(setup?"已创建并解锁本体":"已解锁本体");render();
    }catch(err){ if(!(err instanceof AuthRequired))error.textContent=err.message }
  };
  const meter=$("#auth-meter");
  if(meter){
    const draw=()=>{const value=$("#auth-password").value;const filled=passwordScore(value);
      meter.textContent="▓".repeat(filled)+"░".repeat(5-filled)+" · "+(filled>=4?"强度良好":filled>=3?"可以接受":"建议再加长或加符号");};
    $("#auth-password").addEventListener("input",draw);draw();
  }
  $("#auth-password")?.focus();
}
async function refreshService(){const state=$("#state-label").parentElement;try{const health=await serviceHealth();if(health&&health.offline)throw new Error("offline");state.classList.add("online");state.classList.remove("offline");$("#state-label").textContent="服务在线"}catch{state.classList.add("offline");state.classList.remove("online");$("#state-label").textContent="服务离线"}}
function navigate(page){currentPage=page;$$(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===page));$("#crumb").textContent=page==="dashboard"?"总览":labels[page]?.title||page;render()}
async function load(collection){if(!cache[collection]){const result=await api(`/v1/${collection}`);cache[collection]=result.items||[]}return cache[collection]}
function applyI18n(){try{window.poTranslate&&window.poTranslate(document.body)}catch(error){}}
async function reloadAll(){cache={};await refreshService();if(!sessionStorage.getItem(sessionKey)){const health=await serviceHealth();if(!health.offline&&health.initialized===false)authMode="setup";renderAuth($("#view"),health);applyI18n();return}render()}
function titleBlock(kicker,title,subtitle,action=""){return `<div class="title-row"><div><div class="eyebrow">${kicker}</div><h1 class="page-title">${title}</h1><p class="page-subtitle">${subtitle}</p></div>${action}</div>`}
function badge(value){const v=String(value??"").toLowerCase();const kind=["allow","deny","ask"].includes(v)?v:["true","active","person"].includes(v)?"active":["revoked","false"].includes(v)?"revoked":["high","critical"].includes(v)?"ask":"neutral";const text={allow:"允许",deny:"拒绝",ask:"需确认",true:"启用",false:"停用",person:"个人",low:"低",medium:"中",high:"高",critical:"严重"}[v]||value||"—";return `<span class="badge ${kind}">${esc(text)}</span>`}
async function render(){const view=$("#view");if(!sessionStorage.getItem(sessionKey)){const health=await serviceHealth();if(!health.offline&&health.initialized===false)authMode="setup";renderAuth(view,health);applyI18n();return}
 try{if(currentPage==="dashboard")await renderDashboard(view);else if(currentPage==="scenario-slices")await renderScenarios(view);else if(currentPage==="scenario-instances")await renderScenarioInstances(view);else if(currentPage==="profiles")await renderProfiles(view);else if(currentPage==="scenario-preview")await renderScenarioPreview(view);else if(currentPage==="model-service")await renderModelService(view);else if(currentPage==="account-security")await renderAccountSecurity(view);
  else if(currentPage==="feedback")await renderFeedback(view);else if(currentPage==="display-settings")await renderDisplaySettings(view);else if(currentPage==="decisions")await renderDecisions(view);else if(currentPage==="delivery")await renderDelivery(view);else if(currentPage==="agent-access")await renderAgentAccess(view);else if(currentPage==="agent-integration")await renderAgentIntegration(view);else if(currentPage==="service-monitor")await renderServiceMonitor(view);else await renderCollection(view,currentPage)}catch(error){view.innerHTML=`<div class="panel empty-state"><div class="empty-icon">!</div><strong>暂时无法读取数据</strong><p>${esc(error.message)}</p><button class="button" onclick="reloadAll()">重新连接</button></div>`;if(error instanceof AuthRequired){sessionStorage.removeItem(sessionKey);renderAuth(view,await serviceHealth())}}finally{applyI18n()}}
 if(["scenario-slices","scenario-instances","scenario-preview","delivery","decisions"].includes(currentPage)&&!view.querySelector("[data-pro-mode]"))view.insertAdjacentHTML("afterbegin",proModeButtons());   // Fallback: these three pages must carry the mode switch, whichever branch rendered.
async function renderAgentIntegration(view){
 const [configs,status]=await Promise.all([api("/manager/agent-configs"),api("/manager/status")]);
 const sessions=status.agent_sessions||[];
 view.innerHTML=`${titleBlock("CONFIGURATION · MCP","智能体接入",labels["agent-integration"].subtitle)}
 <section class="panel" style="padding:20px;margin-bottom:16px"><div class="panel-title">通过 MCP 连接个人可信数据空间</div><p class="page-subtitle" style="margin-top:7px;max-width:800px">MCP 服务按需由 WorkBuddy 或 Muse Code 启动为本机子进程。它提供治理目录查询和授权检查；授权检查只给出判定并写入记录，不会代替智能体执行酒店预订等操作。</p><div style="display:flex;gap:8px;margin-top:15px;flex-wrap:wrap"><a class="button" href="https://www.workbuddy.ai/docs/zh/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide" target="_blank" rel="noreferrer">WorkBuddy MCP 文档 ↗</a><a class="button" href="https://dev.meta.ai/docs/muse-code/extending?project_id=1661600634933790&amp;team_id=2096920474558192" target="_blank" rel="noreferrer">Meta Muse Code 文档 ↗</a></div></section>
 <section class="panel" style="padding:20px;margin-bottom:16px"><div class="panel-title">1. 选择智能体并复制配置</div><p class="panel-caption">把对应 JSON 粘贴到智能体的 MCP Server 配置中，然后按客户端提示重载 MCP 服务。</p><div style="display:flex;gap:8px;margin:14px 0"><button class="button agent-tab active" data-client="workbuddy">腾讯 WorkBuddy</button><button class="button agent-tab" data-client="muse_code">Meta Muse Code</button></div><pre id="agent-config" style="white-space:pre-wrap;overflow:auto;background:#f6f8f6;padding:14px;border-radius:7px;font:11px/1.6 var(--mono)"></pre><div style="display:flex;justify-content:flex-end"><button class="button primary" id="copy-agent-config">复制配置</button></div><div class="decision-detail"><strong>关于 Meta Muse</strong><div class="panel-caption">此处支持的是 Meta Muse Code 的 MCP 配置。Meta 面向消费者的 Muse 使用官方提供的连接器/API 能力；当前公开资料没有说明它能配置任意自定义 MCP 服务，所以不能直接套用 Muse Code 配置。</div></div></section>
 <section class="panel" style="padding:20px"><div class="panel-title">2. 数据访问范围</div><label style="display:flex;gap:9px;align-items:flex-start;margin-top:12px;color:#526057;font-size:12px"><input id="mcp-include-principals" type="checkbox" ${status.mcp_settings?.include_principals?"checked":""}>向智能体提供主体目录（包含主体名称和类型）</label><p class="panel-caption" style="margin:6px 0 0 24px">默认关闭。打开后需重新连接智能体，智能体才能读取主体目录。</p>
   <label class="field" style="max-width:420px;margin:12px 0 0 24px"><span class="field-label">名称显示方式</span><select class="select" id="mcp-principal-mode">${[["neutral","中性名（本人 / Me）—— 本机保留真名，智能体看不到"],["full","真实名称 —— 会进入智能体所连模型的上下文"],["id_only","仅 ID —— 不提供名称"]].map(([v,l])=>`<option value="${v}" ${((status.mcp_settings?.principal_display_mode||"neutral")===v)?"selected":""}>${l}</option>`).join("")}</select></label><div style="margin-top:18px"><div class="panel-title">当前 MCP 会话</div>${sessions.length?sessions.map(s=>`<div class="decision-detail"><strong>${esc(s.client?.name||s.client_name||"MCP 客户端")} · ${esc(s.status||"已连接")}</strong><div class="panel-caption">进程 ${esc(s.pid)} · 最近请求 ${esc(s.last_tool||"尚无工具调用")}</div></div>`).join(""):`<div class="panel-caption" style="margin-top:10px">暂无在线会话。连接后会显示客户端名称、进程和最近调用。</div>`}</div></section>`;
 let selected="workbuddy";const draw=()=>{$("#agent-config").textContent=JSON.stringify(configs[selected],null,2);$$('.agent-tab').forEach(x=>x.classList.toggle('active',x.dataset.client===selected))};draw();$$('.agent-tab').forEach(x=>x.onclick=()=>{selected=x.dataset.client;draw()});
 $("#copy-agent-config").onclick=async()=>{try{await navigator.clipboard.writeText(JSON.stringify(configs[selected],null,2));toast("MCP 配置已复制")}catch{toast("无法访问剪贴板，请手动复制配置",true)}};
 const saveMcpSettings=async(patch,onError)=>{const body={include_principals:$("#mcp-include-principals").checked,principal_display_mode:$("#mcp-principal-mode").value,...patch};try{await api("/manager/agent-settings",{method:"PUT",body:JSON.stringify(body)});toast("智能体数据范围设置已保存")}catch(error){onError&&onError();toast(error.message,true)}};
  $("#mcp-include-principals").onchange=e=>saveMcpSettings({},()=>{e.target.checked=!e.target.checked});
  $("#mcp-principal-mode").onchange=()=>saveMcpSettings();
}
async function renderServiceMonitor(view){
 const [status,logs]=await Promise.all([api("/manager/status"),api("/manager/logs")]);
 const state=(ok,up="运行中",down="未运行")=>ok===null||ok===undefined?`<span class="badge pending">未知</span>`:`<span class="badge ${ok?"allow":"pending"}">${ok?up:down}</span>`;
 const row=(name,ok,detail="")=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid #edf0ed;gap:14px"><div><strong style="font-size:12px">${esc(name)}</strong>${detail?`<div class="panel-caption">${esc(detail)}</div>`:""}</div>${state(ok)}</div>`;
 const files=status.files||{};const model=status.model_service||{};const sessions=status.agent_sessions||[];
 view.innerHTML=`${titleBlock("CONFIGURATION · OPERATIONS","服务监控",labels["service-monitor"].subtitle,`<button class="button" id="monitor-refresh">↻ 刷新状态</button>`)}
 <section class="panel" style="padding:18px 20px;margin-bottom:16px"><div class="panel-title">服务与模块</div>
 ${row("本机控制台 / 服务管理器",status.manager,"负责控制台页面、启动/重启后端及查看日志")}${row("治理后端与授权判定引擎",status.backend&&status.decision_engine,"API 运行于本机；后端停止时仍可从本页启动")}${row("前端页面资源",files.frontend,"菜单和浏览器界面")}${row("元模型与 SHACL 校验",files.ontology&&files.shacl,"本体定义和数据约束文件")}${row("RDF 数据存储",files.rdf_store,"本地数据文件读写状态")}${row("模型服务配置",model.configured,model.configured?`${model.model||"模型已配置"} · API Key ${model.has_api_key?"已加密保存":"未设置"}`:(model.error||"未配置；自然语言场景分析不可用"))}${row("MCP 智能体会话",sessions.length>0,sessions.length?`${sessions.length} 个客户端进程连接中`:"暂无客户端连接")}
 <div style="display:flex;gap:8px;margin-top:16px"><button class="button primary" id="manager-start" ${status.backend?"disabled":""}>启动后端</button><button class="button" id="manager-restart">重启后端</button><span id="manager-action-result" class="panel-caption" style="align-self:center"></span></div><div class="panel-caption" style="margin-top:10px">状态检查时间：${esc(formatTime(status.checked_at))}</div></section>
 <section class="panel"><div class="panel-header"><div><div class="panel-title" id="log-title">治理后端启动日志</div><div class="panel-caption">密钥和令牌会在显示前隐藏</div></div><div style="display:flex;gap:6px"><button class="button small log-service active" data-service="backend">后端</button><button class="button small log-service" data-service="manager">管理器</button><button class="button small" id="log-refresh">刷新日志</button></div></div><pre id="server-log" style="margin:0;padding:15px;max-height:360px;overflow:auto;white-space:pre-wrap;word-break:break-word;background:#18231c;color:#d5e2d8;font:10px/1.6 var(--mono)">${esc((logs.lines||[]).join("\n")||logs.message||"暂无日志")}</pre></section>`;
 let logService="backend";$("#monitor-refresh").onclick=()=>renderServiceMonitor(view);const refreshLogs=async()=>{try{const result=await api(`/manager/logs?service=${logService}`);$("#server-log").textContent=(result.lines||[]).join("\n")||result.message||"暂无日志";$("#log-title").textContent=logService==="manager"?"服务管理器启动日志":"治理后端启动日志"}catch(error){toast(error.message,true)}};$("#log-refresh").onclick=refreshLogs;$$('.log-service').forEach(button=>button.onclick=()=>{logService=button.dataset.service;$$('.log-service').forEach(x=>x.classList.toggle('active',x===button));refreshLogs()});
 const act=async action=>{const resultEl=$("#manager-action-result");resultEl.textContent=action==="start"?"正在启动…":"正在重启…";$("#manager-start").disabled=true;$("#manager-restart").disabled=true;try{const result=await api(`/manager/${action}`,{method:"POST",body:"{}"});toast(result.message||"操作完成");await renderServiceMonitor(view)}catch(error){resultEl.textContent=error.message;$("#manager-start").disabled=false;$("#manager-restart").disabled=false;try{const result=await api("/manager/logs");$("#server-log").textContent=(result.lines||[]).join("\n")}catch{}}};
 $("#manager-start").onclick=()=>act("start");$("#manager-restart").onclick=()=>act("restart");
}
async function renderAgentAccess(view){
 let data={};
 try { data=await api("/v1/agents"); }
 catch (e) {
   view.innerHTML=`${titleBlock("CONFIGURATION · ACCESS","智能体授权","")}`+
     `<section class="panel" style="padding:18px 20px"><div class="panel-title">读取失败</div>`+
     `<p class="panel-caption" style="color:#d9534f">读取已批准程序失败：${esc((e&&(e.message||(e.detail&&e.detail.message)))||e)}</p>`+
     `<p class="panel-caption">多半是控制台登录已失效（会话 30 分钟）。重新登录后刷新本页即可；数据没有被改动。</p></section>`;
   return;
 }
 const remote=await api("/v1/settings/remote-agents");
 const scopes=data.scopes||{},pending=data.pending||[],approved=data.approved||[],denied=data.denied||[];
 const scopeBoxes=(selected,idPrefix)=>{const set=new Set(selected||[]);return Object.entries(scopes).map(([key,label])=>
   `<label style="display:flex;gap:7px;align-items:flex-start;font-size:12px;color:#526057;margin:3px 0"><input type="checkbox" data-scope="${esc(idPrefix)}:${esc(key)}" ${set.has(key)?"checked":""}><span>${esc(label)}<span class="mono" style="color:#9aa79f"> · ${esc(key)}</span></span></label>`).join("")};
 const client=(row,actions)=>`<div class="decision-detail" style="margin-top:10px"><strong>${esc(row.name||row.executable||row.key)}</strong>
   <div class="panel-caption mono" style="word-break:break-all">${esc(row.command||"")}</div>
   <div class="panel-caption">首次 ${esc(formatTime(row.first_seen_at))} · 最近 ${esc(row.last_seen_at?formatTime(row.last_seen_at):"—")}${row.approvals?` · 已批准 ${row.approvals} 次`:""}</div>
   ${actions}</div>`;
 view.innerHTML=`${titleBlock("CONFIGURATION · ACCESS","智能体授权","本机程序要读取本体，必须先在这里获得你的批准。未获批准的程序拿不到任何数据，并会看到「请在控制台授权」的提示。",`<button class="button" id="agents-refresh">↻ 刷新</button>`)}
  <section class="panel" style="padding:18px 20px;margin-bottom:16px"><div class="panel-title">等待你批准 · ${pending.length}</div>
   <p class="panel-caption">这些程序已尝试连接本体，但在你批准前读不到任何内容。勾选允许的范围后点「允许」。</p>
   ${pending.length?pending.map(row=>client(row,`<div style="margin-top:8px" data-scopes-for="${esc(row.key)}">${scopeBoxes(data.default_scopes,row.key)}</div>
     <div style="display:flex;gap:8px;margin-top:8px"><button class="button primary" data-approve="${esc(row.key)}">允许所勾选范围</button><button class="button danger" data-deny="${esc(row.key)}">拒绝</button></div>`)).join(""):`<p class="panel-caption">当前没有等待批准的请求。</p>`}
  </section>
  <section class="panel" style="padding:18px 20px;margin-bottom:16px"><div class="panel-title">已授权 · ${approved.length}</div>
   <p class="panel-caption">修改范围后点「保存范围」；「撤销」会让该程序立刻失去访问权。</p>
   ${approved.length?approved.map(row=>client(row,`<div style="margin-top:8px" data-scopes-for="${esc(row.key)}">${scopeBoxes(row.scopes,row.key)}</div>
     <div style="display:flex;gap:8px;margin-top:8px"><button class="button primary" data-save-scopes="${esc(row.key)}">保存范围</button><button class="button danger" data-revoke="${esc(row.key)}">撤销</button><button class="button small" data-forget="${esc(row.key)}">移出清单</button></div>`)).join(""):`<p class="panel-caption">还没有任何程序获得授权。</p>`}
  </section>
  ${denied.length?`<section class="panel" style="padding:18px 20px;margin-bottom:16px"><div class="panel-title">已拒绝 · ${denied.length}</div>
   ${denied.map(row=>client(row,`<div style="margin-top:8px" data-scopes-for="${esc(row.key)}">${scopeBoxes(data.default_scopes,row.key)}</div>
     <div style="display:flex;gap:8px;margin-top:8px"><button class="button" data-approve="${esc(row.key)}">改为允许</button><button class="button small" data-forget="${esc(row.key)}">移出清单</button></div>`)).join("")}</section>`:""}
  <section class="panel" style="padding:18px 20px">
   <div class="panel-title">跨机接入</div>
   <p class="panel-caption"><strong>默认关闭</strong>，也是更安全的状态：关闭时磁盘上不存在任何可直接使用的凭据，本机程序只能靠进程身份 + 上面的授权访问。开启后会写入一份会话令牌文件，供另一台机器经 SSH 隧道读取——同机任何程序也能读到它并绕过智能体授权，请仅在确实需要跨机时开启。</p>
   <div style="display:flex;gap:8px;align-items:center;margin-top:10px"><label style="display:flex;gap:7px;align-items:center;font-size:12px"><input type="checkbox" id="remote-agents" ${remote.allow_remote_agents?"checked":""}>允许跨机接入${remote.token_present?"（令牌文件当前存在）":""}</label><button class="button" id="save-remote">保存</button></div>
  </section>`;
 const scopesOf=key=>$$(`[data-scope^="${key}:"]`).filter(b=>b.checked).map(b=>b.dataset.scope.split(":")[1]);
 const act=async(path,body,message)=>{try{await api(path,{method:"POST",body:JSON.stringify(body||{})});toast(message);render()}catch(error){if(!(error instanceof AuthRequired))toast(error.message,true)}};
 $$('[data-approve]',view).forEach(b=>b.onclick=()=>act(`/v1/agents/${encodeURIComponent(b.dataset.approve)}/approve`,{scopes:scopesOf(b.dataset.approve)},"已允许该程序访问"));
 $$('[data-save-scopes]',view).forEach(b=>b.onclick=()=>act(`/v1/agents/${encodeURIComponent(b.dataset.saveScopes)}/approve`,{scopes:scopesOf(b.dataset.saveScopes)},"授权范围已更新"));
 $$('[data-deny]',view).forEach(b=>b.onclick=()=>act(`/v1/agents/${encodeURIComponent(b.dataset.deny)}/deny`,{},"已拒绝该程序"));
 $$('[data-revoke]',view).forEach(b=>b.onclick=()=>act(`/v1/agents/${encodeURIComponent(b.dataset.revoke)}/revoke`,{},"已撤销，该程序立即失去访问权"));
 $$('[data-forget]',view).forEach(b=>b.onclick=async()=>{try{await api(`/v1/agents/${encodeURIComponent(b.dataset.forget)}`,{method:"DELETE"});toast("已移出清单");render()}catch(error){toast(error.message,true)}});
 $("#agents-refresh").onclick=()=>render();
 $("#save-remote").onclick=async()=>{try{await api("/v1/settings/remote-agents",{method:"PUT",body:JSON.stringify({allow_remote_agents:$("#remote-agents").checked})});toast("跨机接入设置已保存");render()}catch(error){toast(error.message,true)}};
}
async function renderDisplaySettings(view){
 const health=await serviceHealth();
 const current=health.display_language||displayLanguage||"zh";
 view.innerHTML=`${titleBlock("SETTINGS","显示与语言","选择界面与模型产出使用的语言。机器键始终是英文；标签与展示名称跟随这里。")}
  <section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">语言</div>
   <p class="panel-caption">${health.display_language?"当前由你指定。":"当前未指定，跟随浏览器/系统语言。"}影响两件事：① 模型分析场景时产出的字段标签（中文／英文）；② 界面显示主体、资源类型、动作时取用哪个名称字段。</p>
   <div class="form-grid" style="margin-top:12px;align-items:end">
    <label class="field"><span class="field-label">显示与产出语言</span>
     <select class="select" id="display-language">
      <option value="auto" ${health.display_language?"":"selected"}>跟随系统语言（${systemLanguage()==="en"?"English":"中文"}）</option>
      <option value="zh" ${health.display_language==="zh"?"selected":""}>中文</option>
      <option value="en" ${health.display_language==="en"?"selected":""}>English</option>
     </select></label>
    <div class="field"><button class="button primary" type="button" id="save-language">保存</button></div>
   </div>
   <p class="panel-caption" style="margin-top:12px">说明：界面文案与数据标签都跟随这里切换；个别未收录的提示仍会显示中文。</p>
  </section>`;
 $("#save-language").onclick=async()=>{
   try{const result=await api("/v1/settings/language",{method:"PUT",body:JSON.stringify({language:$("#display-language").value})});cache={};
     setDisplayLanguage(result.language);cache={};toast("语言已保存，正在刷新…");setTimeout(()=>location.reload(),350);
   }catch(error){if(!(error instanceof AuthRequired))toast(error.message,true)}
 };
}
async function renderFeedback(view){
 view.innerHTML=`${titleBlock("FEEDBACK","需求反馈","使用上的需求或 Bug 反馈")}
 <section class="panel" style="padding:24px;max-width:760px">
  <p style="font-size:14px;line-height:1.9;margin:0">您有任何的使用上的需求或 Bug 反馈，请联系作者：</p>
  <p style="margin:16px 0 0"><a href="mailto:liso@vip.sina.com" style="font-size:17px;font-weight:600">liso@vip.sina.com</a></p>
 </section>`;
}
async function renderAccountSecurity(view){
 let info={};
 try{info=await api("/v1/account")}catch(error){if(!(error instanceof AuthRequired))view.innerHTML=`<div class="panel empty-state">${esc(error.message)}</div>`;return}
 const kdf=info.kdf||{};
 view.innerHTML=`${titleBlock("SECURITY · LOCAL","登录与安全","管理登录密码、锁定状态与加密容器信息。")}
 <section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">修改登录密码</div>
  <p class="panel-caption">修改后会重新加密容器，并让所有会话（含其他设备与智能体）立即失效。</p>
  <form id="password-form" class="form-grid" style="margin-top:12px" autocomplete="off">
   <label class="field full"><span class="field-label">当前密码</span><input class="input" id="pw-current" type="password" autocomplete="current-password"></label>
   <label class="field"><span class="field-label">新密码</span><input class="input" id="pw-new" type="password" autocomplete="new-password" placeholder="至少 8 位，含 3 类字符"></label>
   <label class="field"><span class="field-label">再输入一次</span><input class="input" id="pw-new2" type="password" autocomplete="new-password"></label>
   <div class="field full"><button class="button primary" type="submit">修改密码并注销所有会话</button></div>
   <div id="password-error" class="form-error field full"></div>
  </form></section>
 <section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">锁定</div>
  <p class="panel-caption">锁定后内存中的密钥与数据立即丢弃，需要重新输入密码才能继续。</p>
  <div class="form-grid" style="margin-top:12px;align-items:end">
   <label class="field"><span class="field-label">空闲多久自动锁定</span>
    <select class="select" id="lock-timeout">${[[0,"不自动锁定（不推荐）"],[5,"5 分钟"],[15,"15 分钟"],[30,"30 分钟（默认）"],[60,"1 小时"],[120,"2 小时"],[480,"8 小时"]].map(([m,l])=>`<option value="${m}" ${(info.session_timeout_minutes??30)===m?"selected":""}>${l}</option>`).join("")}</select></label>
   <div class="field"><button class="button" id="lock-now" type="button">立即锁定</button></div>
  </div></section>
 <section class="panel" style="padding:18px"><div class="panel-title">加密容器</div>
  <div style="display:grid;gap:6px;margin-top:10px" class="panel-caption">
   <div>路径：<span class="mono">${esc(info.container||"data/ontology.po.json")}</span></div>
   <div>算法：${esc(kdf.name||"pbkdf2-hmac-sha256")} · 迭代 ${esc(String(kdf.iterations||""))} 次 · AES-256-GCM</div>
   <div>修订：${esc(String(info.revision??"—"))} · 最后更新：${esc(formatTime(info.updated_at))}</div>
   <div>当前会话数：${esc(String(info.sessions??1))}</div>
   <div>${info.legacy_plaintext?"⚠ 仍存在旧的明文图文件 ontology.ttl，建议尽快迁移并清理。":"✅ 未检测到明文图文件"}</div>
   <div>${(info.local_snapshots||[]).length?`⚠ 检测到 ${info.local_snapshots.length} 个 APFS 本地快照，其中可能留有迁移前的明文副本。删除：<span class="mono">sudo tmutil deletelocalsnapshots /</span>`:"✅ 未检测到 APFS 本地快照"}</div>
  </div></section>`;
 $("#password-form").onsubmit=async e=>{
  e.preventDefault();const error=$("#password-error");error.textContent="";
  const current=$("#pw-current").value,next=$("#pw-new").value;
  if(next!==$("#pw-new2").value){error.textContent="两次输入的新密码不一致。";return}
  try{
   const result=await api("/v1/account/password",{method:"PUT",body:JSON.stringify({current,new:next})});
   toast(result.message||"密码已更新");sessionStorage.removeItem(sessionKey);cache={};authMode="login";renderAuth($("#view"),await serviceHealth());applyI18n();
  }catch(err){if(!(err instanceof AuthRequired))error.textContent=err.message}
 };
 $("#lock-timeout").onchange=async e=>{
  try{const r=await api("/v1/account/session-timeout",{method:"PUT",body:JSON.stringify({minutes:Number(e.target.value)})});toast(r.session_timeout_minutes?`空闲 ${r.session_timeout_minutes} 分钟后自动锁定`:"已关闭自动锁定")}catch(error){if(!(error instanceof AuthRequired))toast(error.message,true)}
 };
 $("#lock-now").onclick=async()=>{try{await api("/v1/lock",{method:"POST"})}catch{}sessionStorage.removeItem(sessionKey);cache={};authMode="login";toast("已锁定");renderAuth($("#view"),await serviceHealth())};
}
async function renderModelService(view){
 const settings=await api("/v1/settings/model-service");
 const state=settings.configured?`<span class="badge allow">已配置</span>`:`<span class="badge pending">尚未配置</span>`;
 view.innerHTML=`${titleBlock("SETTINGS · MODEL","模型服务",labels["model-service"].subtitle)}
 <section class="panel" style="padding:20px;max-width:760px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px"><div><div class="panel-title">OpenAI 兼容接口</div><div class="panel-caption">支持云端服务和本机部署的兼容接口</div></div>${state}</div>
 <form id="model-service-form" class="modal-form"><div class="field"><label class="field-label" for="model-base-url">服务地址</label><input class="input" id="model-base-url" name="base_url" required maxlength="1000" value="${esc(settings.base_url||"")}" placeholder="例如：https://api.example.com/v1"><small class="field-help">填写服务的 API 根地址；本地模型可填写 http://127.0.0.1:端口/v1。也可直接填写完整的 /chat/completions 地址。</small></div>
 <div class="field"><label class="field-label" for="model-name">模型名称</label><input class="input" id="model-name" name="model" required maxlength="200" value="${esc(settings.model||"")}" placeholder="例如：模型服务提供方给出的模型 ID"></div>
 <div class="field"><label class="field-label" for="model-api-key">API Key（可选）</label><input class="input" id="model-api-key" name="api_key" type="password" autocomplete="new-password" maxlength="4096" placeholder="${settings.has_api_key?"密钥已保存；留空表示保留当前密钥":"本地服务无需密钥时可留空"}"><small class="field-help">${settings.has_api_key?"当前密钥已加密保存，不会显示或发送回浏览器。":"密钥保存在本机加密配置文件中，不写入本体数据。"}</small></div>
 <label style="display:flex;gap:8px;align-items:center;color:#77817c;font-size:11px"><input id="model-clear-key" type="checkbox" ${settings.has_api_key?"":"disabled"}>清除已保存的 API Key</label>
 <div id="model-service-error" class="form-error" role="status"></div><div id="model-service-success" class="field-help" role="status"></div>
 <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:8px"><button class="button" id="model-test" type="button" ${settings.configured?"":"disabled"}>测试连接</button><button class="button primary" id="model-save" type="submit">保存配置</button></div></form>
 <div class="decision-detail"><strong>连接测试说明</strong><div class="panel-caption">测试会向已保存的服务发送一条简短请求，确认模型能够响应；模型服务可能按其计费规则计费。请先保存配置，再测试连接。</div></div>
 </section>`;
 $("#model-service-form").onsubmit=saveModelService;
 $("#model-test").onclick=testModelService;
 ["#model-base-url","#model-name","#model-api-key","#model-clear-key"].forEach(selector=>$(selector).addEventListener("input",()=>{if($("#model-test")){ $("#model-test").disabled=true;$("#model-service-success").textContent="配置有更改，请先保存后再测试。"}}));
 $("#model-clear-key").addEventListener("change",()=>{if($("#model-test")){ $("#model-test").disabled=true;$("#model-service-success").textContent="配置有更改，请先保存后再测试。"}});
}
async function saveModelService(e){e.preventDefault();const button=$("#model-save");button.disabled=true;$("#model-service-error").textContent="";$("#model-service-success").textContent="";const body={base_url:$("#model-base-url").value,model:$("#model-name").value,api_key:$("#model-api-key").value,clear_api_key:$("#model-clear-key").checked};try{await api("/v1/settings/model-service",{method:"PUT",body:JSON.stringify(body)});$("#model-api-key").value="";toast("模型服务配置已安全保存");await renderModelService($("#view"))}catch(error){$("#model-service-error").textContent=error.message;button.disabled=false}}
async function testModelService(){const button=$("#model-test");button.disabled=true;button.textContent="正在测试…";$("#model-service-error").textContent="";$("#model-service-success").textContent="";try{const result=await api("/v1/settings/model-service/test",{method:"POST",body:"{}"});$("#model-service-success").textContent=result.message||"连接成功";toast("模型服务连接成功")}catch(error){$("#model-service-error").textContent=error.message}finally{button.disabled=false;button.textContent="测试连接"}}
function roleSummaryHtml(a,status){
 const roleLabel={required:"每次必填",preference:"长期偏好",both:"两者兼有"};
 const items=[...(a.required_inputs||[]).map(x=>({...x,kind:"必填清单"})),...(a.facts||[]).map(x=>({...x,kind:"偏好清单"}))];
 const rows=items.filter(x=>x&&(x.role||x.role_reason));
 if(!rows.length)return "";
 const pending=String(status||"")!=="confirmed";
 const contract=(a.contract_notes||[]);
 const count=r=>rows.filter(x=>x.role===r).length;
 const parts=[["required","条必填"],["preference","条偏好"],["both","条两者兼有"]].filter(([k])=>count(k)).map(([k,l])=>`${count(k)} ${l}`);
 const unknown=rows.filter(x=>!x.role).length; if(unknown)parts.push(`${unknown} 条未标注`);
 const style=pending?"padding:12px 17px;margin-bottom:16px;background:#fffaf0;border-color:#f0e0bd":"padding:12px 17px;margin-bottom:16px";
 return `<section class="panel" style="${style}"><details><summary style="cursor:pointer;font-size:13px">${pending?`<span class="badge pending">待核对</span> `:""}<strong>模型对字段的分档判断</strong> · ${parts.join(" · ")} <span class="panel-caption">（点击展开每一条的理由）</span>${contract.length?` <span class="badge deny">${contract.length} 处契约提醒</span>`:""}</summary>
  <p class="panel-caption" style="margin-top:8px">这只是模型的建议，实际以你的必填清单与偏好为准${pending?"；确认该场景即视为已核对。":"。"}</p>
  <div style="display:grid;gap:10px;margin-top:6px">${contract.length?`<div class="panel-caption" style="border-left:3px solid #e0b4b4;padding-left:8px">模型输出有 ${contract.length} 处不符合契约（后端已自动容错）：${contract.map(n=>`<br>· ${esc(n.message)}（${esc(n.field||"")}）`).join("")}</div>`:""}${rows.map(x=>`<div style="display:flex;gap:10px;align-items:flex-start"><span class="badge ${x.role==="both"?"pending":x.role==="preference"?"allow":""}" style="white-space:nowrap">${esc(roleLabel[x.role]||"未标注")}</span><div><strong style="font-size:12px">${esc(x.label||x.name||"")}</strong><span class="mono" style="color:#9aa79f;font-size:11px"> ${esc(x.name||"")} · 在${esc(x.kind)}</span><div class="panel-caption">${esc(x.role_reason||"（模型未给出理由）")}</div></div></div>`).join("")}</div></details></section>`;
}
// ===== Professional track (R2): mode switch, scenario definitions, judgment entries =====
// The daily path is left untouched: professional mode lives in its own functions and shares one ontology core.
const isProSlice=x=>((x&&x.scenario_profile)||{}).kind==="professional";   // Professional slices stay out of the daily-side lists and counts.
let professionalMode = (() => { try { return localStorage.getItem("po.professionalMode") === "1"; } catch (e) { return false; } })();
let proSliceId = null;

function proModeButtons(){return `<div class="collection-toolbar" style="margin-bottom:14px">
 <button class="button ${professionalMode?"":"primary"}" data-pro-mode="daily">日常生活场景</button>
 <button class="button ${professionalMode?"primary":""}" data-pro-mode="professional">专业技能场景</button>
 <span class="toolbar-spacer"></span>
 <span class="record-count">专业技能场景把专业判断写成可复核、可启用的规则；日常场景不受影响</span>
</div>`}

const PRO_AUTHORITY = {statute:"法条", interpretation:"司法解释", precedent:"判例", experience:"个人经验"};

async function renderProfessionalSlices(view){
 if(window.POPro&&window.POPro.renderSlices){return window.POPro.renderSlices(view)}   // New UI (web/pro.js); falls back to the old one if it failed to load.
 const [defs,slices,allEntries]=await Promise.all([load("scenario-definitions"),load("scenario-slices"),load("knowledge-entries")]);
 document.querySelector('[data-count="scenario-slices"]')?.replaceChildren(document.createTextNode(slices.length));
 const mine=slices.filter(x=>(x.scenario_profile||{}).kind==="professional");
 if(!mine.some(x=>x.id===proSliceId)) proSliceId=mine[0]?.id||null;
 let current=mine.find(x=>x.id===proSliceId)||null;
 const defsById=Object.fromEntries(defs.map(d=>[d.id,d]));
 const def=defsById[current?.scenario_definition_id]||defs[0]||null;
 const entries=allEntries.filter(e=>e.slice_id===proSliceId);
 const active=entries.filter(e=>e.review_state==="active").length;
 const opts=defs.map(d=>`<option value="${esc(d.id)}" ${current&&current.scenario_definition_id===d.id?"selected":""}>${esc(fieldLabel(d,"display_name_zh","display_name_en"))}</option>`).join("");
 const fields=(def?.premise_fields||[]);
 view.innerHTML=`${proModeButtons()}
 ${titleBlock("MY JUDGMENT","我的判断","把你知道的判断写下来：什么情况下、你的判断是什么、什么情况除外、依据是什么。每条先存草稿，确认无误再启用。")}
 <section class="panel" style="padding:18px;margin-bottom:16px">
  <div class="panel-title">第一步 · 选一个专业场景</div>
  <div class="panel-caption">选好后就能按这个场景的前提要素写判断。没有你要的场景？先随便选一个，之后可以改名。</div>
  <div style="display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap">
   <select class="select" id="pro-def" style="max-width:320px">${opts||'<option value="">暂无专业场景</option>'}</select>
   <button class="button primary" id="pro-start">开始录入我的判断</button>
   ${mine.length>1?`<select class="select" id="pro-slice" style="max-width:300px">${mine.map(x=>`<option value="${esc(x.id)}" ${x.id===proSliceId?"selected":""}>${esc((defsById[x.scenario_definition_id]||{}).display_name_zh||x.id)} · ${esc(x.id.slice(-6))}</option>`).join("")}</select>`:""}
  </div>
 </section>
 ${current?`<section class="panel" style="padding:18px;margin-bottom:16px">
  <div class="panel-title">第二步 · 写一条判断</div>
  <div class="panel-caption">四句话就够：什么情况下、我的判断、什么情况除外、依据。不确定的先空着，之后随时能改。</div>
  <div style="display:grid;gap:10px;margin-top:12px">
   ${fields.length?`<div class="field-label">什么情况下</div>
   <div style="display:flex;gap:10px;flex-wrap:wrap">
    ${fields.map(k=>`<label class="field" style="flex:1;min-width:150px"><span class="field-label">${esc(premiseLabel(def,k.key))}</span><input class="input" data-premise="${esc(k.key)}"></label>`).join("")}
   </div>`:`<div class="panel-caption" style="margin:0">这个场景还没有定义前提要素，先直接写判断；前提要素等技能框架定好后会自动出现。</div>`}
   <label class="field"><span class="field-label">我的判断</span><textarea class="input" id="pro-conclusion" rows="2"></textarea></label>
   <label class="field"><span class="field-label">什么情况除外</span><textarea class="input" id="pro-exception" rows="2"></textarea></label>
   <label class="field"><span class="field-label">依据</span><textarea class="input" id="pro-basis" rows="2"></textarea></label>
   <label class="field" style="max-width:280px"><span class="field-label">来源</span>
    <select class="select" id="pro-authority">${Object.entries(PRO_AUTHORITY).map(([k,v])=>`<option value="${k}">${v}</option>`).join("")}</select></label>
   <div><button class="button primary" id="pro-save">保存为草稿</button></div>
  </div>
 </section>`:`<section class="panel empty-state">先在上面选一个专业场景，再点「开始录入我的判断」。</section>`}
 <section class="panel collection-panel">
  <div class="collection-toolbar"><span class="record-count"><span>我的判断</span> ${entries.length} <span>条</span> · <span>已启用</span> ${active} <span>条</span></span><span class="toolbar-spacer"></span><button class="button" id="pro-reload">↻ 刷新</button></div>
  <div class="table-wrap"><table><thead><tr><th>什么情况下</th><th>我的判断</th><th>依据</th><th>来源</th><th>状态</th><th style="text-align:right">操作</th></tr></thead>
  <tbody>${entries.map(e=>`<tr>
   <td>${esc(premiseText(e.premise)||"—")}</td><td>${esc(e.conclusion||"")}</td><td>${esc(e.basis||"—")}</td>
   <td>${esc(PRO_AUTHORITY[e.authority]||e.authority||"—")}</td>
   <td>${e.review_state==="active"?`<span class="badge">已启用</span>`:`<span class="badge">草稿</span>`}</td>
   <td style="text-align:right;white-space:nowrap">
    <button class="button" data-pro-toggle="${esc(e.id)}" data-to="${e.review_state==="active"?"draft":"active"}">${e.review_state==="active"?"转回草稿":"确认并启用"}</button>
    <button class="button" data-pro-del="${esc(e.id)}">删除</button></td></tr>`).join("")}</tbody></table></div>
  <div class="empty-state" ${entries.length?"hidden":""}><div class="empty-icon">◇</div>还没有判断。上面写一条，点「保存为草稿」即可。</div>
 </section>`;
 const defSel=$("#pro-def");
 const startBtn=$("#pro-start"); if(startBtn) startBtn.onclick=async()=>{
   const id=defSel?.value; if(!id){alert("请先选择一个专业场景。");return}
   const label=defSel.options[defSel.selectedIndex].text;
   const r=await api("/v1/scenario-slices",{method:"POST",body:JSON.stringify({original_text:label,status:"analyzed",scenario_definition_id:id,scenario_profile:{kind:"professional"},analysis:{title:label},updated_at:new Date().toISOString()})});
   if(r?.id){proSliceId=r.id;cache["scenario-slices"]=null;render()}};
 const sliceSel=$("#pro-slice"); if(sliceSel) sliceSel.onchange=()=>{proSliceId=sliceSel.value;render()};
 const save=$("#pro-save"); if(save) save.onclick=async()=>{
   if(!proSliceId){alert("请先点「开始录入我的判断」。");return}
   const premise={}; document.querySelectorAll("[data-premise]").forEach(i=>{if(i.value.trim())premise[i.dataset.premise]=i.value.trim()});
   const body={slice_id:proSliceId,premise,conclusion:$("#pro-conclusion").value.trim(),exception:$("#pro-exception").value.trim(),basis:$("#pro-basis").value.trim(),authority:$("#pro-authority").value,review_state:"draft",version:"1",updated_at:new Date().toISOString()};
   if(!body.conclusion){alert("请填写「我的判断」。");return}
   await api("/v1/knowledge-entries",{method:"POST",body:JSON.stringify(body)});cache["knowledge-entries"]=null;render() };
 document.querySelectorAll("[data-pro-toggle]").forEach(b=>b.onclick=async()=>{
   await api(`/v1/knowledge-entries/${b.dataset.proToggle}`,{method:"PATCH",body:JSON.stringify({review_state:b.dataset.to,reviewed_at:new Date().toISOString()})});cache["knowledge-entries"]=null;render() });
 document.querySelectorAll("[data-pro-del]").forEach(b=>b.onclick=async()=>{
   if(!confirm("删除这条判断？"))return; await api(`/v1/knowledge-entries/${b.dataset.proDel}`,{method:"DELETE"});cache["knowledge-entries"]=null;render() });
 const rel=$("#pro-reload"); if(rel) rel.onclick=()=>{cache["knowledge-entries"]=null;cache["scenario-slices"]=null;render()};
}

function premiseLabel(def,key){const f=(def?.premise_fields||[]).find(x=>x.key===key);const l=f?.label;return l?(l.zh||l.en||key):key}
function premiseText(premise){if(!premise)return"";if(typeof premise==="string")return premise;return Object.entries(premise).map(([k,v])=>`${k}=${v}`).join(" · ")}

async function renderScenarios(view){
 if(professionalMode){return renderProfessionalSlices(view)}
 const [rows,provider]=await Promise.all([load("scenario-slices").then(r=>r.filter(x=>!isProSlice(x))),api("/v1/scenario-slices/provider"),load("principals")]);
 // The draft list shows unconfirmed scenes only; confirmed ones are already in the ontology (the sidebar count still shows all).
 const drafts=rows.filter(x=>String(x.status||"")!=="confirmed");
 document.querySelector('[data-count="scenario-slices"]')?.replaceChildren(document.createTextNode(rows.length));
 const scene=activeScenario;const a=scene?.analysis||{};
 view.innerHTML=`${proModeButtons()}${titleBlock("SCENARIO BUILDER","场景切片","用日常语言描述一个场景。模型会拆解资源、动作、条件，并主动提示可能遗漏的信息；所有输出都只是待审草稿。")}
 <section class="panel" style="padding:20px;margin-bottom:16px"><div class="panel-title">描述你的场景</div><div class="panel-caption">例如：预定酒店时，先问清目标城市，价格不超过 500 元；我关心位置、评价、停车场、楼层、是否吸烟和入住天数。</div><form id="scenario-form" style="margin-top:14px"><textarea class="textarea" id="scenario-text" rows="5" maxlength="10000" placeholder="尽可能写下你的目标、偏好和限制；不完整也没关系。模型会指出缺少的信息并给出补充建议。">${esc(scene?.original_text||"")}</textarea><label style="display:flex;gap:8px;align-items:flex-start;margin-top:10px;color:#77817c;font-size:11px"><input id="scenario-consent" type="checkbox" required><span>我知道场景描述和现有资源/动作目录会发送到已配置的模型服务进行分析。主体名称和授权数据不会发送。</span></label><div style="display:flex;align-items:center;gap:12px;margin-top:10px"><button class="button primary" id="scenario-submit" type="submit">${scene?"根据补充信息重新分析":"分析场景"} <span>→</span></button><span class="muted">${provider.configured?"分析服务已配置":"分析服务尚未配置"}</span></div><div id="scenario-error" class="form-error"></div></form></section>
 ${!provider.configured?`<section class="panel" style="padding:16px;margin-bottom:16px;color:#8b611f;background:#fffaf0">还没有配置场景分析模型。请到“配置与监控 → 模型服务”填写服务地址和模型名称，再回来分析场景。</section>`:""}
 ${drafts.length?`<section class="panel" style="padding:17px"><div class="panel-title">未确认的场景草稿</div><div class="panel-caption">草稿保存在本机本体数据中</div><div style="display:grid;gap:8px;margin-top:12px">${drafts.map(x=>`<div style="display:flex;gap:8px"><button class="button" style="flex:1;justify-content:flex-start;height:auto;padding:10px;text-align:left" data-scene="${esc(x.id)}"><span>${esc(x.analysis?.title||x.original_text.slice(0,90))}</span><span class="muted" style="margin-left:auto">${esc(formatTime(x.updated_at))}</span></button><button class="button danger" data-delete-scene="${esc(x.id)}" title="删除场景草稿">删除</button></div>`).join("")}</div></section>`:""}
 ${scene?roleSummaryHtml(a,scene.status):""}
 ${scene?scenarioAnalysisHtml(a):""}
 `;
 if(scene)$("#scenario-text").value=scene.original_text;
 $("#scenario-form").onsubmit=submitScenario;
 $("#reanalyze")?.addEventListener("click",()=>$("#scenario-form").requestSubmit());
 $("#confirm-scenario")?.addEventListener("click",confirmScenario);
 $$('[data-goto]',view).forEach(b=>b.onclick=()=>navigate(b.dataset.goto));
 $$('[data-scene]').forEach(b=>b.onclick=()=>{activeScenario=rows.find(x=>x.id===b.dataset.scene);render()});
 $$('[data-delete-scene]').forEach(b=>b.onclick=()=>deleteScenario(b.dataset.deleteScene));
 bindSegmentationEditor("slice",a);
}
async function deleteScenario(id){const scene=(cache["scenario-slices"]||[]).find(x=>x.id===id);const label=scene?.analysis?.title||scene?.original_text?.slice(0,80)||id;if(!confirm(`确定删除场景实例“${label}”？场景独有的生成对象会一并清理；已被其他数据引用的对象会保留。`))return;try{await api(`/v1/scenario-slices/${encodeURIComponent(id)}`,{method:"DELETE"});cache["scenario-slices"]=(cache["scenario-slices"]||[]).filter(x=>x.id!==id);if(activeScenario?.id===id)activeScenario=null;if(activeInstanceId===id)activeInstanceId=null;toast("场景实例已删除");render()}catch(error){toast(error.message,true)}}
function scenarioSegmentationEditor(a,prefix){
 const saved=a.segmentation&&typeof a.segmentation==="object"?a.segmentation:null;const mode=saved?.mode==="segmented"||a.scope?.mode==="by_dimension"?"segmented":"global";const dimensions=saved?.dimensions||((a.scope?.mode==="by_dimension"&&a.scope?.dimension)?[{field:a.scope.dimension,label:a.scope.label||a.scope.dimension,type:"string"}]:[]);let variants=saved?.variants?.length?saved.variants:[{id:"variant_1",values:{},preferences:[]}];const savedGlobal=Array.isArray(saved?.global_preferences)?saved.global_preferences:[];
 const savedInstance=Array.isArray(a.instance_preferences)?a.instance_preferences:[];
 // 注意：空数组在 JS 里是真值，用 || 会短路掉 instance_preferences 的回退。
 const fromFacts=!(savedGlobal.length||savedInstance.length)&&mode==="global";
 let base=[...(mode==="segmented"?(variants[0].preferences||[]):(savedGlobal.length?savedGlobal:savedInstance))].map(x=>({...x,keep:true}));for(const d of dimensions)if(!base.some(x=>x.field===d.field))base.push({field:d.field,label:d.label,type:d.type,dimension:true,keep:true});if(!base.length){const runtimeNames=new Set([...(a.required_inputs||[]).map(x=>String(x&&x.name||"")),...(mode==="segmented"?(segmentation.dimensions||[]).map(d=>String(d&&d.field||"")):[])]);for(const x of a.facts||[])if(x&&x.source!=="suggestion")base.push({field:x.name,label:x.label||x.name,type:x.type||typeof x.value,value:x.value,keep:!runtimeNames.has(String(x.name||"")),operator:/price_max|_max|budget_max/.test(x.name||"")?"lte":/price_min|_min|budget_min/.test(x.name||"")?"gte":"equals"})}if(mode==="segmented")for(const item of a.required_inputs||[])if(item?.name&&!base.some(x=>x.field===item.name))base.push({field:item.name,label:item.label||item.name,type:item.type||"string",dimension:true});
 const gridCols=mode==="segmented"?"max-content minmax(130px,1fr) minmax(120px,1fr)":"max-content minmax(150px,1fr) minmax(130px,1fr)";
 const renderRow=(x,value,checked)=>{const typ=x.type||typeof value;const control=typ==="boolean"||typ==="bool"?`<select class="select" data-seg-value><option value="true" ${value===true||value==="true"?"selected":""}>是</option><option value="false" ${value===false||value==="false"?"selected":""}>否</option></select>`:`<input class="input" data-seg-value type="${typ==="number"?"number":typ==="date"?"date":"text"}" value="${esc(value??"")}" placeholder="填写当前值">`;
  // 全局模式用首列做「长期」采纳框：从本次描述抽出来的值默认不勾选，只有用户明确采纳才会写入实例并成为判定条件。
  const first=mode==="segmented"
   ?`<label class="seg-dimension-choice" style="display:flex;align-items:center;gap:6px"><input type="checkbox" data-seg-dimension ${checked?"checked":""}><span>维度</span></label>`
   :`<label class="seg-keep-choice" style="display:flex;align-items:center;gap:6px" title="勾选后作为长期偏好保存，并成为判定条件"><input type="checkbox" data-seg-keep ${x.keep===false?"":"checked"}><span>长期</span></label>`;
  return `<div class="form-grid seg-pref-row" data-seg-field="${esc(x.field||x.name||"")}" data-seg-label="${esc(x.label||x.name||"")}" data-seg-type="${esc(typ)}" data-seg-operator="${esc(x.operator||"equals")}" style="grid-template-columns:${gridCols};align-items:center">${first}<div><strong>${esc(x.label||x.name||"信息")}</strong><small class="panel-caption" style="display:block">${esc(x.field||x.name||"")}</small>${(x.role||x.role_reason)?`<small class="panel-caption" style="display:block" title="${esc(x.role_reason||"")}">模型判断：<strong>${{required:"每次必填",preference:"长期偏好",both:"两者兼有"}[x.role]||"未标注"}</strong>${x.role_reason?` · ${esc(x.role_reason)}`:""}</small>`:""}<select class="select" data-seg-tier style="margin-top:3px;font-size:11px;padding:2px 4px;width:auto;max-width:130px"><option value="preference" ${x.role==="both"||x.keep!==false?"selected":""}>长期偏好</option><option value="required" ${x.role!=="both"&&x.keep===false?"selected":""}>每次必填</option><option value="both" ${x.role==="both"?"selected":""}>两者兼有</option></select></div><div>${control}</div></div>`};
 const cards=variants.map((v,i)=>{const rows=[...base];for(const p of v.preferences||[])if(!rows.some(x=>x.field===p.field))rows.push(p);const values=Object.fromEntries((v.preferences||[]).map(p=>[p.field,p.value]));for(const d of dimensions)values[d.field]=v.values?.[d.field]??"";return `<div class="seg-variant-card" data-variant-id="${esc(v.id||`variant_${i+1}`)}" style="border:1px solid #e5e9e6;border-radius:10px;padding:12px"><div style="display:flex;align-items:center;justify-content:space-between"><strong>分组 ${i+1}</strong>${variants.length>1?`<button type="button" class="button danger" data-remove-variant>删除分组</button>`:""}</div><div style="display:grid;gap:8px;margin-top:10px">${rows.map(x=>renderRow(x,values[x.field]??x.value,dimensions.some(d=>d.field===x.field)||x.dimension)).join("")}</div></div>`}).join("");
 const prefs=mode==="global"?base:[];const rowsHtml=mode==="global"?`<div id="${prefix}-seg-rows" style="display:grid;gap:8px">${prefs.map(x=>renderRow(x,x.value,false)).join("")||`<div class="panel-caption">模型还没有识别出偏好字段。</div>`}</div>`:`<div id="${prefix}-seg-variants" style="display:grid;gap:10px">${cards}</div><button type="button" class="button" id="${prefix}-add-variant" style="margin-top:10px">＋ 添加分组</button>`;
 return `<section class="panel" id="${prefix}-seg-editor" style="padding:18px;margin-bottom:14px"><div class="panel-title">场景偏好范围与分组</div><p class="panel-caption">${mode==="global"?"字段和名称由模型定义并保持固定；可调整值。勾选「长期」的偏好今后一直适用，会写入场景实例并成为判定条件；只属于本次的条目（具体日期、人数等）不要勾选。":"每个分组填写一组维度取值；维度之外的字段是该分组的偏好约束。"}</p><label class="field" style="max-width:420px;margin:12px 0"><span class="field-label">偏好适用范围</span><select class="select" id="${prefix}-seg-mode"><option value="global" ${mode==="global"?"selected":""}>所有情况共用一套偏好</option><option value="segmented" ${mode==="segmented"?"selected":""}>按上下文维度区分偏好</option></select></label><div class="panel-caption" style="margin:8px 0">${mode==="global"
   ?`全部偏好共同适用，不需要设置维度。<strong id="${prefix}-seg-count"></strong>${fromFacts?" 下面这些来自首次描述：<strong>每次执行才确定的字段（城市、日期、人数等）默认不勾选，其余默认勾选</strong>——勾上的会在确认后成为长期偏好。":""}`
   :"每个分组填写一组维度取值；维度之外的字段是该分组的偏好约束。"}</div>${rowsHtml}<div id="${prefix}-seg-error" class="form-error"></div></section>`
}
function readScenarioSegmentation(prefix,previous={}){const mode=$(`#${prefix}-seg-mode`)?.value||"global";const readRows=container=>$$(`.seg-pref-row`,container).map(row=>{const field=row.dataset.segField,label=row.dataset.segLabel,type=row.dataset.segType;const control=$("[data-seg-value]",row);let value=control?.value??"";if(type==="number"&&value!=="")value=Number(value);if((type==="boolean"||type==="bool")&&value!=="")value=value==="true";return{field,label,type,value,operator:row.dataset.segOperator||"equals",strength:"must",dimension:$('[data-seg-dimension]',row)?.checked===true,keep:(row.querySelector("[data-seg-tier]")?.value||"")==="required"?false:($('[data-seg-keep]',row)?.checked!==false)}}).filter(x=>x.field&&x.label&&(x.value!==""||x.dimension));if(mode==="global")return{mode,dimensions:[],global_preferences:readRows($(`#${prefix}-seg-rows`)).filter(x=>x.keep).map(({dimension,keep,...x})=>x),variants:[]};const error=$(`#${prefix}-seg-error`);const cards=$$(`#${prefix}-seg-variants .seg-variant-card`);const first=cards[0];const firstRows=readRows(first);const dimensions=firstRows.filter(x=>x.dimension).map(({field,label,type})=>({field,label,type}));if(!dimensions.length){if(error)error.textContent="请至少勾选一个区分维度。";return null}const variants=[];for(const card of cards){const rows=readRows(card);const values=Object.fromEntries(rows.filter(x=>x.dimension).map(x=>[x.field,x.value]));if(dimensions.some(d=>values[d.field]===""||values[d.field]===undefined)){if(error)error.textContent="请填写每个分组的全部维度取值。";return null}variants.push({id:card.dataset.variantId,values,preferences:rows.filter(x=>!x.dimension).map(({dimension,...x})=>x)})}return{mode,dimensions,global_preferences:Array.isArray(previous.global_preferences)?previous.global_preferences:[],variants}}
function bindSegmentationEditor(prefix,a={}){
 const refreshKeepCount=()=>{const el=$(`#${prefix}-seg-count`);if(!el)return;const boxes=$$(`#${prefix}-seg-rows [data-seg-keep]`);const n=boxes.filter(b=>b.checked).length;el.textContent=`已勾选 ${n} / ${boxes.length} 条长期偏好。`};
 const bindKeepRows=()=>{
   $$(`#${prefix}-seg-rows [data-seg-keep]`).forEach(b=>b.addEventListener("change",refreshKeepCount));
   // 手动改过值的行视为"我要它"，自动勾选，避免设了值却没保存。
   $$(`#${prefix}-seg-rows .seg-pref-row`).forEach(row=>{const value=$("[data-seg-value]",row),keep=$("[data-seg-keep]",row);if(value&&keep)value.addEventListener("input",()=>{if(!keep.checked){keep.checked=true;refreshKeepCount()}})});
   refreshKeepCount();
 };
 const editor=$(`#${prefix}-seg-editor`),mode=$(`#${prefix}-seg-mode`);if(editor&&mode)editor.dataset.mode=mode.value;bindKeepRows();mode?.addEventListener("change",()=>{const old=editor.dataset.mode||"global";let segmentation;if(old==="global"){const prefs=$$(`#${prefix}-seg-rows .seg-pref-row`).filter(row=>$('[data-seg-keep]',row)?.checked!==false).map(row=>{const el=$("[data-seg-value]",row);let value=el?.value??"";if(row.dataset.segType==="number"&&value!=="")value=Number(value);if(["bool","boolean"].includes(row.dataset.segType))value=value==="true";return{field:row.dataset.segField,label:row.dataset.segLabel,type:row.dataset.segType,value,operator:row.dataset.segOperator||"equals",strength:"must"}}).filter(x=>x.value!=="");segmentation={mode:"segmented",dimensions:[],global_preferences:prefs,variants:[{id:"variant_1",values:{},preferences:prefs}]}}else{const card=$(`#${prefix}-seg-variants .seg-variant-card`);const rows=card?$$(`.seg-pref-row`,card):[];const prefs=rows.filter(row=>!$('[data-seg-dimension]',row)?.checked).map(row=>{const el=$("[data-seg-value]",row);let value=el?.value??"";if(row.dataset.segType==="number"&&value!=="")value=Number(value);if(["bool","boolean"].includes(row.dataset.segType))value=value==="true";return{field:row.dataset.segField,label:row.dataset.segLabel,type:row.dataset.segType,value,operator:row.dataset.segOperator||"equals",strength:"must"}}).filter(x=>x.value!=="");segmentation={mode:"global",dimensions:[],global_preferences:prefs,variants:[]}}const replacement=document.createElement("div");replacement.innerHTML=scenarioSegmentationEditor({...a,segmentation},prefix);editor.replaceWith(replacement.firstElementChild);bindSegmentationEditor(prefix,a);refreshKeepCount()});const add=$(`#${prefix}-add-variant`);add?.addEventListener("click",()=>{const container=$(`#${prefix}-seg-variants`);const cards=$$(".seg-variant-card",container);const clone=cards[0]?.cloneNode(true);if(!clone)return;clone.dataset.variantId=`variant_${Date.now()}`;clone.querySelector("strong").textContent=`分组 ${cards.length+1}`;clone.querySelector("[data-remove-variant]")?.remove();clone.querySelectorAll("[data-seg-dimension]").forEach(el=>{if(el.checked){const row=el.closest(".seg-pref-row");const input=$("[data-seg-value]",row);if(input)input.value=""}});container.append(clone);bindVariantRemovers(prefix)});bindVariantRemovers(prefix);$$(`#${prefix}-seg-variants [data-seg-dimension]`).forEach(box=>box.onchange=()=>{const field=box.closest(".seg-pref-row")?.dataset.segField;$$(`#${prefix}-seg-variants .seg-pref-row`).filter(row=>row.dataset.segField===field).forEach(row=>{$('[data-seg-dimension]',row).checked=box.checked})})}
function bindVariantRemovers(prefix){const cards=$$(`#${prefix}-seg-variants .seg-variant-card`);cards.forEach(card=>{let button=$("[data-remove-variant]",card);if(cards.length>1&&!button){card.querySelector("div").insertAdjacentHTML("beforeend",'<button type="button" class="button danger" data-remove-variant>删除分组</button>');button=$("[data-remove-variant]",card)}if(cards.length===1)button?.remove();if(button)button.onclick=()=>{card.remove();bindVariantRemovers(prefix)}})}
function relationName(collection,id){const row=(cache[collection]||[]).find(x=>String(x.id)===String(id));return row?displayName(collection,row):String(id||"—")}
function policyEffectText(effect){return {allow:"允许执行",deny:"拒绝执行",ask:"暂停并询问"}[String(effect||"").toLowerCase()]||String(effect||"—")}
function policyConditionText(condition){const c=condition||{};const raw=c.value;const payload=raw&&typeof raw==="object"&&!Array.isArray(raw)?raw:{};const key=payload.key||"";const value=payload.value!==undefined?payload.value:raw;switch(String(c.type||"")){case "context_exists":return `${key||"字段"} 必须提供`;case "context_equals":return `${key||"字段"} = ${value}`;case "numeric_lte":return `${key||"字段"} ≤ ${value}`;case "numeric_gte":return `${key||"字段"} ≥ ${value}`;case "source_trust_min":return `来源可信度 ≥ ${{low:"低",medium:"中",high:"高"}[String(value)]||value}`;default:return `${c.type||"未知条件"}（不可执行）`}}
function scenarioPolicyListHtml(policies){const rules=(policies&&policies.rules)||[];const segmented=policies?.segmentation_mode==="segmented";if(!rules.length)return `<div class="panel-caption">该场景还没有生成授权规则。</div>`;return rules.map(rule=>{const status=String(rule.policy_status||"draft");const blocked=((rule.problems)||[]).length>0;const statusKind=status==="active"?"active":status==="suspended"?"neutral":"pending";const statusText={draft:"草稿，未生效",active:"生效中",suspended:"已暂停"}[status]||status;const canEnable=status!=="active"&&!blocked&&!segmented;const editBtn=`<button type="button" class="button" data-edit-rule="${esc(rule.authorization_id)}">编辑规则</button>`;const delBtn=`<button type="button" class="button danger" data-delete-policy="${esc(rule.authorization_id)}">删除</button>`;const action=(status==="active"?`<button type="button" class="button" data-suspend-policy="${esc(rule.authorization_id)}">暂停规则</button>`:`<button type="button" class="button primary" data-activate-policy="${esc(rule.authorization_id)}" ${canEnable?"":"disabled"}>启用规则</button>`)+editBtn+delBtn;const conditions=(rule.conditions||[]).length?`<div class="panel-caption">条件：${esc(rule.conditions.map(policyConditionText).join("；"))}</div>`:`<div class="panel-caption">无条件：匹配主体、资源与动作即生效</div>`;return `<div class="decision-detail" style="margin:0"><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap"><strong>${esc(policyEffectText(rule.effect))}</strong><span class="badge ${statusKind}">${esc(statusText)}</span><span style="margin-left:auto">${action}</span></div><div class="panel-caption">适用对象：${esc(relationName("principals",rule.grantee_id))}${String(rule.grantor_id||"")!==String(rule.grantee_id||"")?`（由 ${esc(relationName("principals",rule.grantor_id))} 设置）`:""}</div><div class="panel-caption">资源：${esc(relationName("resource-types",rule.resource_type_id))} · 范围 ${esc(rule.resource_pattern||"*")} · 动作 ${esc((rule.actions||[]).map(a=>relationName("actions",a)).join("、")||"—")}</div>${conditions}${blocked?`<div class="form-error">${esc((rule.problems||[]).join("；"))}，因此暂不能启用。</div>`:""}</div>`}).join("")}
function scenarioPolicyBlock(scenarioId,analysis,policies){
  const rules=(policies&&policies.rules)||[];
  if(rules.length)return scenarioPolicySectionHtml(policies);
  const drafts=(analysis&&analysis.policies)||[];
  if(!drafts.length)return scenarioPolicySectionHtml(policies);
  const principals=cache.principals||[];
  return `<section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">授权规则 · 0</div>
   <p class="panel-caption">这个场景有 <strong>${drafts.length} 条规则草稿</strong>（模型在分析时已给出），但确认场景时没有选择主体，因此还没有生成授权记录。选择主体后即可生成草稿规则，再逐条审核启用。</p>
   <div class="form-grid" style="margin-top:12px;align-items:end">
    <label class="field"><span class="field-label">规则适用于谁</span><select class="select" id="compile-grantee">${principals.map(x=>`<option value="${esc(x.id)}">${esc(displayName("principals",x))}</option>`).join("")||`<option value="">（还没有主体，请先到「主体」添加）</option>`}</select></label>
    <div class="field"><button class="button primary" type="button" id="compile-rules">生成授权规则</button></div>
   </div>
   <div id="compile-error" class="form-error"></div></section>`;
}
function scenarioPolicySectionHtml(policies){const rules=(policies&&policies.rules)||[];const active=rules.filter(r=>r.policy_status==="active").length;const segmented=policies?.segmentation_mode==="segmented";return `<section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">授权规则 · ${rules.length}${rules.length?`（${active} 条生效中）`:""}</div><p class="panel-caption">场景生成的规则默认是草稿，不参与判定。启用只让判定引擎读取它，不会执行任何操作；改动上方的偏好或必填信息后，生效中的规则会自动回到草稿。${segmented?" 分组场景的规则暂不支持启用。":""}</p><div style="display:grid;gap:10px;margin-top:12px">${scenarioPolicyListHtml(policies)}</div><div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap"><button type="button" class="button" data-add-policy>＋ 新增一条规则</button><span class="panel-caption" style="margin:0">用上面选定的被授权主体，为该场景的动作新增一条【无条件允许】的草稿规则；建好后可在上方启用，或按需要再改。</span></div></section>`}
async function loadScenarioPolicies(scenarioId){return api(`/v1/scenario-slices/${encodeURIComponent(scenarioId)}/policies`)}
async function setScenarioPolicyStatus(scenarioId,status,ids=null){const action=status==="active"?"activate":"suspend";const body={};if(Array.isArray(ids)&&ids.length)body.authorization_ids=ids;try{const res=await api(`/v1/scenario-slices/${encodeURIComponent(scenarioId)}/${action}`,{method:"POST",body:JSON.stringify(body)});delete cache.authorizations;delete cache["scenario-slices"];const changed=(res.changed||[]).length;const blocked=(res.blocked||[]).length;toast(`${status==="active"?"已启用":"已暂停"} ${changed} 条规则${blocked?`；${blocked} 条因条件不可执行未启用`:""}`);render()}catch(error){toast(error.message,true)}}
async function openPolicyReview(scenarioId){const dialog=$("#record-dialog"),content=$("#dialog-content");content.innerHTML=`<div class="modal-kicker">POLICY REVIEW</div><h2>审核并启用授权规则</h2><p class="modal-intro">正在读取规则…</p>`;dialog.showModal();const dismiss=()=>dialog.close();try{const results=await Promise.all([loadScenarioPolicies(scenarioId),load("scenario-slices"),load("principals"),load("resource-types"),load("actions")]);const policies=results[0],scene=(results[1]||[]).find(x=>x.id===scenarioId)||{};const pending=((policies.rules)||[]).filter(r=>r.policy_status!=="active"&&!((r.problems)||[]).length).length;content.innerHTML=`<div class="modal-kicker">POLICY REVIEW</div><h2>审核并启用授权规则</h2><p class="modal-intro">${esc(scene.analysis?.title||scenarioId)} · 启用只让判定引擎读取这些规则，不会执行任何操作。${policies.segmentation_mode==="segmented"?" 分组场景的规则暂不支持启用。":""}</p><div style="display:grid;gap:10px">${scenarioPolicyListHtml(policies)}</div><div class="modal-actions"><button type="button" class="button" id="close-review">关闭</button>${pending?`<button type="button" class="button primary" id="activate-review">启用全部可执行规则（${pending}）</button>`:""}</div>`;$("#close-review").onclick=dismiss;const all=$("#activate-review");if(all)all.onclick=async()=>{dismiss();await setScenarioPolicyStatus(scenarioId,"active")};content.querySelectorAll("[data-activate-policy]").forEach(b=>b.onclick=async()=>{dismiss();await setScenarioPolicyStatus(scenarioId,"active",[b.dataset.activatePolicy])});content.querySelectorAll("[data-suspend-policy]").forEach(b=>b.onclick=async()=>{dismiss();await setScenarioPolicyStatus(scenarioId,"suspended",[b.dataset.suspendPolicy])})}catch(error){content.innerHTML=`<div class="modal-kicker">POLICY REVIEW</div><h2>审核并启用授权规则</h2><div class="form-error">${esc(error.message)}</div><div class="modal-actions"><button type="button" class="button" id="close-review">关闭</button></div>`;$("#close-review").onclick=dismiss}}
async function renderProfessionalInstances(view){
 const [slices,allEntries,defs]=await Promise.all([load("scenario-slices"),load("knowledge-entries"),load("scenario-definitions")]);
 const mine=slices.filter(x=>(x.scenario_profile||{}).kind==="professional"&&x.status==="confirmed");
 const ids=new Set(mine.map(x=>x.id));
 const entries=allEntries.filter(e=>ids.has(e.slice_id));
 const active=entries.filter(e=>e.review_state==="active");
 view.innerHTML=`${proModeButtons()}
  
 ${proEnabledSlicesHtml(defs, mine)}
  ${titleBlock("PROFESSIONAL INSTANCE","已启用的判断条目","这是你的专业判断在对外可用时的形态——只列已启用的条目，并显示各自的前提与依据")}
 <section class="panel collection-panel">
  <div class="collection-toolbar"><span class="record-count"><span>已启用</span> ${active.length} <span>条</span> · <span>全部</span> ${entries.length} <span>条</span></span></div>
  <div class="table-wrap"><table><thead><tr><th>所属场景</th><th>前提</th><th>结论</th><th>依据</th><th>权威级别</th></tr></thead>
  <tbody>${active.map(e=>`<tr><td>${esc((defs.find(d=>d.id===(mine.find(s=>s.id===e.slice_id)||{}).scenario_definition_id)||{}).display_name_zh||"—")}</td>
   <td>${esc(premiseText(e.premise)||"—")}</td><td>${esc(e.conclusion||"")}</td><td>${esc(e.basis||"—")}</td><td>${esc(PRO_AUTHORITY[e.authority]||e.authority||"—")}</td></tr>`).join("")}</tbody></table></div>
  <div class="empty-state" ${active.length?"hidden":""}><div class="empty-icon">◇</div>还没有已启用的判断条目，请先在场景切片页复核启用</div>
 </section>`;
 
}

async function renderScenarioInstances(view){
 if(professionalMode){return renderProfessionalInstances(view)}
 const rows=(await load("scenario-slices")).filter(x=>!isProSlice(x));
 document.querySelector('[data-count="scenario-instances"]')?.replaceChildren(document.createTextNode(rows.length));
 const selected=rows.find(x=>x.id===activeInstanceId)||null;const a=selected?.analysis||{};const scope=a.scope||{};
 if(!selected){const allRules=await load("authorizations");const ruleStats=id=>{const mine=allRules.filter(r=>String(r.source||"")==="scenario-slice:"+id);return{total:mine.length,active:mine.filter(r=>r.policy_status==="active").length}};view.innerHTML=`${proModeButtons()}${titleBlock("ONTOLOGY INSTANCES","场景实例","统一查看和维护由场景切片确认写入本体的实例。场景范围和每次执行必须提供的信息都在这里管理。")}<section class="panel" style="padding:18px"><div class="panel-title">已有场景实例 · ${rows.length}</div>${rows.length?`<div style="display:grid;gap:8px;margin-top:12px">${rows.map(x=>`<div style="display:flex;gap:8px;align-items:center"><button class="button" style="flex:1;justify-content:flex-start;height:auto;padding:12px;text-align:left" data-open-instance="${esc(x.id)}"><strong>${esc(x.analysis?.title||x.original_text?.slice(0,80)||"场景实例")}</strong><span class="muted" style="margin-left:auto">${x.status==="confirmed"?"已写入本体":"分析草稿"} · ${esc(formatTime(x.updated_at))}</span></button>${(()=>{const s=ruleStats(x.id);if(x.status!=="confirmed"||!s.total)return "";return `<span class="badge ${s.active?"active":"pending"}" style="white-space:nowrap">${s.active?`${s.active} 条生效中`:`${s.total} 条未生效`}</span><button class="button" data-review-policy="${esc(x.id)}" style="white-space:nowrap">审核并启用</button>`})()}<button class="button danger" data-remove-instance="${esc(x.id)}">删除</button></div>`).join("")}</div>`:`<div class="empty-state">还没有保存的场景。先到“场景切片”创建并确认一个场景。</div>`}</section>`;$$('[data-open-instance]').forEach(b=>b.onclick=()=>{activeInstanceId=b.dataset.openInstance;render()});$$('[data-remove-instance]').forEach(b=>b.onclick=()=>deleteScenario(b.dataset.removeInstance));$$('[data-review-policy]').forEach(b=>b.onclick=()=>openPolicyReview(b.dataset.reviewPolicy));return}
 const excludedContext=new Set([scope.dimension||"destination_city","destination_city","district","area"]);
 const fallbackPrefs=new Map();for(const fact of (a.facts||[])){if(!fact||fact.source==="suggestion"||(scope.mode!=="by_dimension"&&excludedContext.has(fact.name)))continue;const field=({min_price:"price_min",max_price:"price_max"})[fact.name]||fact.name;if(!fallbackPrefs.has(field))fallbackPrefs.set(field,{field,label:fact.label||field,value:fact.value,strength:"must"})}const preferences=Array.isArray(a.instance_preferences)?a.instance_preferences:[...fallbackPrefs.values()];
 const hotel=(a.resource_types||[]).some(x=>/酒店|旅馆|宾馆/.test(x.name||""))||/酒店|旅馆|宾馆/.test(selected.original_text||"");
 const required=Array.isArray(a.required_inputs)&&a.required_inputs.length?a.required_inputs:(hotel?[{name:"destination_city",label:"目的城市",type:"string",required:true},{name:"check_in_date",label:"入住日期",type:"date",required:true},{name:"check_out_date",label:"退房日期",type:"date",required:true},{name:"guest_count",label:"入住人数",type:"number",required:true}]:[]);const history=Array.isArray(a.evolution_log)?[...a.evolution_log].reverse():[];
 await Promise.all([load("principals"),load("resource-types"),load("actions")]);
 const policies=await loadScenarioPolicies(selected.id);
 view.innerHTML=`${proModeButtons()}${titleBlock("ONTOLOGY INSTANCES","编辑场景实例","修改场景偏好范围、分组和每次执行必须收集的信息。保存后更新统一实例。",'<button class="button" id="back-instances">← 返回列表</button>')}<form id="instance-form"><section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">场景基本信息</div><div class="form-grid" style="margin-top:12px"><label class="field"><span class="field-label">场景名称</span><input class="input" id="instance-title" required value="${esc(a.title||"")}" placeholder="例如：预定酒店"></label></div></section>${scenarioSegmentationEditor(a,"instance")}
 <section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">智能体每次执行前必须收集</div><p class="panel-caption">这是元模型中的 ParamDefinition。字段定义必填；本次还没有具体值时，由智能体向用户询问。</p><div id="instance-required" style="display:grid;gap:8px;margin-top:12px">${required.map(x=>`<div class="form-grid instance-required-row" data-pkeys='${esc(JSON.stringify(x.profile_keys||[]))}' style="grid-template-columns:150px 1fr 1fr 110px auto"><select class="select" data-required-tier style="font-size:11px;padding:2px 4px;width:auto;max-width:150px"><option value="required" ${x.role!=="preference"&&x.role!=="both"?"selected":""}>每次必填</option><option value="preference" ${x.role==="preference"?"selected":""}>长期偏好</option><option value="both" ${x.role==="both"?"selected":""}>两者兼有</option></select>${(x.role||x.role_reason)?`<div class="panel-caption" style="grid-column:1/-1" title="${esc(x.role_reason||"")}">模型判断：<strong>${{required:"每次必填",preference:"长期偏好",both:"两者兼有（立场+每次取值）"}[x.role]||"未标注"}</strong>${x.role_reason?` · ${esc(x.role_reason)}`:""}</div>`:""}<input class="input" data-required-name placeholder="字段名，例如 check_in_date" value="${esc(x.name||"")}" required><input class="input" data-required-label placeholder="用户看到的名称，例如 入住日期" value="${esc(x.label||"")}" required><select class="select" data-required-type>${["string","number","bool","date"].map(t=>`<option value="${t}" ${(x.type||"string")==t||(x.type==="boolean"&&t==="bool")?"selected":""}>${({string:"文本",number:"数字",bool:"是/否",date:"日期"})[t]}</option>`).join("")}</select><select class="select" data-required-source style="font-size:11px;padding:2px 4px;width:auto"><option value="caller" ${(x.source||"caller")!=="profile"?"selected":""}>调用方提交</option><option value="profile" ${x.source==="profile"?"selected":""}>我的资料</option></select><button type="button" class="button danger" data-remove-row>移除</button></div>`).join("")}</div><button type="button" class="button" id="add-required" style="margin-top:10px">＋ 添加必填信息</button><p class="form-hint">酒店预订常见必填项：目的城市、入住日期、退房日期、入住人数。</p></section><div id="instance-error" class="form-error"></div><div style="display:flex;justify-content:flex-end;gap:8px;margin-bottom:20px"><button class="button" type="button" id="cancel-instance">取消</button><button class="button primary" type="submit">保存场景实例</button></div></form>${scenarioPolicyBlock(selected.id,a,policies)}${history.length?`<section class="panel" style="padding:18px;margin-bottom:20px"><div class="panel-title">实例演进与执行记录 · ${history.length}</div><p class="panel-caption">记录智能体本次收集的信息、用户确认和实例变更；长期偏好更新包含修订版本与前后值。</p><div style="display:grid;gap:9px;margin-top:12px">${history.map(item=>`<div class="decision-detail" style="margin:0"><strong>${item.mode==="instance_preference"?"已确认的长期偏好更新":"本次执行输入"} · ${esc(item.label||item.field||"")}</strong><div class="panel-caption">${esc(item.timestamp||"")} · 执行 ${esc(item.run_id||"未提供")} · ${item.mode==="instance_preference"?`版本 ${esc(item.from_revision??"?")} → ${esc(item.revision??"?")} · 原值 ${esc(item.previous_value??"无")} → 新值 ${esc(item.value??"")}`:`仅记录于本次执行：${esc(item.value??"")}`}</div><div class="panel-caption">用户原话：${esc(item.user_input||"—")}</div></div>`).join("")}</div></section>`:`<section class="panel" style="padding:18px;margin-bottom:20px"><div class="panel-title">实例演进与执行记录</div><p class="panel-caption">智能体收集的信息和经你确认的长期偏好更新，会在此留下可查记录。</p><div class="panel-caption" style="margin-top:10px">暂无记录</div></section>`}`;
 // 没有可启用规则时给出明确出路：先编译规则，或补充描述后重新分析（否则页面是个死路）
 if (!policies.length) {
   view.insertAdjacentHTML("afterbegin",
     '<section class="panel" style="padding:14px 16px;margin-bottom:12px;background:#fffaf0;border:1px solid #f0dcb4">' +
     '<div class="panel-title">这个场景还没有可启用的规则</div>' +
     '<p class="panel-caption" style="margin:6px 0 0">规则是「启用」的前提。请：① 在上方选择一个被授权主体，点【编译规则】；' +
     '② 若编译出 0 条，说明场景描述里没有可执行的动作或必填信息，请回到场景描述补充后再分析一次' +
     '（例如：预订机票时先问清出发城市、到达城市、出发日期、人数，价格不超过 3000 元）。</p></section>');
 }
 // 来源选「我的资料」时，行内展开一个多选框，列出资料库里现有的项，勾哪几项就用哪几项。
let _profileCache=null;
async function renderPkeyPicker(row){
  const sel=row.querySelector("[data-required-source]");
  if(!sel||sel.value!=="profile"){ const old=row.querySelector("[data-pkey-wrap]"); if(old)old.remove(); return }
  if(row.querySelector("[data-pkey-wrap]")) return;
  if(!_profileCache){ try{ _profileCache=(await api("/v1/profiles"))||{} }catch(e){ _profileCache={} } }
  let savedKeys=[]; try{ savedKeys=JSON.parse(row.dataset.pkeys||"[]")||[] }catch(e){ savedKeys=[] }
  const items=[];
  ((_profileCache.items)||[]).forEach(pf=>(pf.items||[]).forEach(it=>{
    const k=String(it.label||it.key||"").trim(); if(k) items.push({k, p:pf.display_name_zh||"资料", v:it.value});
  }));
  const wrap=document.createElement("div");
  wrap.setAttribute("data-pkey-wrap","1");
  wrap.className="panel-caption";
  wrap.style.gridColumn="1/-1";
  wrap.innerHTML= items.length
    ? `<div style="margin-top:4px">勾选要由本机提供的资料项（可多选）：
         <select class="select" data-required-pkeys multiple size="${Math.min(4,items.length)}" style="min-width:260px;margin-left:6px">
           ${items.map(x=>`<option value="${esc(x.k)}" ${(savedKeys||[]).includes(x.k)?"selected":""}>${esc(x.p)} → ${esc(x.k)}（${x.v?esc(maskValue(x.v)):"未填写值"}）</option>`).join("")}
         </select> <span class="panel-caption" data-pk-count style="margin-left:6px"></span></div>`
    : `<div style="margin-top:4px">资料库里还没有内容，请先到【个人资料】页添加。</div>`;
  row.appendChild(wrap);
  const pk=wrap.querySelector("[data-required-pkeys]");
  const cnt=wrap.querySelector("[data-pk-count]");
  const sync=()=>{ if(cnt) cnt.textContent="已勾选 "+(pk?pk.selectedOptions.length:0)+" 项"; };
  if(pk){ pk.onchange=()=>{ sync(); const first=pk.selectedOptions[0];
      if(first){ const n=row.querySelector("[data-required-name]"), l=row.querySelector("[data-required-label]");
        if(n&&!n.value.trim()) n.value="profile_field_"+(row.dataset.idx||"1");
        if(l&&!l.value.trim()) l.value=first.value; } }; sync(); }
}
function applyProfileRowMode(row){
  if(!row) return;
  const sel=row.querySelector("[data-required-source]");
  const byProfile = !!(sel && sel.value==="profile");
  row.querySelectorAll("[data-required-name],[data-required-label]").forEach(inp=>{ inp.required = !byProfile; });
}
function bindRequiredSources(view){
  view.querySelectorAll("[data-required-source]").forEach(sel=>{
    sel.onchange=()=>{const _r=sel.closest(".instance-required-row")||sel.parentElement;applyProfileRowMode(_r);renderPkeyPicker(_r)};
    applyProfileRowMode(sel.closest(".instance-required-row")||sel.parentElement);
    if(sel.value==="profile") renderPkeyPicker(sel.closest(".instance-required-row")||sel.parentElement);
  });
}
const addRequired=()=>{$("#instance-required").insertAdjacentHTML("beforeend",`<div class="form-grid instance-required-row" style="grid-template-columns:150px 1fr 1fr 110px auto"><select class="select" data-required-tier style="font-size:11px;padding:2px 4px;width:auto;max-width:150px"><option value="required" selected>每次必填</option><option value="preference" >长期偏好</option><option value="both" >两者兼有</option></select><input class="input" data-required-name placeholder="字段名，例如 check_in_date" required><input class="input" data-required-label placeholder="用户看到的名称，例如 入住日期" required><select class="select" data-required-type><option value="string">文本</option><option value="number">数字</option><option value="bool">是/否</option><option value="date">日期</option></select><select class="select" data-required-source style="font-size:11px;padding:2px 4px;width:auto"><option value="caller">调用方提交</option><option value="profile">我的资料</option></select><button type="button" class="button danger" data-remove-row>移除</button></div>`);bindRequiredSources(view);};
    bindRequiredSources(view);
 $("#back-instances").onclick=()=>{activeInstanceId=null;render()};$("#cancel-instance").onclick=()=>{activeInstanceId=null;render()};$("#add-required").onclick=addRequired;$$('[data-remove-row]',view).forEach(b=>b.onclick=()=>b.parentElement.remove());bindSegmentationEditor("instance",a);
 bindRequiredSources(view);
$$('[data-activate-policy]',view).forEach(b=>b.onclick=()=>setScenarioPolicyStatus(selected.id,"active",[b.dataset.activatePolicy]));
 $$('[data-suspend-policy]',view).forEach(b=>b.onclick=()=>setScenarioPolicyStatus(selected.id,"suspended",[b.dataset.suspendPolicy]));
$$('[data-delete-policy]',view).forEach(b=>b.onclick=async()=>{
  if(!confirm("删除这条规则？会先暂停再删除，删除后不可恢复（留痕仍在审计记录里）。"))return;
  try{await api(`/v1/scenario-slices/${encodeURIComponent(selected.id)}/policies/${encodeURIComponent(b.dataset.deletePolicy)}`,{method:"DELETE"});
    delete cache.authorizations;delete cache["scenario-slices"];toast("规则已删除");render();
  }catch(err){if(!(err instanceof AuthRequired))toast(err.message,true)}
});
$$('[data-edit-rule]',view).forEach(b=>b.onclick=async()=>{
  const rid=b.dataset.editRule;
  const r=((policies&&policies.rules)||[]).filter(x=>String(x.authorization_id)===String(rid))[0];
  if(!r){toast("找不到这条规则，请刷新后重试",true);return}
  const cs=(r.conditions||[]).slice();
  if(!cs.length){toast("这条规则没有条件（无条件放行），无法用本功能改。请先暂停它，必要时删除后重建。",true);return}
  const show=c=>{const v=(c.value&&typeof c.value==="object")?c.value:{key:"",value:c.value};
    const op=c.type==="numeric_lte"?"≤":c.type==="numeric_gte"?"≥":"=";
    return (v.key||"字段")+" "+op+" "+v.value};
  let idx=0;
  if(cs.length===1){idx=0;}
  else{
    const list=cs.map((c,k)=>(k+1)+") "+show(c)).join("\n");
    const pick=prompt("这条规则有 "+cs.length+" 个条件：\n"+list+"\n\n请输入要修改的编号（1-"+cs.length+"）：","1");
    if(pick===null)return;
    idx=Number(String(pick).trim())-1;
    if(!(idx>=0&&idx<cs.length)){toast("编号不对，请输入 1 到 "+cs.length+" 之间的数字",true);return}
  }
  const c=cs[idx], v=(c.value&&typeof c.value==="object")?c.value:{key:"",value:c.value};
  const cur=String(v.value);
  const nv=prompt("正在修改第 "+(idx+1)+" 个条件："+show(c)+"\n请输入新的数值：",cur);
  if(nv===null)return;
  const nv2=String(nv).trim(); if(nv2==="" || nv2===cur){toast("没有改动");return}
  const isNum=!isNaN(Number(nv2));
  const ncond=Object.assign({},c,{value:Object.assign({},v,{value:isNum?Number(nv2):nv2})});
  const conds=cs.map((x,k)=>k===idx?ncond:x);
  try{await api(`/v1/scenario-slices/${encodeURIComponent(selected.id)}/policies/${encodeURIComponent(rid)}`,{method:"PATCH",
    body:JSON.stringify({conditions:conds})});
    delete cache.authorizations;delete cache["scenario-slices"];toast("已更新，规则回到草稿，请重新启用");render();
  }catch(err){if(!(err instanceof AuthRequired))toast(err.message,true)}
});
$$('[data-add-policy]',view).forEach(b=>b.onclick=async()=>{
  // 沿用已存在规则的主体（用户不必再选一次）；没有既有规则时才回落到下拉框。
  const _rules=(policies&&policies.rules)||[];
  const _base=_rules[0]||null;
  const grantor=_base?( _base.grantor_id||_base.grantee_id ):( $("#compile-grantee")?.value||"" );
  const grantee=_base?( _base.grantee_id||_base.grantor_id ):( $("#compile-grantee")?.value||"" );
  if(!grantor||!grantee){
    const _sel=$("#compile-grantee");
    toast(_sel&&_sel.options&&_sel.options.length
      ?"请先选择被授权主体：就在「生成授权规则」按钮旁边的下拉框里"
      :"还没有主体可选。请先到左侧【主体】菜单新建一个「本人」（类型选 person），再回到本页",true);
    return}
  try{
    await api(`/v1/scenario-slices/${encodeURIComponent(selected.id)}/policies`,{method:"POST",
      body:JSON.stringify({grantor_id:grantor,grantee_id:grantee,effect:"ask",conditions:[]})});
    delete cache.authorizations;delete cache["scenario-slices"];
    toast("已新增一条草稿规则（默认：暂停并询问，最保守）。编辑功能还没做，启用前请谨慎；高风险动作不要直接启用无条件允许。");render();
  }catch(err){if(!(err instanceof AuthRequired))toast(err.message,true)}
});
 const compileButton=$("#compile-rules");
 if(compileButton)compileButton.onclick=async()=>{
   const error=$("#compile-error");error.textContent="";
   const grantee=$("#compile-grantee")?.value;
   if(!grantee){error.textContent="请先添加一个主体。";return}
   compileButton.disabled=true;
   try{
     const result=await api(`/v1/scenario-slices/${encodeURIComponent(selected.id)}/compile`,{method:"POST",body:JSON.stringify({grantor_id:grantee})});
     delete cache.authorizations;delete cache["scenario-slices"];
     const rn=result.compile_report||[];
     toast(rn.length?`已生成 ${(result.created||[]).length} 条规则草稿；${rn.map(n=>`策略${n.policy}：${n.reason}`).join("；")}`:`已生成 ${(result.created||[]).length} 条规则草稿`);render();
   }catch(err){if(!(err instanceof AuthRequired))error.textContent=err.message;compileButton.disabled=false}
 };
 $("#instance-form").onsubmit=async e=>{e.preventDefault();const error=$("#instance-error");error.textContent="";const segmentation=readScenarioSegmentation("instance",a.segmentation||{});if(!segmentation)return;const nextRequired=$$(".instance-required-row",view).map(row=>({name:$('[data-required-name]',row).value.trim(),label:$('[data-required-label]',row).value.trim(),type:$('[data-required-type]',row).value,source:($('[data-required-source]',row)?.value||"caller"),profile_keys:Array.from(row.querySelectorAll('[data-required-pkeys] option:checked')).map(o=>o.value),required:true}));
nextRequired.forEach((it,i)=>{if(it.source==="profile"){if(!it.name)it.name="profile_field_"+(i+1);if(!it.label)it.label=(it.profile_keys&&it.profile_keys[0])||it.name;}});
 // 改档：偏好行上选了「每次必填」或「两者兼有」的字段，并入必填清单（不覆盖已存在的同名项）。
 for(const row of $$(".seg-pref-row",view)){const tier=$("[data-seg-tier]",row)?.value||"";if(tier!=="required"&&tier!=="both")continue;const name=String(row.dataset.segField||"").trim();if(!name||nextRequired.some(x=>x.name===name))continue;nextRequired.push({profile_keys:(src==="profile"?pkeys:[]),name,label:String(row.dataset.segLabel||name).trim(),type:String(row.dataset.segType||"string"),required:true, source: src });}
 // 反向改档：必填行选了「长期偏好」的，从必填清单移除并转成偏好（值留空，待你到偏好区填写）。
 for(const row of $$(".instance-required-row",view)){const tier=$("[data-required-tier]",row)?.value||"required";if(tier!=="preference")continue;
  const name=String($("[data-required-name]",row)?.value||"").trim();if(!name)continue;
  const label=String($("[data-required-label]",row)?.value||name).trim();
  const type=String($("[data-required-type]",row)?.value||"string");
 const src=String($("[data-required-source]",row)?.value||"caller");
 const pkeys=Array.from(row.querySelectorAll("[data-required-pkeys] option:checked")).map(o=>o.value);
  for(let i=nextRequired.length-1;i>=0;i--)if(nextRequired[i].name===name)nextRequired.splice(i,1);
  if(!Array.isArray(segmentation.global_preferences))segmentation.global_preferences=[];
  if(!segmentation.global_preferences.some(p=>p.field===name))
    segmentation.global_preferences.push({field:name,label,type,value:"",operator:"equals",strength:"must"});}try{const res=await api(`/v1/scenario-slices/${encodeURIComponent(selected.id)}/instance`,{method:"PATCH",body:JSON.stringify({title:$("#instance-title").value.trim(),segmentation,required_inputs:nextRequired})});cache["scenario-slices"]=rows.map(x=>x.id===selected.id?res.scenario:x);toast("场景实例已保存");activeInstanceId=null;render()}catch(err){error.textContent=err.message}};
}
// ===== Professional track: skill-framework preview (R3'.1) =====
// The case data comes from the caller and the framework stays local; the page shows only the decision package.
let proEvalResult = null;
let proBacktest = null;
let proEvalDefId = null;

function proInputField(f){
  const name=esc(f.name||"");
  if((f.type||"")==="bool")
    return `<label class="field" style="min-width:160px"><span class="field-label">${name}</span>
      <select class="select" data-pro-bool="${name}"><option value="true">是</option><option value="false">否</option></select></label>`;
  if((f.type||"")==="multi")
    return `<label class="field" style="min-width:200px"><span class="field-label">${name}</span>
      <span class="field-caption">可多选</span>
      ${(f.values||[]).map((v,i)=>`<label class="pro-check"><input type="checkbox" data-pro-multi="${name}" value="${esc(v)}">${esc(v)}</label>`).join("")}</label>`;
  if((f.type||"")==="enum"&&Array.isArray(f.values)&&f.values.length)
    return `<label class="field" style="min-width:160px"><span class="field-label">${name}</span>
      <select class="select" data-pro-input="${name}">${f.values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join("")}</select></label>`;
  if((f.type||"")==="number")
    return `<label class="field" style="min-width:160px"><span class="field-label">${name}</span>
      <input class="input" type="number" step="any" data-pro-input="${name}"></label>`;
  return `<label class="field" style="min-width:160px"><span class="field-label">${name}</span>
    <input class="input" data-pro-input="${name}"></label>`;
}

function proPreviewNote(){
  return `<section class="panel" style="padding:14px 16px;margin-bottom:16px">
   <div class="panel-caption" style="margin:0">这是预演：不写判定记录，也不产生审计号与数字签名。真实调用交付时还会附上审计号、有效期、内容指纹与签名状态；交付层级取你在场景切片页设置的默认层级</div>
  </section>`;
}

function proDeliveryHtml(pkg){
  if(!pkg) return "";
  const fp=String(pkg.content_fingerprint||"");
  const signed=pkg.signature_status!=="not_implemented"&&pkg.owner_signature;
  return `<section class="panel" style="padding:16px;margin-bottom:16px">
   <div class="panel-title">本次交付信息</div>
   <div class="panel-caption" style="margin-top:6px">交付层级：<strong>${esc(pkg.tier||"—")}</strong>（按调用方付费层裁剪）</div>
   ${pkg.professional_insight?`<div style="margin-top:10px"><div class="panel-caption" style="margin:0">专业洞察</div><div>${esc(pkg.professional_insight)}</div></div>`:""}
   ${pkg.owner_credentials?`<div style="margin-top:10px"><div class="panel-caption" style="margin:0">资历</div><div>${esc(pkg.owner_credentials)}</div></div>`:""}
   <div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:12px">
    <div><div class="panel-caption" style="margin:0">审计号</div><div class="mono">${esc(pkg.audit_id||"—")}</div></div>
    <div><div class="panel-caption" style="margin:0">有效期至</div><div>${esc(pkg.valid_until||"—")}</div></div>
    <div><div class="panel-caption" style="margin:0">内容指纹</div><div class="mono">${fp?esc(fp.slice(0,16))+"…":"—"}</div></div>
    <div><div class="panel-caption" style="margin:0">数字签名</div><div>${signed?esc(String(pkg.owner_signature)):'<span class="muted">尚未实现</span>'}</div></div>
   </div></section>`;
}

function proPackageHtml(pkg){
  if(!pkg) return "";
  const sev=({"低":"低","中":"中","高":"高","极高":"极高"})[pkg.severity]||pkg.severity||"—";
  const conf=pkg.confidence==null?`<span class="muted">未验证</span>`:`${pkg.confidence}（${esc(pkg.confidence_status||"")}）`;
  return `<section class="panel" style="padding:18px;margin-bottom:16px">
   <div style="display:flex;gap:18px;flex-wrap:wrap;align-items:baseline">
    <div><div class="panel-caption" style="margin:0">结论</div><div style="font-size:20px;font-weight:600">${esc(pkg.decision||"—")}</div></div>
    <div><div class="panel-caption" style="margin:0">严重度</div><div style="font-size:20px">${esc(sev)}</div></div>
    <div><div class="panel-caption" style="margin:0">置信度</div><div>${conf}</div></div>
    ${pkg.confidence_basis?`<div><div class="panel-caption" style="margin:0">来源</div><div>${esc(pkg.confidence_basis)}</div></div>`:""}
   </div>
   ${pkg.rule_cited?`<div class="panel-caption" style="margin-top:10px">引用框架：${esc(pkg.rule_cited)}</div>`:""}
  </section>
  <section class="panel" style="padding:18px;margin-bottom:16px">
   <div class="panel-title">推理路径</div>
   <div style="display:grid;gap:6px;margin-top:10px">
    ${(pkg.reasoning_path||[]).map(x=>`<div style="display:flex;gap:10px"><span class="muted" style="min-width:22px">${esc(String(x.step))}</span>
      <span style="min-width:96px"><strong>${esc(x.name)}</strong></span><span>${esc(x.detail)}</span></div>`).join("")}
   </div>
  </section>
  <section class="panel collection-panel">
   <div class="collection-toolbar"><span class="record-count">证据</span></div>
   <div class="table-wrap"><table><thead><tr><th>因素</th><th>取值</th><th>基准</th><th>动态阈值</th><th>来源</th></tr></thead>
   <tbody>${(pkg.evidence||[]).map(e=>`<tr><td>${esc(e.factor||"")}</td><td>${esc(String(e.value ?? "—"))}</td>
     <td>${esc(e.benchmark||"—")}</td><td>${esc(e.dynamic_threshold||"—")}</td><td>${esc(e.source||"—")}</td></tr>`).join("")}</tbody></table></div>
  </section>`;
}

function proBacktestHtml(rep){
  if(!rep) return "";
  const pct=rep.accuracy==null?"—":(rep.accuracy*100).toFixed(1)+"%";
  return `<div style="margin-top:12px">
   <div style="display:flex;gap:18px;flex-wrap:wrap">
    <div><div class="panel-caption" style="margin:0">样本数</div><div style="font-size:18px">${esc(String(rep.total))}</div></div>
    <div><div class="panel-caption" style="margin:0">一致</div><div style="font-size:18px">${esc(String(rep.matched))}</div></div>
    <div><div class="panel-caption" style="margin:0">不一致</div><div style="font-size:18px">${esc(String(rep.mismatched))}</div></div>
    <div><div class="panel-caption" style="margin:0">准确率</div><div style="font-size:18px">${pct}</div></div>
   </div>
   ${(rep.mismatch_detail||[]).length?`<div class="panel-caption" style="margin-top:10px">不一致明细（最多 20 条）</div>
   <div class="table-wrap"><table><thead><tr><th>案例</th><th>实际结果</th><th>框架结论</th><th>严重度</th></tr></thead>
   <tbody>${rep.mismatch_detail.map(m=>`<tr><td>${esc(m.case_id||"")}</td><td>${esc(String(m.expected??""))}</td>
     <td>${esc(String(m.actual??""))}</td><td>${esc(String(m.severity??""))}</td></tr>`).join("")}</tbody></table></div>`:""}
  </div>`;
}

async function renderProfessionalPreview(view){
  const defs=(await load("scenario-slices")).filter(x=>(x.scenario_profile||{}).kind==="professional");   // The preview judges against my slice
  if(!proEvalDefId||!defs.some(d=>d.id===proEvalDefId)) proEvalDefId=defs[0]?.id||null;
  const def=defs.find(d=>d.id===proEvalDefId)||null;
  const fw=(def?.framework)||null;
  const opts=defs.map(d=>`<option value="${esc(d.id)}" ${d.id===proEvalDefId?"selected":""}>${esc((d.analysis&&d.analysis.title)||d.original_text||d.id)}</option>`).join("");
  view.innerHTML=`${proModeButtons()}
  ${titleBlock("SKILL FRAMEWORK","专业预演","用一组标的数据跑一遍你的判断框架：结论、严重度、推理路径与证据都会列出来。预演不写判定记录，也不执行任何操作。")}
  <section class="panel" style="padding:18px;margin-bottom:16px">
   <div class="panel-title">第一步 · 选场景与框架</div>
   <div class="panel-caption">框架留在本机；标的数据只用于这一次判定。</div>
   <div style="display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap">
    <select class="select" id="pe-def" style="max-width:320px">${opts||'<option value="">暂无专业场景</option>'}</select>
    ${fw?`<span class="badge">框架已配置 · ${esc(fw.framework_version||fw.skill_id||"")}</span>`:`<span class="badge">尚未配置框架</span>`}
   </div>
   ${fw?"":`<div style="margin-top:12px">
     <div class="panel-caption">把技能框架的 JSON 粘贴进来（导入后即可判定；框架只保存在本机）。</div>
     <textarea class="input mono" id="pe-framework" rows="8" style="width:100%;margin-top:6px" placeholder='{"framework_version":"...","industry_map":{},"thresholds":{},"signals":[],"combination_rules":[],"exception_rules":[],"signal_priority":[]}'></textarea>
     <div style="margin-top:8px"><button class="button primary" id="pe-save-framework">保存框架</button></div>
   </div>`}
  </section>
  ${fw?`<section class="panel" style="padding:18px;margin-bottom:16px">
   <div class="panel-title">第二步 · 填标的数据</div>
   <div class="panel-caption">字段来自这条切片里「我要知道的信息」——在「场景切片」页改动并保存后，这里会跟着变。</div>
   <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px">
    ${(fw.inputs||[]).map(proInputField).join("")||'<div class="panel-caption" style="margin:0">框架没有声明输入字段</div>'}
   </div>
   <div style="margin-top:14px"><button class="button primary" id="pe-run">判定</button></div>
  </section>`:""}
  ${fw?`<section class="panel" style="padding:18px;margin-bottom:16px">
   <div class="panel-title">置信度与回测</div>
   <div class="panel-caption">导入历史案例跑一遍框架，看它与实际结果的一致率；保存后判定包会带上置信度。对比口径：结论与实际结果逐字相等。</div>
   <div style="margin-top:10px">当前置信度：
    ${def?.confidence==null?`<span class="muted">未验证</span>`:`<strong>${esc(String(def.confidence))}</strong>（${esc(def.confidence_status||"")}）`}
    ${def?.confidence_basis?` · ${esc(def.confidence_basis)}`:""}</div>
   <textarea class="input mono" id="pe-cases" rows="6" style="width:100%;margin-top:10px" placeholder='[{"case_id":"CASE-001","inputs":{"字段名":值},"actual_result":"当时实际得出的结论"}]'></textarea>
   <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
    <button class="button" id="pe-backtest">跑回测</button>
    <button class="button primary" id="pe-persist">保存为置信度</button>
   </div>
   <div id="pe-backtest-result">${proBacktestHtml(proBacktest)}</div>
  </section>`:""}
  <div id="pe-result">${proPackageHtml(proEvalResult)}${proDeliveryHtml(proEvalResult)}</div>
  `;
  document.querySelectorAll("[data-pro-mode]").forEach(b=>b.onclick=()=>{professionalMode=b.dataset.proMode==="professional";proEvalResult=null;render()});
  const sel=$("#pe-def"); if(sel) sel.onchange=()=>{proEvalDefId=sel.value;proEvalResult=null;render()};
  const saveFw=$("#pe-save-framework"); if(saveFw) saveFw.onclick=async()=>{
    let parsed; try{ parsed=JSON.parse($("#pe-framework").value); }catch(e){ alert("框架 JSON 解析失败："+e.message); return; }
    if(typeof parsed!=="object"||!parsed){ alert("框架必须是一个对象。"); return; }
    await api(`/v1/scenario-slices/${encodeURIComponent(proEvalDefId)}`,{method:"PATCH",body:JSON.stringify({framework:parsed})});
    cache["scenario-definitions"]=null; render(); };
  const parseCases=()=>{ try{ return JSON.parse($("#pe-cases").value); }catch(e){ alert("案例 JSON 解析失败："+e.message); return null; } };
  const sendFeedback=async(verdict)=>{
    const out=await api(`/v1/scenario-slices/${encodeURIComponent(proEvalDefId)}/judgment-feedback`,{method:"POST",body:JSON.stringify({verdict})});
    const h=$("#pe-fb-hint");
    if(h) h.textContent=out&&out.confidence_status?("已记录：共 "+out.feedback_total+" 次反馈，一致率 "+Math.round((out.accuracy_from_feedback||0)*100)+"%，置信度 "+out.confidence_status):"反馈未记录";
    cache["scenario-definitions"]=null; };
  const fbOk=$("#pe-fb-ok"); if(fbOk) fbOk.onclick=()=>sendFeedback("accurate");
  const fbNo=$("#pe-fb-no"); if(fbNo) fbNo.onclick=()=>sendFeedback("inaccurate");
  const bt=$("#pe-backtest"); if(bt) bt.onclick=async()=>{
    const cases=parseCases(); if(!cases) return;
    const rep=await api(`/v1/scenario-slices/${encodeURIComponent(proEvalDefId)}/backtest`,{method:"POST",body:JSON.stringify({cases})});
    if(rep&&rep.total!==undefined){ proBacktest=rep; $("#pe-backtest-result").innerHTML=proBacktestHtml(rep); }
    else { proBacktest=null; $("#pe-backtest-result").innerHTML=`<div class="panel-caption" style="margin-top:10px">回测未完成：${esc((rep&&(rep.detail||rep.error))||"案例或框架有问题")}</div>`; } };
  const ps=$("#pe-persist"); if(ps) ps.onclick=async()=>{
    const cases=parseCases(); if(!cases) return;
    const rep=await api(`/v1/scenario-slices/${encodeURIComponent(proEvalDefId)}/backtest`,{method:"POST",body:JSON.stringify({cases,persist:true})});
    if(rep&&rep.persisted){ proBacktest=rep; cache["scenario-definitions"]=null; render(); }
    else { $("#pe-backtest-result").innerHTML=`<div class="panel-caption" style="margin-top:10px">保存未完成：${esc((rep&&(rep.detail||rep.error))||"案例或框架有问题")}</div>`; } };
  const run=$("#pe-run"); if(run) run.onclick=async()=>{
    const data={};
    document.querySelectorAll("[data-pro-input]").forEach(i=>{
      const v=i.value.trim(); if(v==="") return;
      const numeric=i.type==="number"||/^-?\d+(\.\d+)?$/.test(v);
      data[i.dataset.proInput]=numeric?Number(v):v; });
    document.querySelectorAll("[data-pro-bool]").forEach(sel=>{ data[sel.dataset.proBool]=sel.value==="true"; });
    const mult={}; document.querySelectorAll("[data-pro-multi]").forEach(c=>{
      const k=c.dataset.proMulti; if(!mult[k])mult[k]=[]; if(c.checked)mult[k].push(c.value); });
    Object.keys(mult).forEach(k=>{ if(mult[k].length)data[k]=mult[k]; });
    const tier=(def&&def.boundaries&&def.boundaries.default_tier)||"audit";
    const out=await api(`/v1/scenario-slices/${encodeURIComponent(proEvalDefId)}/evaluate`,{method:"POST",body:JSON.stringify({data,tier})});
    if(out&&out.decision){ proEvalResult=out;
      // Convention B: the judgment lists missing required inputs. Mark them on the form, not only in prose.
      const miss=(out.missing_inputs||[]).slice();
      document.querySelectorAll("[data-pro-input],[data-pro-bool],[data-pro-multi]").forEach(el=>{
        const name=el.dataset.proInput||el.dataset.proBool||el.dataset.proMulti||"";
        el.classList.toggle("pro-missing", miss.indexOf(name)>=0); });
      const note=miss.length?('<div class="panel-caption" style="color:#d9534f;margin-bottom:6px">' +
        esc("还缺这些必须提供的信息：" + miss.join("、") + " —— 补齐后再判定。") + "</div>") : "";
      $("#pe-result").innerHTML=note+proPackageHtml(out)+proPreviewNote(); }
    else { proEvalResult=null; $("#pe-result").innerHTML=`<section class="panel empty-state">判定未完成：${esc((out&&(out.detail||out.error))||"框架或输入有问题")}</section>`; } };
}

async function renderScenarioPreview(view){
 if(professionalMode){return renderProfessionalPreview(view)}
 const all=await load("scenario-slices");const rows=all.filter(x=>x.status==="confirmed"&&!isProSlice(x));
 if(!rows.length){view.innerHTML=`${proModeButtons()}${titleBlock("SAFE DRY RUN","场景预演",labels["scenario-preview"].subtitle)}<section class="panel empty-state"><div class="empty-icon">▷</div><strong>还没有可预演的场景实例</strong><p>先在“场景切片”分析并确认一个场景，然后回来填写模拟输入。</p><button class="button primary" id="go-to-scenes">打开场景切片</button></section>`;$("#go-to-scenes").onclick=()=>navigate("scenario-slices");return}
 const selectedId=new URLSearchParams(location.search).get("scenario")||rows[0].id;const selected=rows.find(x=>x.id===selectedId)||rows[0];const a=selected.analysis||{};const scope=a.scope||{mode:"global"};const segmentation=a.segmentation||{mode:"global",dimensions:[],global_preferences:[],variants:[]};if(segmentation.mode==="segmented"){scope.mode="by_dimension";scope.dimension=(segmentation.dimensions||[]).map(d=>d.label||d.field).join(" + ");scope.value="按请求匹配分组"}
 const dimensions=segmentation.mode==="segmented"?(segmentation.dimensions||[]):[];let required=Array.isArray(a.required_inputs)?[...a.required_inputs]:[];for(const d of dimensions)if(!required.some(x=>x.name===d.field))required.push({name:d.field,label:d.label||d.field,type:d.type||"string",required:true});let prefs=Array.isArray(a.instance_preferences)?a.instance_preferences:[];
 if(segmentation.mode==="segmented")prefs=[...(segmentation.global_preferences||[]),...(segmentation.variants||[]).flatMap(v=>v.preferences||[])];
 if(!prefs.length){const excluded=new Set([scope.dimension||"destination_city","destination_city","district","area"]);prefs=(a.facts||[]).filter(x=>x&&x.source!=="suggestion"&&(scope.mode==="by_dimension"||!excluded.has(x.name))).map(x=>({field:x.name,label:x.label||x.name,value:x.value,strength:"must"}))}
 const groups=new Map();for(const p of prefs){const field=String(p.field||p.name||"");if(!field)continue;const key=["min_price","max_price","price_min","price_max","budget_min","budget_max"].includes(field)?"price":field;if(!groups.has(key))groups.set(key,{key,label:key==="price"?"模拟酒店价格":p.label||field,rules:[]});groups.get(key).rules.push({...p,field})}
 const typeOf=x=>x.type==="boolean"?"bool":x.type||"string";const inputHtml=(item,group)=>{const key=item.name||item.key;const label=item.label||item.name||item.key;const type=group?((group.rules.some(r=>["lte","gte"].includes(r.operator)||typeof r.value==="number")?"number":group.rules.some(r=>typeof r.value==="boolean")?"bool":"string")):typeOf(item);let control=type==="bool"?`<select class="select" data-preview-input="${esc(key)}"><option value="">请选择</option><option value="true">是</option><option value="false">否</option></select>`:`<input class="input" data-preview-input="${esc(key)}" type="${type==="date"?"date":type==="number"?"number":"text"}" ${type==="number"?"step=any":""} placeholder="${esc(type==="date"?"选择日期":type==="number"?"输入数字":"请输入模拟值")}">`;return `<label class="field"><span class="field-label">${esc(label)}${item.required?" · 必填":""}</span>${control}${group?`<small class="panel-caption">${group.rules.map(r=>`${esc(r.label||r.field)} ${esc(({equals:"=",lte:"≤",gte:"≥",exists:"需提供"})[r.operator]||"=")} ${esc(r.value??"")}`).join("；")}</small>`:""}</label>`};
 const statusText={pass:"符合",fail:"不符合",missing:"待输入",invalid:"值无法比较",incomplete:"信息不完整",not_applicable:"此实例不适用",needs_data:"还需更多信息"};
 view.innerHTML=`${proModeButtons()}${titleBlock("SAFE DRY RUN","场景预演","使用模拟请求和模拟对象检查实例。整个过程只读取已保存实例，不执行预订、不联系服务商，也不会写入判定记录。")}
 <section class="panel" style="padding:18px;margin-bottom:14px"><div class="panel-title">选择已确认的场景实例</div><div class="form-grid" style="margin-top:10px"><label class="field"><span class="field-label">场景实例</span><select class="select" id="preview-scene">${rows.map(x=>`<option value="${esc(x.id)}" ${x.id===selected.id?"selected":""}>${esc(x.analysis?.title||x.original_text?.slice(0,80)||x.id)}</option>`).join("")}</select></label><div class="field"><span class="field-label">适用范围</span><div class="panel-caption" style="padding:10px 0">${scope.mode==="by_dimension"?`按 ${esc(scope.label||scope.dimension||"上下文维度")} = ${esc(scope.value||"未设置")} 区分`:"所有情况共用同一套偏好"}</div></div></div></section>
 <form id="preview-form"><div class="dashboard-grid"><section class="panel" style="padding:18px"><div class="panel-title">模拟一次用户请求</div><p class="panel-caption">填写这个场景每次执行前必须取得的信息。</p><div class="form-grid" style="margin-top:12px">${required.length?required.map(x=>inputHtml(x,null)).join(""):`<div class="panel-caption">该实例尚未定义运行时必填项。</div>`}</div></section><section class="panel" style="padding:18px"><div class="panel-title">模拟一个候选对象</div><p class="panel-caption">填写酒店或对象实际提供的数据，查看它是否满足实例偏好。留空会显示“待输入”。</p><div class="form-grid" style="margin-top:12px">${groups.size?[...groups.values()].map(g=>inputHtml({key:g.key,label:g.label},g)).join(""):`<div class="panel-caption">该实例还没有偏好条件。</div>`}</div></section></div><div id="preview-error" class="form-error"></div><div style="display:flex;gap:8px;justify-content:flex-end;margin:12px 0 16px"><button type="button" class="button" id="preview-sample">填入符合条件的模拟数据</button><button type="submit" class="button primary" id="preview-run">运行预演 →</button></div></form><div id="preview-result"></div>`;
 $("#preview-scene").onchange=e=>{const q=`?scenario=${encodeURIComponent(e.target.value)}`;try{history.replaceState(null,"",q)}catch(_){/* 仅更新地址栏，绝不重载页面 */}render()};
 $("#preview-sample").onclick=()=>{for(const item of required){const el=$(`[data-preview-input="${CSS.escape(item.name)}"]`);if(!el)continue;const samples={destination_city:scope.mode==="by_dimension"?scope.value:"武汉",check_in_date:"2026-10-15",check_out_date:"2026-10-18",guest_count:"2"};el.value=samples[item.name]|| (typeOf(item)==="number"?"1":typeOf(item)==="bool"?"true":"示例值")}for(const group of groups.values()){let sample;const exact=group.rules.find(r=>r.operator==="equals");if(exact)sample=exact.value;else{const lows=group.rules.filter(r=>r.operator==="gte").map(r=>Number(r.value)).filter(Number.isFinite);const highs=group.rules.filter(r=>r.operator==="lte").map(r=>Number(r.value)).filter(Number.isFinite);sample=lows.length&&highs.length?(Math.max(...lows)+Math.min(...highs))/2:lows[0]??highs[0]??group.rules[0]?.value}const el=$(`[data-preview-input="${CSS.escape(group.key)}"]`);if(el&&sample!==undefined&&sample!==null)el.value=String(sample)}toast("已填入本地模拟值，可修改后运行")};
 $("#preview-form").onsubmit=async e=>{e.preventDefault();const button=$("#preview-run");button.disabled=true;button.textContent="正在预演…";$("#preview-error").textContent="";$("#preview-result").innerHTML="";const request_inputs={},candidate={};$$('[data-preview-input]',e.currentTarget).forEach(el=>{if(el.value==="")return;const raw=el.value;const item=[...required,...[...groups.values()].map(g=>({name:g.key,type:g.rules.some(r=>["lte","gte"].includes(r.operator)||typeof r.value==="number")?"number":"string"}))].find(x=>x.name===el.dataset.previewInput);let value=raw;if(item?.type==="number")value=Number(raw);else if(item?.type==="boolean"||item?.type==="bool")value=raw==="true";if(required.some(x=>x.name===el.dataset.previewInput))request_inputs[el.dataset.previewInput]=value;else candidate[el.dataset.previewInput]=value});try{const result=await api(`/v1/scenario-slices/${encodeURIComponent(selected.id)}/preview`,{method:"POST",body:JSON.stringify({request_inputs,candidate})});const badgeType=result.status==="pass"?"allow":result.status==="fail"?"deny":"ask";$("#preview-result").innerHTML=`<section class="panel" style="padding:18px;margin-bottom:20px"><div class="panel-title">预演结果 <span class="badge ${badgeType}">${esc(statusText[result.status]||result.status)}</span></div><p class="panel-caption" style="margin-top:8px">${esc(result.message)} · 必填缺失 ${result.missing_required.length} 项 · 约束符合 ${result.summary.pass} 项 · 不符合 ${result.summary.fail} 项 · 待输入 ${result.summary.missing} 项</p>${result.missing_required.length?`<div class="decision-detail"><strong>尚缺少的必填信息</strong><div class="panel-caption">${result.missing_required.map(x=>esc(x.label)).join("、")}</div></div>`:""}<div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>检查项</th><th>条件</th><th>模拟值</th><th>结果</th></tr></thead><tbody>${result.scope.mode==="by_dimension"?`<tr><td>实例适用范围：${esc(result.scope.dimension)}</td><td>${esc(result.scope.expected||"")}</td><td>${esc(result.scope.actual??"—")}</td><td>${esc(statusText[result.scope.status]||result.scope.status)}</td></tr>`:""}${result.checks.map(x=>`<tr><td>${esc(x.label)}</td><td>${esc(({equals:"等于",lte:"不高于",gte:"不低于",exists:"必须提供"})[x.operator]||x.operator)} ${esc(x.expected??"")}</td><td>${esc(x.actual??"—")}</td><td>${esc(statusText[x.status]||x.status)}</td></tr>`).join("")||`<tr><td colspan="4">没有可检查的偏好条件</td></tr>`}</tbody></table></div></section>`}catch(error){$("#preview-error").textContent=error.message}finally{button.disabled=false;button.textContent="运行预演 →"}};
}
function scenarioAnalysisHtml(a){const section=(title,items,renderItem)=>`<section class="panel" style="padding:17px;margin-bottom:12px"><div class="panel-title">${title}</div>${items?.length?`<div style="display:grid;gap:8px;margin-top:10px">${items.map(renderItem).join("")}</div>`:`<div class="panel-caption" style="margin-top:9px">暂未识别到内容</div>`}</section>`;
 const hotel=/酒店|旅馆|宾馆/.test(`${a.title||""} ${a.intent||""} ${JSON.stringify(a.resource_types||[])}`);const requiredInputs=Array.isArray(a.required_inputs)&&a.required_inputs.length?a.required_inputs:(hotel?[{name:"destination_city",label:"目的城市",type:"string",required:true},{name:"check_in_date",label:"入住日期",type:"date",required:true},{name:"check_out_date",label:"退房日期",type:"date",required:true},{name:"guest_count",label:"入住人数",type:"number",required:true}]:[]);
 const needsSupplement=Array.isArray(a.questions)&&a.questions.length>0&&!a.supplement_completed;const canCreate=Array.isArray(a.resource_types)&&a.resource_types.length>0&&Array.isArray(a.actions)&&a.actions.length>0;
 const empty=[a.facts,a.resource_types,a.actions,a.policies,a.questions].every(items=>!Array.isArray(items)||items.length===0);
 return `${empty?`<section class="panel" style="padding:14px;margin:16px 0;color:#8b611f;background:#fffaf0"><strong>这个草稿保存的是空分析结果</strong><div class="panel-caption" style="margin-top:5px">解析已修复。请在上方重新勾选数据处理确认，再点“根据补充信息重新分析”更新此草稿。</div></section>`:""}<div class="dashboard-grid" style="margin:16px 0"><section class="panel" style="padding:17px"><div class="eyebrow">ANALYSIS</div><label class="field" style="margin-top:9px"><span class="field-label">本体模型建议的场景名称（可修改）</span><input class="input" id="scenario-title" maxlength="160" value="${esc(a.title||"")}" placeholder="例如：预订机票"></label><p class="page-subtitle">${esc(a.intent||"")}</p><small class="panel-caption">名称应概括可复用的任务，不包含本次城市、日期等临时信息。</small></section><section class="panel" style="padding:17px"><div class="panel-title">场景事实与偏好</div><div style="display:grid;gap:7px;margin-top:10px">${(a.facts||[]).map(x=>`<div><strong>${esc(x.label||x.name||"信息")}</strong>：${esc(x.value??"待补充")} <span class="muted">${esc(x.source==="suggestion"?"· 模型建议":"· 来自你的描述")}</span></div>`).join("")||"尚未识别"}</div></section></div>
 ${scenarioSegmentationEditor(a,"slice")}
 ${section("智能体每次执行前必须收集",requiredInputs,x=>`<div><strong>${esc(x.label||x.name||"必填信息")}${x.required?` <span class="badge ask">必填</span>`:""}</strong><div class="panel-caption">字段 ${esc(x.name||"")} · ${esc(({string:"文本",number:"数字",bool:"是/否",boolean:"是/否",date:"日期"})[x.type]||x.type||"文本")}${x.help?` · ${esc(x.help)}`:""}</div></div>`)}
 ${section("资源类型建议",a.resource_types,x=>`<div><strong>${esc(x.name||"资源")}</strong><div class="panel-caption">${esc(x.description||"")}${Array.isArray(x.attributes)&&x.attributes.length?` · 关注信息：${esc(x.attributes.join("、"))}`:""}</div></div>`)}
 ${section("动作建议",a.actions,x=>`<div><strong>${esc(x.name||"动作")}</strong><div class="panel-caption">${esc(x.description||"")} · 风险：${esc(x.risk||"待确认")}</div></div>`)}
 ${section("授权规则草稿",a.policies,x=>`<div><strong>${esc(x.subject||"主体待选择")} · ${esc(x.effect||"ask")==="allow"?"拟允许":esc(x.effect||"ask")==="deny"?"拟拒绝":"需要确认"}</strong><div class="panel-caption">${esc(x.resource||"")} · ${(Array.isArray(x.actions)?x.actions:[]).map(esc).join("、")} ${Array.isArray(x.conditions)&&x.conditions.length?` · 条件：${esc(x.conditions.map(c=>typeof c==="string"?c:`${c.label||c.field||"条件"} ${({equals:"等于",lte:"不高于",gte:"不低于",exists:"需提供"})[c.operator]||c.operator||""} ${c.value??""}`).join("；"))}`:""}</div><span class="badge pending">仅草稿，尚未生效</span></div>`)}
 ${section("需要你补充或确认",a.questions,x=>`<label style="display:grid;gap:5px"><strong>${esc(x.question||"请补充")}</strong><small class="panel-caption">${esc(x.reason||"")}${x.importance?` · ${esc(x.importance)}`:""}</small><input class="input scenario-answer" data-question="${esc(x.question||"")}" placeholder="可填写回答；留空表示暂不补充"></label>`)}
 ${needsSupplement?`<section class="panel" style="padding:17px;margin:12px 0 18px"><div class="panel-title">下一步：提交补充信息</div><p class="panel-caption">可回答上面的建议，也可以留空跳过。提交后系统会更新分析；本轮之后不再追加可选确认。</p><div id="scene-confirm-error" class="form-error"></div><div style="display:flex;justify-content:flex-end;margin-top:12px"><button class="button primary" id="reanalyze">提交补充并重新分析</button></div></section>`:a.generated?`<section class="panel" style="padding:17px;margin:12px 0 18px"><div class="panel-title">场景实例已创建</div><p class="panel-caption">资源、动作、规则和运行时字段已保存，可在“场景实例”菜单统一维护。</p><button class="button" data-goto="scenario-instances">打开场景实例</button></section>`:canCreate?`<section class="panel" style="padding:17px;margin:12px 0 18px"><div class="panel-title">分析已就绪，可以创建场景实例</div><p class="panel-caption">必要的资源类型和动作已识别。运行时必填信息由系统生成默认定义；你可以之后在场景实例中调整。授权记录仍为草稿。</p><div class="form-grid" style="margin-top:11px"><div class="field"><label class="field-label">规则由谁设置（可选）</label><select id="scene-grantor" class="select">${entityOptions("principals","")}</select></div><div class="field"><label class="field-label">规则适用于谁（可选）</label><select id="scene-grantee" class="select">${entityOptions("principals","")}</select></div></div><div id="scene-confirm-error" class="form-error"></div><div style="display:flex;justify-content:flex-end;margin-top:12px"><button class="button primary" id="confirm-scenario">确认并创建场景实例</button></div></section>`:`<section class="panel" style="padding:17px;margin:12px 0 18px"><div class="panel-title">还需要完善场景描述</div><p class="panel-caption">系统尚未识别完整的资源类型和动作。请在上方描述中补充“要处理什么对象”以及“要执行什么操作”，再重新分析。</p><div id="scene-confirm-error" class="form-error"></div><div style="display:flex;justify-content:flex-end;margin-top:12px"><button class="button" id="reanalyze">重新分析</button></div></section>`}`}
async function confirmScenario(){const button=$("#confirm-scenario");const segmentation=readScenarioSegmentation("slice",activeScenario.analysis?.segmentation||{});if(!segmentation)return;
 if(segmentation.mode==="global"&&!segmentation.global_preferences.length&&$$("#slice-seg-rows .seg-pref-row").length){
   if(!confirm("你还没有勾选任何「长期」偏好。\n\n继续确认的话，这些值不会保存为场景偏好，场景实例里也不会出现它们。\n\n仍要继续？"))return;
 }button.disabled=true;button.textContent="正在保存…";try{const title=$("#scenario-title")?.value.trim(),priorTitle=activeScenario.analysis?.title;const titleBody=title&&(title!==priorTitle||activeScenario.analysis?.title_user_modified)?{title}:{};const result=await api("/v1/scenario-slices/confirm",{method:"POST",body:JSON.stringify({scenario_id:activeScenario.id,...titleBody,segmentation,grantor_id:$("#scene-grantor").value||null,grantee_id:$("#scene-grantee").value||null})});activeScenario=result.scenario;activeInstanceId=result.scenario.id;for(const key of ["resource-types","actions","authorizations","constraints","params"])delete cache[key];
 const notes=result.compile_report||[];
 toast(notes.length?`场景实例已写入本体；有 ${notes.length} 条策略的个别条件无法编译，已忽略（${notes.map(n=>`策略${n.policy}`).join("、")}）`:"场景实例已写入本体");
 navigate("scenario-instances")}catch(error){$("#scene-confirm-error").textContent=error.message;button.disabled=false;button.textContent="确认并创建场景实例"}}
async function submitScenario(e){e.preventDefault();const button=$("#scenario-submit");if(!$("#scenario-consent").checked){$("#scenario-error").textContent="请先确认模型服务的数据处理说明。";return}button.disabled=true;button.textContent="正在分析…";$("#scenario-error").textContent="";try{const answers=$$(".scenario-answer").map(x=>({question:x.dataset.question,answer:x.value.trim()})).filter(x=>x.answer);const title=$("#scenario-title")?.value.trim();const oldTitle=activeScenario?.analysis?.title;const body={text:$("#scenario-text").value.trim(),...(activeScenario?{scenario_id:activeScenario.id,answers}:{}),...(title&&title!==oldTitle?{title_override:title}:{})};const result=await api("/v1/scenario-slices/analyze",{method:"POST",body:JSON.stringify(body)});activeScenario=result.scenario;delete cache["scenario-slices"];toast("场景分析草稿已保存");render()}catch(error){$("#scenario-error").textContent=error.message}finally{button.disabled=false;button.textContent=activeScenario?"根据补充信息重新分析 →":"分析场景 →"}}
async function renderDashboard(view){
 // 总览回答两个问题：我的场景现在能不能用？有什么需要我处理？
 // 本体对象（资源类型/动作/授权）由场景自动生成，只在末尾作为一行说明，不再占卡片位。
 let scenes=[],rules=[],decisions=[],principals=[],resourceTypes=[],actions=[],provider={configured:true},offline=false;
 try{
  [scenes,rules,decisions,principals,resourceTypes,actions]=await Promise.all([load("scenario-slices").then(r=>r.filter(x=>!isProSlice(x))),load("authorizations"),load("decisions"),load("principals"),load("resource-types"),load("actions")]);
  try{provider=await api("/v1/scenario-slices/provider")}catch{provider={configured:true}}
 }catch(error){offline=true}
 const published=scenes.filter(s=>s.status==="confirmed");
 const drafts=scenes.filter(s=>s.status!=="confirmed");
 const rulesOf=id=>rules.filter(r=>String(r.source||"")==="scenario-slice:"+id);
 const activeRules=rules.filter(r=>r.policy_status==="active");
 const pendingRules=rules.filter(r=>r.policy_status!=="active");
 const latest=[...decisions].sort((a,b)=>String(b.timestamp||"").localeCompare(String(a.timestamp||""))).slice(0,5);
 [["principals",principals.length],["scenario-slices",scenes.length],["scenario-instances",published.length],["decisions",decisions.length]].forEach(([key,value])=>{const el=document.querySelector(`[data-count="${key}"]`);if(el)el.textContent=value});
 const todos=[];
 if(offline)todos.push({badge:["deny","服务离线"],title:"治理后端没有响应",note:"场景与判定数据暂时读不到。",page:"service-monitor",label:"查看服务监控 →"});
 else if(!provider.configured)todos.push({badge:["pending","模型服务未配置"],title:"还没有配置场景分析模型",note:"没有模型就无法把一句话拆解成场景与规则。",page:"model-service",label:"去配置 →"});
 drafts.forEach(s=>todos.push({badge:["pending","草稿场景"],title:s.analysis?.title||s.original_text?.slice(0,40)||s.id,note:"尚未确认发布，智能体在 MCP 目录里看不到它。",page:"scenario-slices",label:"去确认 →"}));
 published.forEach(s=>{const inactive=rulesOf(s.id).filter(r=>r.policy_status!=="active");if(inactive.length)todos.push({badge:["pending","规则未启用"],title:s.analysis?.title||s.id,note:`${inactive.length} 条规则仍是草稿，判定不会放行。`,review:s.id,label:"审核并启用 →"})});
 try{const agents=await api("/v1/agents");if((agents.pending||[]).length)todos.push({badge:["pending","智能体待授权"],title:`${agents.pending.length} 个本机程序请求读取本体`,note:"在你批准前它们读不到任何内容。",page:"agent-access",label:"去处理 →"})}catch(error){}
 const pendingRoles=scenes.filter(x=>String(x.status||"")!=="confirmed"&&[...((x.analysis||{}).required_inputs||[]),...((x.analysis||{}).facts||[])].some(y=>y&&(y.role||y.role_reason)));
 if(pendingRoles.length)todos.push({badge:["pending","分档待核对"],title:`${pendingRoles.length} 个场景的字段分档建议待你核对`,note:"模型判断了哪些字段是每次必填、哪些是长期偏好；确认该场景即视为已核对。",page:"scenario-slices",label:"去处理 →"});
 const sceneIds=new Set(scenes.map(s=>s.id));
 const orphans=rules.filter(r=>{const src=String(r.source||"");return src.startsWith("scenario-slice:")&&!sceneIds.has(src.slice("scenario-slice:".length))});
 if(orphans.length)todos.push({badge:["deny","孤立规则"],title:`${orphans.length} 条规则所属的场景已被删除`,note:"它们不再受任何场景管理，也不会参与判定。",cleanup:orphans.map(r=>r.id).join(","),label:"清理"});
 const sceneRow=s=>{const mine=rulesOf(s.id);const active=mine.filter(r=>r.policy_status==="active").length;const confirmed=s.status==="confirmed";const status=!confirmed?`<span class="badge neutral">草稿</span>`:active?`<span class="badge active">${active} 条生效中</span>`:`<span class="badge pending">${mine.length} 条未生效</span>`;return `<div class="decision-detail" style="margin:0;padding:13px 15px;display:flex;align-items:center;gap:11px"><div style="flex:1;min-width:0"><strong>${esc(s.analysis?.title||s.original_text?.slice(0,40)||s.id)}</strong><div class="panel-caption">${confirmed?`已发布 · 智能体可读取 · ${mine.length?`规则 ${mine.length} 条`:"无规则"}`:"未发布 · 智能体看不到"} · 更新于 ${esc(formatTime(s.updated_at))}</div></div>${status}<button class="button" data-open-scene="${esc(s.id)}">管理 →</button></div>`};
 const statCard=(label,value,foot,icon)=>`<article class="stat-card"><div class="stat-top"><span>${label}</span><span class="stat-icon">${icon}</span></div><div class="stat-num">${value}</div><div class="stat-foot">${foot}</div></article>`;
 view.innerHTML=`${titleBlock("CONTROL CENTER · LOCAL","个人可信数据空间总览","管理你的场景实例、确认哪些规则已经生效，并在执行前检查授权结果。")}
 <div class="stats-grid">
  ${statCard("已发布场景",published.length,"智能体可通过 MCP 目录读取","◎")}
  ${statCard("生效中的规则",`${activeRules.length}/${rules.length}`,"只有生效的规则参与判定","▤")}
  ${statCard("待启用规则",pendingRules.length,"仍是草稿，判定不会放行","◷")}
  ${statCard("判定记录",decisions.length,latest.length?`最近 ${esc(formatTime(latest[0].timestamp))}`:"还没有判定记录","⌁")}
 </div>
 <div class="panel-caption" style="margin:-6px 0 17px">由场景自动生成：${principals.length} 个主体 · ${resourceTypes.length} 个资源类型 · ${actions.length} 个动作。这些不需要单独维护，随场景实例一起更新。</div>
 ${todos.length?`<section class="panel" style="margin-bottom:16px"><div class="panel-header"><div><div class="panel-title">需要你处理 · ${todos.length}</div><div class="panel-caption">下面这些还没真正生效</div></div></div><div style="display:grid;gap:9px;padding:15px 17px">${todos.map(t=>`<div class="decision-detail" style="margin:0;padding:13px 15px;display:flex;align-items:center;gap:11px"><span class="badge ${t.badge[0]}">${esc(t.badge[1])}</span><div style="flex:1;min-width:0"><strong>${esc(t.title)}</strong><div class="panel-caption">${esc(t.note)}</div></div><button class="button ${t.review||t.cleanup?"primary":""}" ${t.review?`data-todo-review="${esc(t.review)}"`:(t.cleanup?`data-todo-cleanup="${esc(t.cleanup)}"`:`data-todo-goto="${esc(t.page)}"`)}>${esc(t.label)}</button></div>`).join("")}</div></section>`:""}
 <div class="dashboard-grid" style="align-items:start">
  <section class="panel"><div class="panel-header"><div><div class="panel-title">我的场景</div><div class="panel-caption">已发布 ${published.length} · 草稿 ${drafts.length}</div></div><button class="text-link" data-goto="scenario-slices">新建场景 →</button></div><div style="display:grid;gap:9px;padding:15px 17px">${scenes.length?scenes.map(sceneRow).join(""):`<div class="empty-state"><div class="empty-icon">◇</div>还没有场景。用一句话描述你想让智能体替你做的事，系统会拆解成可确认的场景与规则。<div style="margin-top:14px"><button class="button primary" data-goto="scenario-slices">创建第一个场景 →</button></div></div>`}</div></section>
  <section class="panel quick-check"><div class="panel-title">快速判定</div><div class="panel-caption">检查某个主体能否对指定资源执行动作</div><form id="check-form" class="form-grid">${fieldHtml(f("principal_id","谁要执行？","entity",true,"principals","例如选择“林素”或某个助手。"))}${fieldHtml(f("action_id","要做什么？","entity",true,"actions","例如查看文件。"))}${fieldHtml(f("resource_type_id","哪类资源？","entity",true,"resource-types","例如文件或应用。"))}${fieldHtml(f("resource_id","具体资源","text",true,"例如：/文档/计划.md","填写资源的名称或位置。"))}<div class="field full"><label class="field-label" for="check-trust">来源可信度</label><select class="select" id="check-trust"><option value="high">高</option><option value="medium">中</option><option value="low">低</option></select></div><button class="button primary check-submit" style="grid-column:1/-1" type="submit">检查授权 <span>→</span></button></form>${activeRules.length?"":`<p class="form-hint">当前没有生效中的规则，判定结果会是默认拒绝。</p>`}<div id="check-output"></div></section>
 </div>
 <section class="panel" style="margin-top:16px"><div class="panel-header"><div><div class="panel-title">最近判定</div><div class="panel-caption">授权引擎写入的决策记录，每次判定都会留档</div></div><button class="text-link" data-goto="decisions">全部记录 →</button></div>${latest.length?`<div class="table-wrap"><table><thead><tr><th>结果</th><th>判定阶段</th><th>原因</th><th>时间</th></tr></thead><tbody>${latest.map(d=>`<tr><td>${badge(d.result_id)}</td><td>${esc(d.phase||"—")}</td><td class="mono">${esc(d.reason_key||"—")}</td><td class="muted">${esc(formatTime(d.timestamp))}</td></tr>`).join("")}</tbody></table></div>`:`<div class="empty-state"><div class="empty-icon">◷</div>还没有判定记录。先启用规则，再用上面的快速判定检查一次。</div>`}</section>`;
 $$('[data-goto]',view).forEach(b=>b.onclick=()=>navigate(b.dataset.goto));
 $$('[data-todo-goto]',view).forEach(b=>b.onclick=()=>navigate(b.dataset.todoGoto));
 $$('[data-todo-review]',view).forEach(b=>b.onclick=()=>openPolicyReview(b.dataset.todoReview));
 $$('[data-todo-cleanup]',view).forEach(b=>b.onclick=async()=>{
   const ids=String(b.dataset.todoCleanup||"").split(",").filter(Boolean);
   if(!ids.length)return;
   if(!confirm(`将删除 ${ids.length} 条所属场景已不存在的规则。此操作不可撤销，继续？`))return;
   let removed=0;
   for(const id of ids){try{await api(`/v1/authorizations/${encodeURIComponent(id)}`,{method:"DELETE"});removed++}catch(error){toast(`${id}: ${error.message}`,true)}}
   delete cache.authorizations;toast(`已清理 ${removed} 条孤立规则`);render();
 });
 $$('[data-open-scene]',view).forEach(b=>b.onclick=()=>{activeInstanceId=b.dataset.openScene;navigate("scenario-instances")});
 $("#check-form").onsubmit=runCheck;}
function formatTime(value){if(!value)return"—";const d=new Date(value);return Number.isNaN(d.getTime())?value:d.toLocaleString("zh-CN",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"})}
async function renderCollection(view,collection){const meta=labels[collection];if(!meta){view.innerHTML="<div class='panel empty-state'>该模块尚未开放</div>";return}const rows=await load(collection);document.querySelector(`[data-count="${collection}"]`)?.replaceChildren(document.createTextNode(rows.length));const action=meta.readonly?"":`<button class="button primary" id="new-record"><span class="plus">＋</span> 新建${meta.singular}</button>`;view.innerHTML=`${titleBlock("ONTOLOGY REGISTRY",meta.title,meta.subtitle,action)}<div class="collection-toolbar"><label class="search-box"><input class="input" id="search" placeholder="搜索${meta.title}…" aria-label="搜索${meta.title}"></label><span class="record-count" id="record-count">${rows.length} 条记录</span><span class="toolbar-spacer"></span><button class="button" id="reload-list">↻ 刷新</button></div><section class="panel collection-panel"><div class="table-wrap"><table><thead><tr>${meta.cols.map(c=>`<th>${c[1]}</th>`).join("")}${meta.readonly?"":"<th style='text-align:right'>操作</th>"}</tr></thead><tbody id="table-body"></tbody></table></div><div class="empty-state" id="list-empty" hidden><div class="empty-icon">◇</div>没有匹配的记录</div></section>`;
 const draw=(query="")=>{const visible=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(query.toLowerCase()));$("#record-count").textContent=`${visible.length} 条记录`;$("#table-body").innerHTML=visible.map(row=>`<tr class="data-row">${meta.cols.map(([key])=>`<td>${renderCell(key,row[key],collection,row)}</td>`).join("")}${meta.readonly?"":`<td><div class="row-actions"><button class="button small" data-edit="${esc(row.id)}">编辑</button><button class="button small danger" data-delete="${esc(row.id)}">删除</button></div></td>`}</tr>`).join("");$("#list-empty").hidden=visible.length>0;$$('[data-edit]').forEach(b=>b.onclick=()=>openRecord(collection,rows.find(x=>x.id===b.dataset.edit)));$$('[data-delete]').forEach(b=>b.onclick=()=>deleteRecord(collection,b.dataset.delete))};draw();$("#search").oninput=e=>draw(e.target.value);$("#reload-list").onclick=async()=>{delete cache[collection];await render()};$("#new-record")?.addEventListener("click",()=>openRecord(collection));}
function renderCell(key,value,collection,record){if(key==="display_name_zh")return esc(fieldLabel(record||{},"display_name_zh","display_name_en")||value);if(value===undefined||value===null||value==="")return`<span class="muted">—</span>`;if(key==="effect"||key==="result_id"||key==="risk_level"||key==="revoked")return badge(value);if(key==="policy_status")return badge(({draft:"草稿",active:"生效中",suspended:"已暂停"})[value]||value);if(key==="principal_type")return esc(({person:"个人",agent:"智能体",group:"群组",role:"角色",org:"组织",service:"服务"})[value]||value);const rel={parent_id:"principals",grantor_id:"principals",grantee_id:"principals",applies_to:"resource-types",resource_type_id:"resource-types"};if(rel[key]){const row=(cache[rel[key]]||[]).find(r=>r.id===value);return esc(row?displayName(rel[key],row):value)}if(key==="matcher_id")return esc(({glob:"通配符",exact:"完全匹配",prefix:"开头匹配"})[value]||value);if(Array.isArray(value)){const target=key==="constraints"?"constraints":collection==="authorizations"||collection==="resource-types"?"actions":null;return esc(value.map(v=>target?displayName(target,(cache[target]||[]).find(r=>r.id===v)||{id:v,display_name_zh:(cache[target]||[]).find(r=>r.id===v)?.constraint_type}):v).join("、"))}if(key.endsWith("_at")||key==="timestamp")return esc(formatTime(value));if(typeof value==="object")return`<span class="mono">${esc(JSON.stringify(value))}</span>`;return esc(value)}
function fieldHtml(field,value=""){
 const id=`field-${field.name}`;let control;
 if(field.type==="select")control=`<select class="select" id="${id}" name="${field.name}" ${field.required?"required":""}>${field.extra.map(x=>{const o=typeof x==="string"?{value:x,label:x}:x;return`<option value="${esc(o.value)}" ${String(value)===o.value?"selected":""}>${esc(o.label)}</option>`}).join("")}</select>`;
 else if(field.type==="entity"||field.type==="multi-entity")control=`<select class="select" id="${id}" name="${field.name}" ${field.type==="multi-entity"?"multiple size='4'":""} ${field.required?"required":""} data-entity="${field.extra}">${entityOptions(field.extra,value,field.type==="multi-entity")}</select>`;
 else if(field.type==="json")control=`<textarea class="textarea" id="${id}" name="${field.name}" rows="3" ${field.required?"required":""} placeholder="${esc(field.extra||"")}">${esc(typeof value==="object"?JSON.stringify(value,null,2):value||"")}</textarea>`;
 else control=`<input class="input" id="${id}" name="${field.name}" type="text" value="${esc(value)}" ${field.required?"required":""} placeholder="${esc(field.extra||"")}">`;
 return`<div class="field"><label class="field-label" for="${id}">${field.label}${field.required?" <span style='color:#b25b52'>*</span>":""}</label>${control}${field.help?`<small class="field-help">${esc(field.help)}</small>`:""}</div>`
}
function displayName(collection,row){return fieldLabel(row,"display_name_zh","display_name_en")||({person:"个人",agent:"智能体",group:"群组",role:"角色",org:"组织"}[row.principal_type])||row.id}
function entityOptions(collection,value,multiple=false){const selected=new Set(Array.isArray(value)?value:[value].filter(Boolean));return`<option value="">${multiple?"请选择一项或多项":"请选择"}</option>${(cache[collection]||[]).map(row=>`<option value="${esc(row.id)}" ${selected.has(row.id)?"selected":""}>${esc(displayName(collection,row))}</option>`).join("")}`}
async function openRecord(collection,record=null){
 const meta=labels[collection],dialog=$("#record-dialog"),isEdit=!!record;
 const entityCollections=[...new Set(meta.fields.filter(x=>x.type==="entity"||x.type==="multi-entity").map(x=>x.extra))];
 try{await Promise.all(entityCollections.map(load))}catch(error){toast(error.message,true);return}
 $("#dialog-content").innerHTML=`<div class="modal-kicker">${isEdit?"EDIT RECORD":"NEW RECORD"}</div><h2>${isEdit?"编辑":"新建"}${meta.singular}</h2><p class="modal-intro">${isEdit?"修改下方信息即可；":""}系统会自动创建内部标识。保存前会检查必填项和数据关系。</p><form class="modal-form" id="record-form"><div class="form-grid">${meta.fields.map(field=>fieldHtml(field,record?.[field.name]??(collection==="authorizations"&&field.name==="policy_status"?"active":""))).join("")}</div><div id="record-error" class="form-error"></div><div class="modal-actions"><button class="button" type="button" id="cancel-record">取消</button><button class="button primary" type="submit">保存</button></div></form>`;
 dialog.showModal();
 const refreshActions=()=>{const resource=$("#field-resource_type_id");const actions=$("#field-actions");if(collection!=="authorizations"||!resource||!actions)return;const selected=actions.selectedOptions? [...actions.selectedOptions].map(x=>x.value):[];actions.innerHTML=entityOptions("actions",selected,true);[...actions.options].forEach(o=>{if(!o.value){o.hidden=true;return}const action=(cache.actions||[]).find(x=>x.id===o.value);o.hidden=!!(action?.applies_to&&action.applies_to!==resource.value)});};
 $("#field-resource_type_id")?.addEventListener("change",refreshActions);refreshActions();
 $("#cancel-record").onclick=()=>dialog.close();
 $("#record-form").onsubmit=async e=>{e.preventDefault();const data=new FormData(e.currentTarget),body={};
   for(const field of meta.fields){let raw;if(field.type==="multi-entity")raw=data.getAll(field.name).filter(Boolean);else raw=data.get(field.name);if((Array.isArray(raw)&&!raw.length)||raw===""||raw===null)continue;if(field.type==="json"){try{raw=JSON.parse(raw)}catch{$("#record-error").textContent=`${field.label} 必须是有效 JSON`;return}}body[field.name]=raw}
   try{const id=record?.id;const url=isEdit?`/v1/${collection}/${encodeURIComponent(id)}`:`/v1/${collection}`;await api(url,{method:isEdit?"PATCH":"POST",body:JSON.stringify(body)});cache={};dialog.close();toast(isEdit?"记录已更新":"记录已创建");render()}catch(error){$("#record-error").textContent=error.message}
 };
}
async function deleteRecord(collection,id){if(!confirm(`确定删除记录“${id}”？如果仍被其他数据引用，系统会阻止删除。`))return;try{await api(`/v1/${collection}/${encodeURIComponent(id)}`,{method:"DELETE"});delete cache[collection];toast("记录已删除");render()}catch(error){toast(error.message,true)}}
async function runCheck(e){e.preventDefault();const form=new FormData(e.currentTarget);const button=e.currentTarget.querySelector("button[type=submit]");button.disabled=true;button.textContent="正在判定…";try{const result=await api("/v1/decisions/evaluate",{method:"POST",body:JSON.stringify({principal_id:form.get("principal_id"),action_id:form.get("action_id"),resource_type_id:form.get("resource_type_id"),resource_id:form.get("resource_id"),context:{source_trust:$("#check-trust").value},phase:"pre_planning"})});const kind=result.result_id==="allow"?"allow":result.result_id==="deny"?"deny":"ask";$("#check-output").innerHTML=`<div class="decision-result ${kind}"><strong>${({allow:"✓ 允许执行",deny:"⊘ 拒绝执行",ask:"◷ 暂停并确认"})[kind]}</strong>${esc(result.reason_key)}<div class="decision-id">${esc(result.decision_id||"")}</div></div>`;delete cache.decisions;document.querySelector('[data-count="decisions"]')&&(document.querySelector('[data-count="decisions"]').textContent="·")}catch(error){$("#check-output").innerHTML=`<div class="decision-result deny">${esc(error.message)}</div>`}finally{button.disabled=false;button.innerHTML="检查授权 <span>→</span>"}}
$$('.nav-item').forEach(button=>button.addEventListener("click",()=>navigate(button.dataset.page)));
// 模式切换用事件委托：无论按钮由哪个渲染函数画出（日常页或专业页）都能响应。
document.addEventListener("click",event=>{const bd=event.target.closest?.("[data-bill-demo]");if(!bd)return;const dn=(document.querySelector("#bill-demo-tier")||{}).value||"basic";const list=(typeof cache!=="undefined"&&cache["scenario-definitions"])||[];const dd=list[0]||{};const dp=((dd.boundaries||{}).pricing)||{};const dt=(dp.tiers||{})[dn];const du=dp.mode==="monthly"?"元/月":"元/次";const dl={basic:"基础层",standard:"标准层",professional:"专业层",audit:"审计层"}[dn];const out=document.querySelector("#bill-demo-out");if(out)out.textContent=(dt==null)?"这个层级还没有定价（到场景切片页的「对外交付时附上的说明」里填）":("应收 "+dt+" "+du+" · 调用方：示例调用方（"+dl+"）");});
document.addEventListener("click",event=>{const b=event.target.closest?.("[data-pro-mode]");if(!b)return;professionalMode=b.dataset.proMode==="professional";try{localStorage.setItem("po.professionalMode",professionalMode?"1":"0")}catch(e){}render()});$("#refresh").onclick=reloadAll;$("#token-button").onclick=()=>navigate("account-security");refreshService();render();


// -- Delivery and feedback (a top-level menu page) --
async function renderDelivery(view){
  if(!professionalMode){
    view.innerHTML=`${proModeButtons()}${titleBlock("DELIVERY & FEEDBACK","对外交付与反馈","这一页属于专业判断侧：看你的判断对外交付的层级与定价，以及调用方的反馈统计。")}
     <section class="panel empty-state"><div class="empty-icon">◇</div>先在上方切到「专业技能场景」</section>`;
    return;
  }
  const [defs,slices]=await Promise.all([load("scenario-definitions"),load("scenario-slices")]);
  const mine=(slices||[]).filter(x=>(x.scenario_profile||{}).kind==="professional");
  const nameOf=s=>(s.analysis&&s.analysis.title)||s.original_text||s.id;
  const rows=mine.map(s=>{
    const b=s.boundaries||{}, pr=b.pricing||{}, tiers=pr.tiers||{};
    const ft=Number(s.feedback_total||0), fa=Number(s.feedback_accurate||0);
    const unit=pr.mode==="monthly"?" 元/月":" 元/次";
    const price=t=>tiers[t]==null?"未定价":(tiers[t]+unit);
    return `<tr><td>${esc(nameOf(s))}</td>
      <td>${esc((defs.find(d=>d.id===s.scenario_definition_id)||{}).display_name_zh||"—")}</td>
      <td>${esc(b.default_tier||"audit")}</td>
      <td>基础 ${esc(price("basic"))} · 标准 ${esc(price("standard"))} · 专业 ${esc(price("professional"))} · 审计 ${esc(price("audit"))}</td>
      <td>${ft?esc(String(ft)+" 次 · "+Math.round(fa/ft*100)+"%"):"—"}</td>
      <td>${esc(s.confidence_status||"unverified")}</td></tr>`;
  }).join("");
  view.innerHTML=`${proModeButtons()}
   ${titleBlock("DELIVERY & FEEDBACK","对外交付与反馈","你的判断对外交付的层级与定价，以及调用方的反馈统计。层级、定价、洞察与资历都在「场景切片」页的交付说明里设置。")}
   <section class="panel collection-panel">
    <div class="collection-toolbar"><span class="record-count"><span>我的切片</span> ${mine.length} <span>条</span></span><span class="toolbar-spacer"></span><button class="button" id="dl-reload">↻ 刷新</button></div>
    <div class="table-wrap"><table><thead><tr><th>我的切片</th><th>场景</th><th>默认层级</th><th>四层定价</th><th>调用方反馈</th><th>置信度</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="empty-state" ${mine.length?"hidden":""}><div class="empty-icon">◇</div>还没有专业切片。到「场景切片」页新建一条。</div>
   </section>
   <section class="panel" style="padding:16px;margin-bottom:16px">
    <div class="panel-title">计费演示</div>
    <div class="panel-caption" style="margin:6px 0 10px">演示数据，不写记录；价格与计费方式由你在「场景切片」页设定。</div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
     <select class="select" id="bill-demo-slice" style="max-width:280px">${mine.map(s=>`<option value="${esc(s.id)}">${esc(nameOf(s))}</option>`).join("")}</select>
     <select class="select" id="bill-demo-tier" style="max-width:220px">
      <option value="basic">基础层</option><option value="standard">标准层</option>
      <option value="professional">专业层</option><option value="audit">审计层</option></select>
     <button class="button" id="bill-demo-run">模拟一次调用</button>
     <span class="panel-caption" style="margin:0" id="bill-demo-out"></span>
    </div>
   </section>
   <section class="panel" style="padding:16px;margin-bottom:16px">
    <div class="panel-title">生成一次正式交付</div>
    <div class="panel-caption" style="margin:6px 0 10px">预演不写记录；正式交付会写一条判定记录，并附上审计号、有效期与内容指纹</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
     <select class="select" id="dl-slice" style="max-width:260px">${mine.map(s=>`<option value="${esc(s.id)}">${esc(nameOf(s))}</option>`).join("")}</select>
     <input class="input" id="dl-data" style="min-width:320px" placeholder='标的数据（字段名与你在场景切片里填的一致）'>
     <button class="button primary" id="dl-deliver">生成正式交付</button>
     <span class="panel-caption" style="margin:0" id="dl-out"></span>
    </div>
   </section>
   <section class="panel" style="padding:16px">
    <div class="panel-title">真实调用时会附上什么</div>
    <div class="panel-caption" style="margin-top:6px">审计号 · 有效期至 · 内容指纹 · 数字签名状态（预演不产生这些）；反馈由调用方通过接口提交，满 10 次升为「初步置信度」，满 100 次升为「稳定置信度」</div>
   </section>`;
  const rel=view.querySelector("#dl-reload"); if(rel) rel.onclick=()=>{cache["scenario-slices"]=null;render()};
  const dv=view.querySelector("#dl-deliver");
  if(dv) dv.onclick=async()=>{
    const sid=(view.querySelector("#dl-slice")||{}).value||"";
    const out=view.querySelector("#dl-out");
    let data; try{ data=JSON.parse((view.querySelector("#dl-data")||{}).value||"{}"); }
    catch(e){ if(out) out.textContent="标的数据不是合法 JSON："+e.message; return; }
    const r=await api("/v1/scenario-slices/"+encodeURIComponent(sid)+"/deliver",{method:"POST",body:JSON.stringify({data})});
    if(out) out.textContent=(r&&r.recorded)
      ?("已记录 · 结论 "+((r.decision)||"—")+" · 审计号 "+(r.audit_id||"—"))
      :("交付失败："+((r&&(r.detail||r.error))||"请检查数据与框架"));
    cache["decisions"]=null;
  };
  const run=view.querySelector("#bill-demo-run");
  if(run) run.onclick=()=>{
    const sid=(view.querySelector("#bill-demo-slice")||{}).value||"";
    const t=(view.querySelector("#bill-demo-tier")||{}).value||"basic";
    const s=mine.find(x=>x.id===sid)||{};
    const pr=(s.boundaries||{}).pricing||{}, amt=(pr.tiers||{})[t];
    const unit=pr.mode==="monthly"?" 元/月":" 元/次";
    const label={basic:"基础层",standard:"标准层",professional:"专业层",audit:"审计层"}[t];
    const out=view.querySelector("#bill-demo-out");
    if(out) out.textContent=(amt==null)
      ?(label+" 还没有定价（到场景切片页的交付说明里填）")
      :("应收 "+amt+unit+" · 调用方：示例调用方（"+label+"）");
  };
  view.querySelectorAll("[data-pro-mode]").forEach(b=>{b.onclick=()=>{professionalMode=b.dataset.proMode==="professional";try{localStorage.setItem("po.professionalMode",professionalMode?"1":"0")}catch(e){}render()}});
}

// -- Decision records (a top-level menu page): one row per formal delivery --
async function renderDecisions(view){
  if(!professionalMode){
    view.innerHTML=`${proModeButtons()}${titleBlock("DECISION RECORDS","判定记录","这一页属于专业判断侧：每条记录是一次正式交付（预演不写记录）")}
     <section class="panel empty-state"><div class="empty-icon">◇</div>先在上方切到「专业技能场景」</section>`;
    return;
  }
  const [slices,decs]=await Promise.all([load("scenario-slices"),load("decisions")]);
  const nameOf=id=>{const s=(slices||[]).find(x=>x.id===id);return (s&&((s.analysis&&s.analysis.title)||s.original_text))||id;};
  const rows=(decs||[]).filter(d=>(d.reason_key||"")==="skill_delivery")
    .sort((a,b)=>String(b.timestamp||"").localeCompare(String(a.timestamp||"")));
  const body=rows.map(d=>{
    const p=d.reason_params||{}, disp=d.reason_display||{}, inp=d.input_params||{};
    return `<tr>
      <td>${esc(d.timestamp||"")}</td>
      <td>${esc(nameOf(inp.slice_id))}</td>
      <td>${esc(disp.decision||"—")}</td>
      <td>${esc(disp.severity||"—")}</td>
      <td>${esc(inp.tier||"—")}</td>
      <td>${esc(p.audit_id||"—")}</td>
      <td>${esc(p.valid_until||"—")}</td>
      <td>${esc((p.content_fingerprint||"").slice(0,12)||"—")}</td>
      <td>${p.signature_status==="not_implemented"?'<span class="muted">尚未实现</span>':esc(String(p.signature_status||"—"))}</td>
    </tr>`;}).join("");
  view.innerHTML=`${proModeButtons()}
   ${titleBlock("DECISION RECORDS","判定记录","每条记录是一次正式交付：结论、交付层级，以及这次交付的审计号、有效期、内容指纹与签名状态。预演不写记录。")}
   <section class="panel collection-panel">
    <div class="collection-toolbar"><span class="record-count"><span>正式交付</span> ${rows.length} <span>条</span></span><span class="toolbar-spacer"></span><button class="button" id="dr-reload">↻ 刷新</button></div>
    <div class="table-wrap"><table><thead><tr><th>时间</th><th>我的切片</th><th>结论</th><th>严重度</th><th>交付层级</th><th>审计号</th><th>有效期至</th><th>内容指纹</th><th>数字签名</th></tr></thead><tbody>${body}</tbody></table></div>
    <div class="empty-state" ${rows.length?"hidden":""}><div class="empty-icon">◇</div>还没有正式交付。到「对外交付与反馈」页点「生成正式交付」。</div>
   </section>`;
  const rel=view.querySelector("#dr-reload"); if(rel) rel.onclick=()=>{cache["decisions"]=null;render()};
  view.querySelectorAll("[data-pro-mode]").forEach(b=>{b.onclick=()=>{professionalMode=b.dataset.proMode==="professional";try{localStorage.setItem("po.professionalMode",professionalMode?"1":"0")}catch(e){}render()}});
}

// -- Enabled professional slices: the form in which your judgment is available outside --
function proEnabledSlicesHtml(defs, slices) {
  const enabled = (slices || []).filter(x => x.status === "confirmed");
  if (!enabled.length) {
    return `<section class="panel" style="padding:16px;margin-bottom:14px">
     <div class="panel-caption" style="margin:0">还没有已启用的切片。到「场景切片」页把写好框架的切片点「确认并启用」，它就会出现在这里</div>
    </section>`;
  }
  const nameOf = x => (x.analysis && x.analysis.title) || x.original_text || x.id;
  const defName = id => ((defs || []).find(d => d.id === id) || {}).display_name_zh || "—";
  const summary = x => {
    const f = x.framework || {}, th = f.thresholds || {}, b = x.boundaries || {}, pr = b.pricing || {};
    return `输入 ${(f.inputs || []).length} · 信号 ${(f.signals || []).length} · 组合 ${(f.combination_rules || []).length} · 例外 ${(f.exception_rules || []).length} · 阈值 ${th.base == null ? "—" : th.base}`
      + `　|　默认层级 ${b.default_tier || "audit"} · 已定价 ${Object.keys(pr.tiers || {}).length} 项`;
  };
  const rows = enabled.map(x => `<tr>
    <td>${esc(nameOf(x))}</td>
    <td>${esc(defName(x.scenario_definition_id))}</td>
    <td>${esc(summary(x))}</td>
    <td>${esc(x.confidence_status || "unverified")}</td>
    <td style="text-align:right"><button class="button" data-edit-slice="${esc(x.id)}">编辑</button> <button class="button" data-unconfirm-slice="${esc(x.id)}">退回草稿</button></td>
  </tr>`).join("");
  return `<section class="panel collection-panel" style="margin-bottom:14px">
   <div class="collection-toolbar"><span class="record-count"><span>已启用的切片</span> ${enabled.length} <span>条</span></span>
    <span class="toolbar-spacer"></span><span class="panel-caption" style="margin:0">已启用 = 对外可用；退回草稿即暂停对外</span></div>
   <div class="table-wrap"><table><thead><tr><th>我的切片</th><th>场景</th><th>框架摘要</th><th>置信度</th><th style="text-align:right">操作</th></tr></thead>
   <tbody>${rows}</tbody></table></div></section>`;
}
document.addEventListener("click", event => {
  const e2 = event.target.closest?.("[data-edit-slice]");
  if (e2) {
    try { sessionStorage.setItem("poProPickSlice", e2.dataset.editSlice); } catch (err) {}
    const nav = document.querySelector('[data-page="scenario-slices"]');
    if (nav) nav.click();
    return;
  }
  const b = event.target.closest?.("[data-unconfirm-slice]");
  if (!b) return;
  api("/v1/scenario-slices/" + encodeURIComponent(b.dataset.unconfirmSlice),
    { method: "PATCH", body: JSON.stringify({ status: "analyzed" }) })
    .then(() => { cache["scenario-slices"] = null; render(); })
    .catch(err => alert("退回草稿失败：" + (err && err.message ? err.message : err)));
});


// ===== 个人资料：页面内直接输入（不用弹窗），字段可增删改；列表默认掩码 =====
function maskValue(v){
  const t=String(v==null?"":v);
  if(!t) return "";
  if(t.length<=2) return t.slice(0,1)+"*";                 // 短值也留一个字符，否则看不出有数据
  if(t.length<=4) return t.slice(0,1)+"*".repeat(t.length-1);
  return t.slice(0,2)+"*".repeat(Math.max(4,t.length-4))+t.slice(-2);
}
let profileEdit=null;   // null=不在编辑；{id?,name,items:[{key,label,value,kind}]}=正在编辑
function profileFormHtml(){
  const e=profileEdit;
  const rows=e.items.map((it,i)=>`
    <div class="form-grid" style="grid-template-columns:1.1fr 1.6fr .9fr auto;gap:8px;align-items:end;margin-bottom:8px">
      <label class="field"><span class="field-label">字段名</span>
        <input class="input" data-pf-label="${i}" value="${esc(it.label||it.key||"")}" placeholder="例如 身份证号"></label>
      <label class="field"><span class="field-label">值</span>
        <input class="input" data-pf-value="${i}" value="${esc(it.value||"")}" placeholder="填写内容"></label>
      <label class="field"><span class="field-label">类型</span>
        <select class="select" data-pf-kind="${i}">
          ${["text","phone","id","date","bool"].map(k=>`<option value="${k}" ${((it.kind||"text")===k)?"selected":""}>${({text:"文本",phone:"电话",id:"证件号",date:"日期",bool:"是/否"})[k]}</option>`).join("")}
        </select></label>
      <button type="button" class="button danger" data-pf-del="${i}">删除</button>
    </div>`).join("");
  return `<section class="panel" style="padding:18px;margin-bottom:14px;border:1px solid #cfe3da;background:#fbfdfc">
    <div class="panel-title">${e.id?"编辑资料":"新建资料"}</div>
    <label class="field" style="max-width:420px;margin-top:10px"><span class="field-label">资料名称</span>
      <input class="input" id="pf-name" value="${esc(e.name||"")}" placeholder="例如 我的实名信息"></label>
    <div style="margin-top:14px"><div class="field-label">字段（想加什么就加什么）</div>${rows||'<div class="panel-caption">还没有字段，点下面添加。</div>'}</div>
    <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
      <button type="button" class="button" id="pf-add-row">＋ 添加字段</button>
      <button type="button" class="button primary" id="pf-save">保存</button>
      <button type="button" class="button" id="pf-cancel">取消</button>
    </div></section>`;
}
function syncProfileForm(view){
  // 重画之前必须先把页面上已输入的内容收进状态，否则点击"添加字段/删除"会丢掉刚填的值。
  const name=$("#pf-name"); if(name) profileEdit.name=String(name.value||"");
  $$('[data-pf-label]',view).forEach(inp=>{
    const i=Number(inp.dataset.pfLabel);
    if(!profileEdit.items[i]) return;
    profileEdit.items[i].label=String(inp.value||"");
    const v=$(`[data-pf-value="${i}"]`); if(v) profileEdit.items[i].value=String(v.value||"");
    const k=$(`[data-pf-kind="${i}"]`); if(k) profileEdit.items[i].kind=String(k.value||"text");
  });
  profileEdit.items.forEach(it=>{ if(!it.key) it.key=it.label||"" });
}
function bindProfileForm(view){
  const refresh=()=>{ render() };
  $$('[data-pf-del]',view).forEach(b=>b.onclick=()=>{ syncProfileForm(view); profileEdit.items.splice(Number(b.dataset.pfDel),1); render() });
  $("#pf-add-row").onclick=()=>{ syncProfileForm(view); profileEdit.items.push({key:"",label:"",value:"",kind:"text"}); render() };
  $("#pf-cancel").onclick=()=>{ profileEdit=null; render() };
  $("#pf-save").onclick=async()=>{
    const name=String($("#pf-name")?.value||"").trim();
    const items=[];
    $$('[data-pf-label]',view).forEach(inp=>{
      const k=inp.dataset.pfLabel;
      const label=String(inp.value||"").trim();
      const value=String(($(`[data-pf-value="${k}"]`)||{}).value||"");
      const kind=String(($(`[data-pf-kind="${k}"]`)||{}).value||"text");
      if(label||value) items.push({key:label||value,label,value,kind,verified:false});
    });
    if(!name){toast("请填资料名称",true);return}
    if(!items.length){toast("至少添加一个字段",true);return}
    try{
      if(profileEdit.id){ await api(`/v1/profiles/${encodeURIComponent(profileEdit.id)}`,{method:"PATCH",body:JSON.stringify({display_name_zh:name,display_name_en:name,items})}); toast("已保存") }
      else { await api("/v1/profiles",{method:"POST",body:JSON.stringify({display_name_zh:name,display_name_en:name,items})}); toast("已新建") }
      profileEdit=null; render();
    }catch(e){toast(e.message,true)}
  };
}
async function renderProfiles(view){
  let rows=[]; try{ rows=((await api("/v1/profiles"))||{}).items||[] }catch(e){ rows=[] }
  const editing=(profileEdit!==null);
  view.innerHTML=`${proModeButtons()}${titleBlock("PERSONAL PROFILE","个人资料","实名、证件、联系方式等敏感信息放在这里，场景只引用不复制。字段可随时增删改；列表默认显示掩码。")}
   ${editing?profileFormHtml():""}
   <section class="panel" style="padding:18px;margin-bottom:14px">
     <div class="panel-title">资料 ${rows.length?`· ${rows.length} 份`:""}</div>
     <div class="panel-caption" style="margin:6px 0 10px;padding:10px 12px;background:#fff6f6;border:1px solid #f0c9c9;border-radius:8px">
       <strong style="color:#b91c1c">⚠️ 这些资料一旦交给执行操作的智能体，就无法回收</strong><br>
       交给智能体意味着它可能进入该智能体所连模型的上下文、被写进记忆或日志。<br>
       所以：只给本次要用的字段、只在本次使用、用完即失效；每提供一次都会在这里留痕。
     </div>
     <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
       <button class="button primary" id="profile-add">＋ 新建一份资料</button>
       <button class="button" id="profile-refresh">↻ 刷新</button>
     </div>
     <div id="profile-usage" style="margin-top:16px"></div>
     <div id="profile-list" style="margin-top:14px;display:grid;gap:10px">
       ${rows.length?rows.map(p=>`
         <div class="decision-detail" style="margin:0">
           <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
             <strong>${esc(p.display_name_zh||p.id)}</strong>
             <span class="badge neutral">${(p.items||[]).length} 个字段</span>
             <span style="margin-left:auto;display:flex;gap:6px">
               <button class="button" data-edit-profile="${esc(p.id)}">编辑</button>
               <button class="button danger" data-del-profile="${esc(p.id)}">删除</button>
             </span>
           </div>
           <div class="panel-caption">${(p.items||[]).map(it=>esc(it.label||it.key)+"："+esc(maskValue(it.value))).join(" ｜ ")||"（还没有字段）"}</div>
         </div>`).join(""):`<div class="empty-state">还没有资料。点上面的「新建一份资料」开始。</div>`}
     </div></section>`;
  $("#profile-refresh").onclick=()=>render();
  $("#profile-add").onclick=()=>{ profileEdit={name:"",items:[{key:"",label:"",value:"",kind:"text"}]}; render() };
  $$('[data-edit-profile]',view).forEach(b=>b.onclick=()=>{
    const rec=rows.filter(x=>String(x.id)===String(b.dataset.editProfile))[0]||{};
    profileEdit={id:rec.id,name:rec.display_name_zh||"",items:(rec.items||[]).map(x=>Object.assign({},x))};
    render();
  });
  $$('[data-del-profile]',view).forEach(b=>b.onclick=async()=>{
    if(!confirm("删除这份资料？删除后不可恢复。"))return;
    try{await api(`/v1/profiles/${encodeURIComponent(b.dataset.delProfile)}`,{method:"DELETE"});toast("已删除");render()}catch(e){toast(e.message,true)}
  });
  // 反查：我的资料被谁用过
  try{
    const u=await api("/v1/profiles/usage");
    const box=$("#profile-usage");
    if(box){
      const items=(u&&u.items)||[];
      box.innerHTML=`<div class="panel-title">本机资料的使用记录 · ${items.length}</div>`+
        (items.length?`<div style="display:grid;gap:8px;margin-top:8px">${items.map(x=>`
          <div class="decision-detail" style="margin:0">
            <div class="panel-caption">${esc(x.at||"")} · 切片 ${esc(x.slice_id||"")} · 调用方 ${esc(x.caller||"")}</div>
            <div class="panel-caption">提供字段：${esc((x.fields||[]).join("、"))}${(x.missing||[]).length?`（本机缺：${esc((x.missing||[]).join("、"))}）`:""}</div>
          </div>`).join("")}</div>`
        :`<div class="panel-caption" style="margin-top:6px">还没有被使用过。</div>`);
    }
  }catch(e){ }
  if(editing) bindProfileForm(view);
}
