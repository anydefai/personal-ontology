"""i18n 文本替换逻辑自检（含"剥掉符号前缀再查"的回退）。

    ~/personal-ontology/.venv/bin/python tests/test_i18n_text.py

动机：按钮文本常把图标与文字放在同一个文本节点里（"↻ 刷新"、"＋ 新建"），
而替换是按文本节点精确匹配的 → 查不到 → 保持中文；且扫描器只抽中文片段，
这类缺口不会出现在待补清单里。回退逻辑：剥掉开头符号与空白再查，命中后接回前缀。
"""
import pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "web/i18n.js").read_text(encoding="utf-8")
if not (re.search(r"const PREFIX_RE = /.*?/;", SRC, re.S) and re.search(r"function translateText\(text\) \{.*?\n  \}", SRC, re.S)):
    print("  ✗ 无法从 web/i18n.js 抠出 PREFIX_RE 或 translateText"); sys.exit(1)

harness = r'''const fs=require("fs");
const src=fs.readFileSync(process.argv[1],"utf8");
const pre=src.match(/const PREFIX_RE = \/.*?\/;/s)[0];
const fn=src.match(/function translateText\(text\) \{[\s\S]*?\n  \}/)[0];
const DICT={"刷新":"Refresh","刷新状态":"Refresh status","新建主体":"New Principal","需求反馈":"Feedback"};
const RULES=[];
const translateInner=v=>v;
const translateText=eval("(function(){"+pre+"\n"+fn+"\nreturn translateText;})()");
const cases=[["↻ 刷新","↻ Refresh"],["↻ 刷新状态","↻ Refresh status"],["＋ 新建主体","＋ New Principal"],
 ["✉ 需求反馈","✉ Feedback"],["  刷新  ","  Refresh  "],["未收录的短语","未收录的短语"],["Refresh","Refresh"],
 ["刷新","Refresh"]];
let ok=0;
for(const c of cases){
  const got=translateText(c[0]); const pass=got===c[1]; if(pass)ok++;
  console.log("  "+(pass?"✔":"✗")+" 「"+c[0]+"」→「"+got+"」"+(pass?"":"  期望「"+c[1]+"」"));
}
console.log("\n===== "+ok+"/"+cases.length+" 项通过 =====");
process.exit(ok===cases.length?0:1);'''
out = subprocess.run(["node", "-e", harness, str(ROOT / "web/i18n.js")], capture_output=True, text=True)
print(out.stdout.rstrip())
if out.returncode != 0:
    print(out.stderr.strip()[:300]); sys.exit(1)
