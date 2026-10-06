"""前端语法检查（堵住"测试只读文本、抓不到语法错误"的盲区）。

    ~/personal-ontology/.venv/bin/python tests/test_frontend_syntax.py

背景：2026-10-04 我把 app.js 写出语法错误，而当时 3 套"全绿"的界面测试
只把 app.js 当**文本**读，根本没有执行它，所以谁都没抓住 ✗
本测试对 web/ 下每个 .js 跑一次 `node --check`，语法错误当场失败。
"""
import pathlib, shutil, subprocess, sys

RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label))
    print(("  ✔ " if ok else "  ✗ ") + label + (f" — {detail}" if detail and not ok else ""))

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
files = sorted(p for p in WEB.glob("*.js"))
check("找到前端脚本", len(files) >= 2, str([p.name for p in files]))
check("本机有 node（语法检查依赖它）", shutil.which("node") is not None, "未找到 node")

for f in files:
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    check(f"{f.name} 语法正确", r.returncode == 0, (r.stderr or "").strip().split("\n")[-1][:160])

# index.html 引用的脚本必须都存在（避免 404 的静默失败）
html = (WEB / "index.html").read_text(encoding="utf-8")
import re
refs = re.findall(r'src="/assets/([A-Za-z0-9_.-]+)\?v=', html)
check("外壳引用的脚本都存在", all((WEB / r).exists() for r in refs),
      str([r for r in refs if not (WEB / r).exists()]))
check("引用的脚本都在被检查之列", all((WEB / r) in files for r in refs), str(refs))



def check_iife_scope():
    """node --check 查不出"作用域被切开"这类错：一个函数定义在 IIFE 里，却在 IIFE 之外被调用。

    真实事故：pro.js 的 IIFE 在第 748 行就结束了，而我在文件末尾追加的渲染函数在 IIFE 之外
    调用了 hasFramework -> 场景切片页直接报 "hasFramework is not defined"。
    """
    src = (ROOT / "web" / "pro.js").read_text(encoding="utf-8")
    lines = src.split("\n")
    close = next((i for i, l in enumerate(lines) if l.strip() == "})();"), None)
    if close is None:
        return True, "没有 IIFE（无需检查）"
    inner = set()
    for l in lines[:close]:
        m = re.match(r"^  (?:async )?function ([A-Za-z_$][\w$]*)", l)
        if m:
            inner.add(m.group(1))
    outer = "\n".join(lines[close + 1:])
    bad = sorted(n for n in inner if re.search(r"\b" + re.escape(n) + r"\s*\(", outer))
    # 变量同理：只在 IIFE 内用 var 声明的名字，IIFE 外不能裸用
    declared = set()
    for l in lines[:close]:
        m = re.match(r"^  var ([A-Za-z_$][\w$]*)", l)
        if m:
            declared.add(m.group(1))
    for l in lines[close + 1:]:
        for name in declared:
            if re.search(r"(?<![\w.])" + re.escape(name) + r"\b", l):
                bad.append(name + "(变量)")
    if bad:
        return False, f"这些 IIFE 内部函数在 IIFE 之外被调用：{bad}"
    return True, f"IIFE 之外没有调用 IIFE 内部函数（内部共 {len(inner)} 个函数）"


check("IIFE 作用域没被切开（IIFE 外不调用内部函数）", *check_iife_scope())


def check_template_splices():
    """抓"+ +字符串"这种断裂拼接：它在 JS 里合法（一元加号），node --check 不报错，
    但会把模板拼成 NaN，于是整块面板（含按钮）渲染不出来 —— 正是"点了没反应"的真实成因。
    """
    bad = []
    for f in sorted((ROOT / "web").glob("*.js")):
        for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"\+\s*\+\s*[\"'`]", line):
                bad.append(f"{f.name}:{n}")
    if bad:
        return False, f"这些行有多余的 +（模板会拼成 NaN）：{bad}"
    return True, "没有断裂的模板拼接"


check("模板拼接没有断裂（+ 后直接跟字符串会拼成 NaN）", *check_template_splices())
p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
sys.exit(0 if p == len(RESULTS) else 1)
