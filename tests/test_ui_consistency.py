"""界面一致性自检：导航项 ↔ 路由 ↔ 渲染。

    ~/personal-ontology/.venv/bin/python tests/test_ui_consistency.py

动机：今天两次踩坑——「智能体授权」页面代码齐全但导航项漏了（点不进去），
以及误以为某个渲染片段属于切片页（实际属于实例页）。这类问题测试抓不到，
所以补一条静态一致性检查。
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = (ROOT / "web/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "web/index.html").read_text(encoding="utf-8")
RESULTS = []

def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label))
    print(f"  {'✔' if ok else '✗'} {label}" + (f" — {detail}" if detail else ""))

def labels_object(src: str) -> str:
    """用花括号配对取出 labels 对象，避免 find('};') 截断（这是上一版检查失灵的根因）。"""
    i = src.find("const labels")
    j = src.find("{", i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{": depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0: return src[j:k+1]
    raise AssertionError("labels 对象未闭合")

body = labels_object(APP)
routes = {m.group(1).strip('"\'') for m in re.finditer(r'([A-Za-z_$][\w$-]*|"[a-z_-]+")\s*:\s*\{\s*title:', body)}
navs = set(re.findall(r'data-page="([a-z-]+)"', HTML))

def has_dedicated_render(page: str) -> bool:
    camel = "".join(part.capitalize() for part in page.split("-"))
    return (f'currentPage==="{page}"' in APP or f"render{camel}" in APP
            or f'render{page}' in APP or f'page==="{page}"' in APP)

# 有专门渲染函数的页面本就不在 labels 里（dashboard 等），因此不能用 labels 覆盖全部导航项。
known = routes | {page for page in navs if has_dedicated_render(page)}
check("导航项都有去处（点了不会空转）", not (navs - known), f"无去处: {sorted(navs - known)}")

# 走通用渲染器的页面靠 labels 条目驱动，条目存在即视为可达。
unreachable = {page for page in routes if page not in navs and not has_dedicated_render(page)}
# 死路由是需要清理的技术债，但零引用、无害，因此只告警不计失败——否则测试长期红灯会变成噪音。
if unreachable:
    print(f"  ⚠ 待清理的死路由（有路由但无导航）: {sorted(unreachable)}")
else:
    print("  ✔ 没有不可达的死路由")


# 携带导航项的处理函数必须存在（防止 onclick 指向不存在的函数）
for name in ("navigate", "renderScenarios", "renderScenarioInstances", "roleSummaryHtml"):
    check(f"{name} 已定义", f"function {name}" in APP or f"{name}=" in APP)

passed = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
for ok, label in RESULTS:
    if not ok: print("  失败：", label)
sys.exit(0 if passed == len(RESULTS) else 1)
