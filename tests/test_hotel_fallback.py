"""酒店兜底路径自检（覆盖一次漏测导致的 500）。

    ~/personal-ontology/.venv/bin/python tests/test_hotel_fallback.py

背景：给 add_fact 加上 language 参数时漏了 _hotel_fallback 这一层，
它没有 analyze 的局部变量 language → 用户点击「分析场景」时 NameError → 500。
之前没有任何测试跑到这条路径（需要"文本含酒店"且"模型返回空数组"两个条件同时成立）。
"""
import json, os, sys, tempfile, pathlib
RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(f"  {'✔' if ok else '✗'} {label}" + (f" — {detail}" if detail else ""))

def load(lang, data_dir):
    os.environ["PERSONAL_ONTOLOGY_DATA"] = data_dir
    pathlib.Path(data_dir, "settings.json").write_text(json.dumps({"display_language": lang}))
    for name in [m for m in list(sys.modules) if m.startswith("backend")]:
        del sys.modules[name]
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from backend import scenario_llm
    return scenario_llm

EMPTY = {"facts": [], "resource_types": [], "actions": [], "policies": [], "questions": []}
for lang, expected in (("zh", "目的城市"), ("en", "Destination city")):
    module = load(lang, tempfile.mkdtemp())
    result = module._hotel_fallback("预定酒店，到北京，不超过500元", json.loads(json.dumps(EMPTY)), None, lang)
    labels = [f.get("label") for f in result.get("facts") or []]
    check(f"{lang}：兜底不再抛 NameError 且标签正确", expected in labels, str(labels))

module = load("zh", tempfile.mkdtemp())
check("不带 language 时也能工作（向后兼容）",
      bool(module._hotel_fallback("预定酒店，到北京", json.loads(json.dumps(EMPTY))).get("facts")))
check("非酒店文本不触发兜底",
      not (module._hotel_fallback("整理相册", json.loads(json.dumps(EMPTY))) or {}).get("facts"))

passed = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
for ok, label in RESULTS:
    if not ok: print("  失败：", label)
sys.exit(0 if passed == len(RESULTS) else 1)
