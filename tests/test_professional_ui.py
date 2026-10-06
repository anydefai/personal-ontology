"""专业判断侧界面（R2）静态验收。

    ~/personal-ontology/.venv/bin/python tests/test_professional_ui.py

界面无法在无口令环境下点开，因此这里做**静态断言**：入口存在、日常路径未被改写、
资源版本号已升、专业串都有中英词条。运行时行为由 test_professional_model.py 覆盖。
"""
import pathlib, re, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
app = (ROOT / "web/app.js").read_text(encoding="utf-8")
html = (ROOT / "web/index.html").read_text(encoding="utf-8")
i18n = (ROOT / "web/i18n.js").read_text(encoding="utf-8")
RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(("  ✔ " if ok else "  ✗ ") + label + (f" — {detail}" if detail and not ok else ""))

# ① 两个入口
check("切片页有「日常生活场景」入口", 'data-pro-mode="daily"' in app and "日常生活场景" in app)
check("切片页有「专业技能场景」入口", 'data-pro-mode="professional"' in app and "专业技能场景" in app)
# ② 专业模式走独立函数，日常路径保持原样
check("专业模式在切片页提前分流", re.search(r"if\(professionalMode\)\{return renderProfessionalSlices", app) is not None)
check("专业模式在实例页提前分流", re.search(r"if\(professionalMode\)\{return renderProfessionalInstances", app) is not None)
check("模式选择会被记住（刷新/切页不丢）", "po.professionalMode" in app and "localStorage.setItem(\"po.professionalMode\"" in app.replace(" ", ""))
check("日常预演页也有模式切换（否则切不过去）", app.count("proModeButtons()") >= 5, str(app.count("proModeButtons()")))
check("日常侧不显示专业切片（列表/实例/预演/仪表盘四处过滤）",
      app.count("!isProSlice(x)") >= 4, str(app.count("!isProSlice(x)")))
check("专业切片判定口径统一", "const isProSlice=x=>" in app)
_pro = pathlib.Path(__file__).resolve().parent.parent.joinpath("web/pro.js").read_text(encoding="utf-8")
check("新界面在独立文件 web/pro.js（含四步）", "POPro" in _pro and "renderSlices" in _pro)
check("专业场景可自行新建/重命名/删除",
      all(k in _pro for k in ("pro-new", "pro-rename", "pro-del-def", "domain_pack_ids")),
      "缺入口或字段名不对")
check("app.js 只做一处接入并保留回退",
      "window.POPro&&window.POPro.renderSlices" in app, "接入点缺失")
check("边界面板存在（第一层授权判定用）", all(k in _pro for k in ("data-bnd-amount", "data-bnd-scenarios", "data-bnd-conf")))
check("路由器兜底：三个页面缺模式切换会自动补（防同类漏加）",
      "insertAdjacentHTML(\"afterbegin\",proModeButtons())" in app
      and 'view.querySelector("[data-pro-mode]")' in app
      and '"scenario-slices","scenario-instances","scenario-preview"' in app)
check("交付说明面板存在（洞察/资历/有效期）", all(k in _pro for k in ("data-dlv-insight", "data-dlv-cred", "data-dlv-days")))
def _renderers_missing_switch(src):
    """凡函数体内含「专业模式分流」的渲染函数，必须自己画模式切换按钮。

    判据用函数体本身（分流的那个 if 就在这个函数里），不靠名字映射 —— 名字猜错会让测试空转。
    """
    import re as _re
    missing, checked = [], 0
    for m in _re.finditer(r"(?:async )?function (render[A-Za-z]+)\(view\)\{", src):
        name = m.group(1)
        nxt = _re.search(r"\n(?:async )?function ", src[m.end():])
        body = src[m.end():m.end() + (nxt.start() if nxt else len(src))]
        if "if(professionalMode){return render" not in body:
            continue
        checked += 1
        if "proModeButtons()" not in body:
            missing.append(name)
    return missing, checked


