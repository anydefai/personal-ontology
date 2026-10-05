"""专业判断侧界面（R2）静态验收。

    ~/personal-ontology/.venv/bin/python tests/test_professional_ui.py

界面无法在无口令环境下点开，因此这里做**静态断言**：入口存在、日常路径未被改写、
资源版本号已升、专业串都有中英词条。运行时行为由 test_professional_model.py 覆盖。
"""
import pathlib, re, sys

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
check("资源版本号已更新为 2026-10-04 版", v is not None and v.group(1).startswith("20261004"), v.group(1) if v else "无")
# ⑥ 专业串有中英词条
for zh in ("专业技能场景", "我的判断规则", "判断条目", "权威级别", "所属场景"):
    check(f"词条已收录：{zh}", ('"%s":' % zh) in i18n)

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
sys.exit(0 if p == len(RESULTS) else 1)
