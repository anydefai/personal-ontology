"""样例自足性验收：只凭方式二那篇样例，就能建出【能打分】的框架。

    ~/personal-ontology/.venv/bin/python tests/test_sample_selfsufficient.py

为什么需要它：样例曾经缺「行业」字段、也不含作者侧的行业侧重表，
照着样例建出来的切片分数恒为 0 —— 这个测试把"样例自足"钉住。
"""
import json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import line_format as LF, engine

RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

# 用 node 跑真实的 docSample()，拿到的就是用户点【填入样例】看到的那篇
js = (
    'const fs=require("fs"),vm=require("vm");'
    f'const src=fs.readFileSync({json.dumps(str(ROOT / "web" / "pro.js"))},"utf8");'
    'const noop=()=>{}, el=()=>({style:{},dataset:{},classList:{add:noop,remove:noop,contains:()=>false},'
    'appendChild:noop,insertBefore:noop,setAttribute:noop,getAttribute:()=>null,querySelector:()=>null,'
    'querySelectorAll:()=>[],addEventListener:noop,children:[],innerHTML:"",textContent:""});'
    'const ctx={console,setTimeout,clearTimeout,setInterval,clearInterval,'
    'document:{createElement:el,querySelector:()=>null,querySelectorAll:()=>[],addEventListener:noop,body:el()},'
    'window:{addEventListener:noop,removeEventListener:noop,location:{},localStorage:{getItem:()=>null,setItem:noop},'
    'sessionStorage:{getItem:()=>null,setItem:noop},CSS:{escape:x=>x}},alert:noop,confirm:()=>true,api:async()=>({}),'
    'esc:x=>String(x==null?"":x),fieldLabel:()=>"",load:async()=>[],isProSlice:()=>true,displayName:()=>"",'
    'proModeButtons:()=>"",titleBlock:(a,b)=>"<b>"+b+"</b>",hint:t=>t,row:h=>h,input:()=>"",del:()=>"",'
    'clone:o=>JSON.parse(JSON.stringify(o)),requestAnimationFrame:noop};'
    'ctx.globalThis=ctx; vm.createContext(ctx); vm.runInContext(src,ctx);'
    'process.stdout.write(ctx.docSample());'
)
r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
check("能取到样例文本（node 跑 docSample）", r.returncode == 0 and len(r.stdout) > 200, (r.stderr or "")[-120:])
text = r.stdout

parts, errs = LF.split_document(text)
texts = {k: ("\n".join(v) if isinstance(v, list) else v) for k, v in parts.items()}
out = LF.apply_lines({}, texts)
fw, rep = out["framework"], out["report"]
allbad = list(errs) + [e for rr in rep.values() for e in rr["errors"]]
check("整篇样例走真实导入：0 解析错误", not allbad, str(allbad[:2]))

check("样例带作者侧的行业侧重表（重量级缺口）",
      bool(fw.get("industry_map")) and bool(fw.get("industry_weights")),
      "industry_map=%s weights=%s" % (bool(fw.get("industry_map")), bool(fw.get("industry_weights"))))
check("调用方字段里有「行业」（否则取不到权重）",
      any(x.get("name") == "行业" for x in (fw.get("inputs") or [])), str([x.get("name") for x in fw.get("inputs") or []]))
check("「行业」给出了具体可选取值（不是占位「文字」两个字）",
      len([x for x in (fw.get("inputs") or []) if x.get("name") == "行业"][0].get("values") or []) >= 3,
      str([x for x in (fw.get("inputs") or []) if x.get("name") == "行业"]))
dims = sorted({s.get("dimension") for s in (fw.get("signals") or []) if s.get("dimension")})
w_dims = sorted({d for w in (fw.get("industry_weights") or {}).values() for d in w})
check("权重表的维度名与信号里的维度名完全一致（否则按 0 分算）",
      dims == w_dims, "信号 %s ｜ 权重 %s" % (dims, w_dims))

data = {"行业": "房地产", "不动产权属": "有瑕疵", "未决诉讼金额占比": 7.5, "对外担保": "有未披露",
        "业绩对赌条款": "无", "数据合规结论": "基本合规", "市盈率": 46, "行业平均市盈率": 32,
        "客户集中度": 58, "交易结构": "股权收购", "标的为国资背景": "否"}
p = engine.judge(fw, data)
check("只凭这份样例就能打分（分数 > 0）", (p.get("score") or 0) > 0, "分数 %s" % p.get("score"))
check("给出的结论与命中信号符合样例规则",
p.get("decision") in ("交易风险极高", "交易风险高", "交易风险中等", "交易风险低") and (p.get("signals") or {}).get("权属瑕疵") is True,
      "%s / %s" % (p.get("decision"), p.get("signals")))

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
