"""i18n 插值串规则（RULES）自检。

    ~/personal-ontology/.venv/bin/python tests/test_i18n_rules.py

动机：形如「已有场景实例 · 3」「等待你批准 · 1」的文案，其文本节点里带着数字或
字段名，精确匹配（DICT）覆盖不到，必须用 RULES 正则。本测试从 web/i18n.js 里
抠出真实的 DICT 与 RULES 来跑，因此不会与实现漂移。
"""
import pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
JS = r"""const fs=require("fs");
const src=fs.readFileSync(process.argv[1],"utf8");
const st=src.indexOf("const DICT");let d=0,e=-1;
for(let i=src.indexOf("{",st);i<src.length;i++){if(src[i]==="{")d++;else if(src[i]==="}"){d--;if(!d){e=i;break}}}
const DICT=eval("("+src.slice(src.indexOf("{",st),e+1)+")");
const rs=src.indexOf("const RULES = [");let d2=0,e2=-1;
for(let i=src.indexOf("[",rs);i<src.length;i++){if(src[i]==="[")d2++;else if(src[i]==="]"){d2--;if(!d2){e2=i;break}}}
const RULES=eval(src.slice(src.indexOf("[",rs),e2+1));
function T(text){const t=text.trim();if(!t)return text;let x=DICT[t];if(x)return text.replace(t,x);
 for(const [p,r] of RULES){if(!p.test(t))continue;const rep=typeof r==="function"?t.replace(p,r):t.replace(p,r);return text.replace(t,DICT[rep]||rep);}return text;}
const cases=[["已有场景实例 · 3","Existing scenario instances · 3"],["授权规则 · 2（1 条生效中）","Authorization rules · 2 (1 active)"],
["等待你批准 · 1","Waiting for your approval · 1"],["已授权 · 2","Authorized · 2"],["实例演进与执行记录 · 5","Instance history and runs · 5"],
["搜索主体…","Search Principals…"],["搜索场景实例","Search Scenario instances"],["3 条规则","3 rules"]];
let ok=0;for(const [a,b] of cases){const g=T(a);const p=g===b;if(p)ok++;console.log(`  ${p?"✔":"✗"} 「${a}」→「${g}」`+(p?"":`  期望「${b}」`));}
console.log(`\n===== ${ok}/${cases.length} 项通过 =====`);process.exit(ok===cases.length?0:1);
"""
out = subprocess.run(["node", "-e", JS, str(ROOT / "web/i18n.js")], capture_output=True, text=True)
print(out.stdout.rstrip())
if out.returncode != 0:
    print(out.stderr.strip()[:300]); sys.exit(1)
