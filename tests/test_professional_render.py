"""渲染验收：把专业侧的每个面板函数**真的跑一遍**，看它吐出的 HTML。

为什么需要这一套：`node --check` 只查语法。而我踩过的三次重大 bug 都是**语法合法**的：
  · hasFramework 在 IIFE 外被调用（作用域被切开）
  · enableFor 同一个盲区
  · 模板里多了一个 "+"，"..' + +" 是合法的一元加号，却把整块面板拼成 NaN，
    于是按钮根本没渲染出来，点它"没反应" —— 我用肉眼和语法检查都看不见它

    ~/personal-ontology/.venv/bin/python tests/test_professional_render.py
"""
import json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "web" / "pro.js").read_text(encoding="utf-8")
RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label))
    print(("  ✔ " if ok else "  ✗ ") + label + (f" — {detail}" if detail and not ok else ""))


def extract(name):
    i = SRC.index("function " + name)
    depth, j, in_str, q = 0, i, False, ""
    while j < len(SRC):
        c = SRC[j]
        if in_str:
            if c == "\\":
                j += 2
                continue
            if c == q:
                in_str = False
        else:
            if c in "\"'`":
                in_str, q = True, c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
        j += 1
    return SRC[i:j]


# 面板函数依赖的模块级常量：从源码里取出来一起放进测试脚本
CONSTS = ""
for name in ("TYPES", "OPS", "OP_LABEL", "INT_TYPE", "EX_KINDS", "TYPE_LABEL", "SEV_LABEL", "TYPE_HINT"):
    lines = SRC.split("\n")
    for k, line in enumerate(lines):
        if re.match(r"^\s*var " + name + r"\s*=", line):
            chunk = [line]
            # 单行没闭合就把后续行一起收进来，直到括号与分号平衡
            if line.count("[") + line.count("{") > line.count("]") + line.count("}"):
                for extra in lines[k + 1:]:
                    chunk.append(extra)
                    if extra.rstrip().endswith("];") or extra.rstrip().endswith("};"):
                        break
            CONSTS += "\n".join(chunk) + "\n"
            break

STUBS = """function esc(x){return String(x==null?"":x).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");}
function hint(t){return '<div class="panel-caption">'+t+'</div>';}
function input(v,attrs){return '<input '+(attrs||'')+' value="'+esc(v)+'">';}
function del(w){return '<button data-del="'+w+'">del</button>';}
function row(h){return '<div class="pro-row">'+h+'</div>';}
function titleBlock(a,b,c){return '<h1>'+b+'</h1>';}
"""

PANELS = ["inputsPanel", "weightsPanel", "thresholdsPanel", "signalsPanel",
          "rulesPanel", "exceptionsPanel", "tailPanels", "boundariesPanel", "deliveryPanel"]
FW_EMPTY = {}
FW_FULL = json.loads((ROOT / "tests" / "_render_fixture.json").read_text(encoding="utf-8")) \
    if (ROOT / "tests" / "_render_fixture.json").exists() else {
        "inputs": [{"name": "a", "type": "number"}],
        "industry_weights": {"keji": {"jishu": 0.35}},
        "industry_map": {"x": "keji"},
        "thresholds": {"base": 1.3, "adjustments": [{"condition": {"a": "b"}, "delta": 0.1}]},
        "signals": [{"name": "s1", "dimension": "jishu", "when": {"a": {"op": "gt", "value": 1}}},
                   {"name": "s2", "dimension": "caiwu", "when": {"a": {"op": "gt", "value": 2}}}],
        "combination_rules": [{"all_of": ["s1"], "conclusion": "c", "severity": "高"}],
        "exception_rules": [{"condition": {"all_signals": ["s1"]},
                             "override": {"kind": "reduce_weight", "target": "jishu", "factor": 0.5}}],
        "signal_priority": [{"signal": "s1", "priority": 1}],
        "citations": [{"text": "cite", "signals": []}],
        "score_bands": {"high": {"min": 0.5, "conclusion": "c", "severity": "高"}},
        "adjustment_log": [{"step": "s", "reason": "r"}],
    }

tmp = pathlib.Path(tempfile.mkdtemp()) / "render.js"
ok_all = True
for fn in PANELS:
    try:
        body = extract(fn)
    except ValueError:
        check(f"面板 {fn} 存在", False, "源码里找不到")
        ok_all = False
        continue
    # 参数形态：weights/thresholds/signals/rules/exceptions/tail 收 framework；另外几个收对象
    arg2 = "({})" if fn in ("boundariesPanel", "deliveryPanel") else "(FW)"
    script = STUBS + CONSTS + body + f"""
const FW = {json.dumps(FW_FULL, ensure_ascii=False)};
let out = "";
try {{ out = {fn}{arg2.replace('FW','FW')} || ""; }} catch (e) {{ console.log("THREW:" + e.message); process.exit(0); }}
console.log("LEN:" + out.length + "|NAN:" + (out.indexOf("NaN") >= 0 ? 1 : 0));
"""
    tmp.write_text(script, encoding="utf-8")
    r = subprocess.run(["node", str(tmp)], capture_output=True, text=True)
    line = (r.stdout or "").strip().split("\n")[-1] if r.stdout else ""
    if "THREW" in line:
        # 桩不全时不算页面 bug，但要报出来（不许静默）
        check(f"面板 {fn} 能渲染", False, f"测试桩不足：{line[6:80]}")
        ok_all = False
    elif line.startswith("LEN:"):
        length, nan = line[4:].split("|NAN:")
        check(f"面板 {fn} 能渲染且不含 NaN（长度 {length}）", nan == "0", "HTML 里出现 NaN")
    else:
        check(f"面板 {fn} 能渲染", False, (r.stderr or line)[-120:])

# 关键按钮/输入必须真的出现在 HTML 里
wp = extract("weightsPanel")
tmp.write_text(STUBS + CONSTS + wp + """
const fw = {industry_weights:{keji:{jishu:0.35}}, industry_map:{}};
const h = weightsPanel(fw);
console.log([h.indexOf('data-add="weight-cat"')>=0, h.indexOf('data-w-cat="0"')>=0,
             h.indexOf('data-w-val="0:jishu"')>=0, h.indexOf('data-im-lines')>=0].join(","));
""", encoding="utf-8")
r = subprocess.run(["node", str(tmp)], capture_output=True, text=True)
flags = (r.stdout or "").strip().split("\n")[-1].split(",")
check("权重表的列名来自信号维度（表为空时也不例外，否则会误说\u201c还没标维度\u201d）",
      "sg.dimension" in SRC and SRC.index("sg.dimension") > SRC.index("function weightsPanel"))

check("权重表在为空时也有一行可填（不依赖\u201c加一个行业\u201d按钮）",
      "cats = [\"新行业1\"]" in SRC)

check("折叠块真的插入了 summary（否则浏览器会显示它自己的默认文字）",
      "d.appendChild(sum)" in SRC and SRC.index("d.appendChild(sum)") < SRC.index("d.appendChild(sec)"))
check("权重面板真的吐出了：加行业按钮 · 行名输入 · 权重输入 · 归类框",
      flags == ["true", "true", "true", "true"], str(flags))

p = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {p}/{len(RESULTS)} 项通过 =====")
for ok, l in RESULTS:
    if not ok:
        print("  失败：", l)
sys.exit(0 if p == len(RESULTS) else 1)
