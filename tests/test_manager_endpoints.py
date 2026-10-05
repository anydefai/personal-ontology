"""管理器端点与「用到但未导入」的回归检查。

    ~/personal-ontology/.venv/bin/python tests/test_manager_endpoints.py

为什么有这套测试：2026-10 的双语改造中，manager.py 里加了
`display_language(request.headers...)` 却**忘了导入**，导致
「服务监控 → 重启后端」抛 NameError、界面报 Internal Server Error。
`py_compile` 与导入都发现不了函数体里的 NameError，只有调用才会暴露，
而当时管理器端点没有任何测试覆盖 —— 所以这里补上静态与在线两类检查。
"""
import ast, json, pathlib, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(("  ✔ " if ok else "  ✗ ") + label + (f" — {detail}" if detail and not ok else ""))

WATCHED = {"display_language", "msg_for", "messages", "normalize_language", "MESSAGES"}

def missing_names(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported, defined = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names: imported.add(a.asname or a.name)
        elif isinstance(n, ast.Import):
            for a in n.names: imported.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(n.name)
            for a in n.args.args + n.args.kwonlyargs + n.args.posonlyargs: defined.add(a.arg)
        elif isinstance(n, ast.ClassDef):
            defined.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Name): defined.add(sub.id)
        elif isinstance(n, ast.comprehension):
            for sub in ast.walk(n.target):
                if isinstance(sub, ast.Name): defined.add(sub.id)
        elif isinstance(n, ast.ExceptHandler) and n.name: defined.add(n.name)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return sorted((used & WATCHED) - imported - defined)

# ① 静态：所有后端模块对共享工具的调用都必须有导入
for f in sorted((ROOT / "backend").glob("*.py")):
    miss = missing_names(f)
    check(f"{f.name} 无「用到但未导入」", not miss, str(miss))

# ② 静态：manager 模块命名空间里必须真的能解析出 display_language
sys.path.insert(0, str(ROOT))
from backend import manager
check("manager 模块可解析 display_language", "display_language" in vars(manager))

# ③ 在线：管理器的只读端点必须可用（管理器始终运行）
def head(path):
    with urllib.request.urlopen(f"http://127.0.0.1:8765{path}", timeout=8) as r:
        return dict(r.headers), r.read()

def get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:8765{path}", timeout=8) as r:
        return r.status, json.loads(r.read() or b"{}")
try:
    st, body = get("/manager/health")
    check("GET /manager/health 可用", st == 200 and body.get("status") == "ok", f"{st} {str(body)[:80]}")
    headers, body = head("/")
    check("控制台 HTML 带 no-store（改前端立即生效）",
          "no-store" in headers.get("cache-control", ""), str(headers.get("cache-control")))
    check("控制台 HTML 引用当前资源版本号",
          b"assets/app.js?v=20261004a" in body, body[:0] and "" or "未见 ?v=20261004a")
    # 控制端点的存在性用路由表检查（调用它们会真的重启后端，不适合放在测试里）
    paths = {r.path for r in manager.app.routes if hasattr(r, "path")}
    for path in ("/manager/status", "/manager/start", "/manager/restart", "/manager/logs"):
        check(f"控制端点已注册：{path}", path in paths, str(sorted(paths))[:160])
except Exception as exc:
    check("管理器只读端点可访问", False, repr(exc))

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok: print("  失败：", l)
sys.exit(0 if p == len(RESULTS) else 1)
