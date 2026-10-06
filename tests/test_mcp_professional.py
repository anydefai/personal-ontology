"""MCP 侧专业技能可用性验收：目录带调用说明 + 真有能调用的工具。

    ~/personal-ontology/.venv/bin/python tests/test_mcp_professional.py
"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = []
def check(label, cond, detail=""):
    print(("  ✔ " if cond else "  ✗ ") + label + ((" — " + str(detail)) if detail and not cond else ""))
    RESULTS.append(bool(cond))

src = (ROOT / "backend" / "mcp_server.py").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT))
import backend.mcp_server as m

names = [t["name"] for t in m.TOOLS]
check("暴露了 judge_professional_slice（智能体真能调专业判断）", "judge_professional_slice" in names, str(names))
tool = next((t for t in m.TOOLS if t["name"] == "judge_professional_slice"), {})
check("入参含 slice_id 与 data", "slice_id" in str(tool.get("inputSchema")) and "data" in str(tool.get("inputSchema")))
check("说明里要求切片已启用、并写明缺项后果",
      "确认并启用" in str(tool.get("description")) and "信息不足" in str(tool.get("description")))
check("目录对专业切片附上调用说明", 'instances[-1]["professional"]' in src and "kind_label" in src)
check("调用前检查是否已启用，未启用明确拒绝",
      "contract = self._api(\"GET\"" in src and "确认并启用，现在不能调用" in src)
check("说明只走 contract 接口，不直接吐框架", "industry_weights" not in src and "/contract" in src)

ok = sum(1 for x in RESULTS if x)
print("\n===== %d/%d 项通过 =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
