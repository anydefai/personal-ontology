"""主体类型枚举验收：个人 / 智能体 / 群组 / 角色 / 组织 / 服务。

    ~/personal-ontology/.venv/bin/python tests/test_principal_types.py
"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

line = [l for l in (ROOT / "ontology" / "shapes.ttl").read_text(encoding="utf-8").split("\n")
        if "po:principalType" in l][0]
for kind in ("person", "agent", "group", "role", "org", "service"):
    check("枚举含 %s" % kind, '"%s"^^xsd:string' % kind in line)
a = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
check("前端下拉有「服务」选项", 'value:"service"' in a)
check("下拉里 agent 标为「智能体」", 'label:"智能体"' in a)
check("列表显示名映射里 agent 也叫「智能体」", 'agent:"智能体"' in a)
s = (ROOT / "web" / "pro.js").read_text(encoding="utf-8")
check("镜像主体按 agent 建（程序＝智能体）", 'principal_type: "agent"' in s)

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