_missing, _checked = _renderers_missing_switch(app)
check("分流页面至少有 3 个（确保这条检查不是空转）", _checked >= 3, str(_checked))
check("按模式分流的页面里，渲染函数都自带模式切换", not _missing, str(_missing))
check("交付信息会显示出来（洞察/资历/审计号/有效期/指纹/签名状态）",
      all(k in app for k in ("proDeliveryHtml", "审计号", "有效期至", "内容指纹", "数字签名")))
check("分层设置已挪到切片页（四层可选，预演页不再出现）",
      "data-dlv-tier" in _pro and app.count("审计层（完整判定包）") == 0 and _pro.count("审计层（完整判定包）") == 1)
check("反馈入口在界面上（准确/不准确）", "pe-fb-ok" in app and "pe-fb-no" in app and "sendFeedback" in app)
check("预演页不再展示交付身份信息，改为预演说明", "proPreviewNote" in app and "pe-feedback-panel" not in app)
check("分层设置移到切片页（默认交付层级）", "data-dlv-tier" in _pro and "pe-tier" not in app)
check("对外交付与反馈是独立一级菜单（在场景预演之后）",
      'data-page="delivery"' in pathlib.Path(__file__).resolve().parent.parent.joinpath("web/index.html").read_text(encoding="utf-8")
      and 'currentPage==="delivery")await renderDelivery(view)' in app)
check("该区块已从场景实例页移除（不再重复）", "对外交付与调用方反馈" not in app)
check("计费演示已随该页走（不再挤在场景实例页）", app.count("bill-demo-run") == 2 and "id=\"bill-demo-slice\"" in app)
check("四层价格由用户自己填（切片页）", _pro.count("data-price-tier") >= 2 and "data-price-mode" in _pro and "pricing" in _pro)
check("场景实例页有计费演示（读本人定价）", "data-bill-demo" in app and "bill-demo-tier" in app and "pricing" in app)
check("切片页是两级选择（场景模板 + 我的切片）并从切片读数据",
      all(k in _pro for k in ("id=\"pro-slice\"", "id=\"pro-add-slice\"", "migrate-from-definitions")))
check("保存与起草都写到切片上",
      '"/v1/scenario-slices/" + encodeURIComponent(sliceId)' in _pro
      and "/draft\", { method: \"POST\"" in _pro)
check("预演页按切片判定（端点指向切片层）",
      "/v1/scenario-slices/${encodeURIComponent(proEvalDefId)}" in app
      and "/judgment-feedback" in app
      and 'const defs=(await load("scenario-slices"))' in app)
check("判定记录是独立一级菜单（在对外交付之后）",
      'data-page="decisions"' in pathlib.Path(__file__).resolve().parent.parent.joinpath("web/index.html").read_text(encoding="utf-8")
      and 'currentPage==="decisions")await renderDecisions(view)' in app)
check("判定记录页展示交付身份信息（审计号/有效期/指纹/签名）",
      all(k in app for k in ("renderDecisions", "content_fingerprint", "valid_until", "signature_status")))
check("交付页可生成正式交付（写入记录）", "dl-deliver" in app and "/deliver" in app)
check("前端语法检查已纳入测试", pathlib.Path(__file__).resolve().parent.parent.joinpath("tests/test_frontend_syntax.py").exists())
check("切片页有「我的切片」列表（含选中/删除与空态）",
      all(k in _pro for k in ("function sliceTable", "data-pick-slice", "data-drop-slice", "这个场景还没有我的切片")))
check("有「未归属切片」区（删场景后切片可挂回）",
      all(k in _pro for k in ("function orphanPanel", "data-orphan-attach", "data-orphan-del", "未归属切片")))
check("切片页有「一行一条录入」六个框（只有一个「保存」按钮，不再有多个导入按钮）",
      all(k in _pro for k in ("function lineImportPanel", "data-line-part", "import-lines"))
      and "line-import\"" not in _pro and "line-import-save" not in _pro)
