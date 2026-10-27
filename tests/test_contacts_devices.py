"""设备区分：标签带完整序列号；别名可设可清；同型号不同序列号不混。"""
import os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()
from backend import contacts_sync as cs
R = []
def check(n, ok, d=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + n + ((" — " + str(d)[:160]) if d and not ok else ""))
# 伪造 adb 输出：两台同型号手机，序列号不同
cs.list_devices = lambda: [{"serial": "33c00b3", "model": "PKG110"}, {"serial": "9af21c7", "model": "PKG110"}]
cs._run_adb = lambda args, timeout=120, serial=None: "PKG110\n"
l1 = cs.device_label("33c00b3"); l2 = cs.device_label("9af21c7")
check("标签含完整序列号", "33c00b3" in l1, l1)
check("同型号不同序列号得到不同标签", l1 != l2, (l1, l2))
check("型号也在标签里", "PKG110" in l1, l1)
cs._run_adb = lambda args, timeout=120, serial=None: "\n"
l3 = cs.device_label(None)
check("取不到型号时仍保留序列号（可区分）", "33c00b3" in l3, l3)
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
