"""字段标签按显示语言本地化自检。

    ~/personal-ontology/.venv/bin/python tests/test_label_localization.py

动机：场景分析产出的标签固定为**分析当时**的语言，切换界面语言后旧场景仍显示中文。
读取时按显示语言重新取用：已知字段用规范英文标签，自定义字段含中文时退回英文键。
"""
import os, sys, tempfile, pathlib
os.environ.setdefault("PERSONAL_ONTOLOGY_DATA", tempfile.mkdtemp(prefix="label-"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend.api import _localize_scene_labels

RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(f"  {'✔' if ok else '✗'} {label}" + (f" — {detail}" if detail else ""))

SCENE = {"id": "scene_x", "analysis": {
    "required_inputs": [{"name": "check_in_date", "label": "入住日期"},
                        {"name": "target_host", "label": "目标主机"}],
    "facts": [{"name": "price_max", "label": "最高价格"}, {"name": "custom_flag", "label": "自定义标记"}]}}

zh = _localize_scene_labels(SCENE, "zh")
check("中文模式下标签原样（不写回、不改动）",
      zh["analysis"]["required_inputs"][0]["label"] == "入住日期")
en = _localize_scene_labels(SCENE, "en")
labels = {x["name"]: x["label"] for x in en["analysis"]["required_inputs"] + en["analysis"]["facts"]}
check("已知字段取规范英文标签", labels["check_in_date"] == "Check-in date", str(labels["check_in_date"]))
check("已知偏好字段取规范英文标签", labels["price_max"] == "Maximum price", str(labels["price_max"]))
check("自定义字段含中文时退回英文键", labels["target_host"] == "target_host", str(labels["target_host"]))
check("英文标签的自定义字段保持不变", labels["custom_flag"] == "custom_flag", str(labels["custom_flag"]))
check("原记录未被修改（只影响展示）", SCENE["analysis"]["required_inputs"][0]["label"] == "入住日期")

passed = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
for ok, label in RESULTS:
    if not ok: print("  失败：", label)
sys.exit(0 if passed == len(RESULTS) else 1)