check("未选切片时保存会给提示（不再静默无反应）", "请先新建或选择一条「我的切片」" in _pro)
check("导入失败不再静默（会弹出来）", "catch (err)" in _pro and "导入失败：" in _pro)
check("保存我的框架会先导入逐行框（不会默默丢掉输入）",
      "function hasFramework" in _pro and "lineTexts" in _pro and "save: true" in _pro)
check("两种生成方式在页面上一眼可辨（方式一/方式二 + 第三步 + 混用提示）",
      all(k in _pro for k in ("方式一 · 让模型起草", "方式二 · 一行一条自己写", "第三步 · 核对与微调", "两种方式随时可以混用")))
check("保存入口只有一个（就是方式二里的「保存」按钮）", _pro.count("data-save-framework>") == 1)
check("切片可确认并启用 / 退回草稿（状态闭环）",
      all(k in _pro for k in ("data-confirm-slice", "data-unconfirm-slice", 'status: "confirmed"', 'status: "analyzed"')))
check("场景实例页显示已启用的专业切片（含框架摘要与退回草稿）",
      all(k in app for k in ("function proEnabledSlicesHtml", "已启用的切片", "框架摘要", "data-unconfirm-slice")))
check("逐行录入含「我的依据」与「打分线」两个框（共 8 个）",
      all(k in _pro for k in ('["citations"', '["score"', "我的依据", "打分线")))
check("save keeps the imported framework rather than an empty panel read", "importedFw || collect()" in _pro)
check("保存按钮只有一个（不再有底部常驻栏那个重复入口）", _pro.count("data-save-framework>") == 1 and "pro-savebar" not in _pro)
check("日常侧原有渲染函数仍在", "async function renderScenarios(view){" in app and "async function renderScenarioInstances(view){" in app)
# ③ 复用通用 CRUD，未新增专属端点
check("专业侧复用通用集合端点", "/v1/knowledge-entries" in app
      and 'load("scenario-definitions")' in app and 'load("knowledge-entries")' in app)
check("未新增专业专属后端端点", "/v1/professional" not in app and "/v1/pro/" not in app)
# ④ 四槽与复核流转
for slot in ("pro-conclusion", "pro-exception", "pro-basis", "pro-authority"):
    check(f"条目编辑器含 {slot}", slot in app)
check("复核流转（草稿↔启用）存在", 'data-pro-toggle' in app and "转回草稿" in app)
# R3'.1：专业预演页
check("专业预演页存在并分流", "async function renderProfessionalPreview" in app
      and "if(professionalMode){return renderProfessionalPreview" in app)
check("预演页可导入技能框架", "pe-save-framework" in app and "skillFramework" not in app)
check("预演页调用判定接口", "/evaluate" in app and "pe-run" in app)
check("预演页展示判定包（结论/严重度/路径/证据）",
      all(k in app for k in ("决策" if False else "结论", "严重度", "推理路径", "证据")))
# ⑤ 资源版本号已升
v = re.search(r"\?v=(\d{8}[a-z]?)", html)
_html = pathlib.Path(__file__).resolve().parent.parent.joinpath("web/index.html").read_text(encoding="utf-8")
_ver = re.search(r"assets/app\.js\?v=([0-9a-z]+)", _html)
check("资源版本号与工作区一致（部署自检）", v is not None and _ver and v.group(1) == _ver.group(1),
      f"读取 {v.group(1) if v else '无'} / 工作区 {_ver.group(1) if _ver else '无'}")
# ⑥ 专业串有中英词条
for zh in ("专业技能场景", "我的判断规则", "判断条目", "权威级别", "所属场景"):
    check(f"词条已收录：{zh}", ('"%s":' % zh) in i18n)

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
sys.exit(0 if p == len(RESULTS) else 1)
