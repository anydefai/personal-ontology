"""i18n 覆盖率防回退检查。

    ~/personal-ontology/.venv/bin/python tests/test_i18n_coverage.py

机制：渲染后按文本节点精确匹配替换，未收录的串保持中文原文。
本测试扫描 web/index.html 与 web/app.js 里的中文串，与词典做差，报告未收录数量。
**基线**：当前已知未收录的数量。新增界面文案若忘记补词条，数量会上升 → 测试失败。
完整清单：docs/i18n-pending.md
"""
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = 60           # 2026-10-02：含词典/RULES 内中文注释的扫描噪音

def scan():
    script = '''
const fs=require("fs");
const i18n=fs.readFileSync("web/i18n.js","utf8");
const keys=new Set();
for(const m of i18n.matchAll(/"([^"\\n]*[\\u4e00-\\u9fff][^"\\n]*)"\\s*:/g)) keys.add(m[1]);
for(const m of i18n.matchAll(/'([^'\\n]*[\\u4e00-\\u9fff][^'\\n]*)'\\s*:/g)) keys.add(m[1]);
function scan(file){
  const src=fs.readFileSync(file,"utf8"); const found=new Set();
  for(const m of src.matchAll(/[\\u4e00-\\u9fff][\\u4e00-\\u9fff\\u3000-\\u303f\\uff00-\\uffefA-Za-z0-9 《》“”‘’·、，。：；！？（）\\-—…%/\\.]*/g)){
    const s=m[0].replace(/[·。，、）]+$/,"").trim(); if(s.length>=2) found.add(s);
  }
  return [...found].filter(s=>!keys.has(s));
}
console.log(JSON.stringify({html:scan("web/index.html"),app:scan("web/app.js")}));
'''
    out = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        print("  ✗ 扫描失败：", out.stderr.strip()[:200]); sys.exit(1)
    return json.loads(out.stdout)

data = scan()
total = len(data["html"]) + len(data["app"])
print(f"  未收录界面文案：HTML {len(data['html'])} 条 + app.js {len(data['app'])} 条 = {total} 条")
print(f"  基线：{BASELINE} 条（完整清单见 docs/i18n-pending.md）")
if total <= BASELINE:
    print(f"  ✔ 未超出基线（较基线减少 {BASELINE - total} 条）" if total < BASELINE else "  ✔ 与基线持平")
    sys.exit(0)
print(f"\n  ✗ 未收录数量较基线增加 {total - BASELINE} 条——新增界面文案请补词条：")
for s in (data["html"] + data["app"])[:15]:
    print("     ·", s)
sys.exit(1)
