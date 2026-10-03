"""后端消息目录自检（中英双语）。

    ~/personal-ontology/.venv/bin/python tests/test_messages_bilingual.py

覆盖两部分：
  1. 目录完整性：每条消息都有 zh 与 en，且英文不含中文字符；
  2. 取值逻辑：set_language 后 msg() 返回对应语言，插值参数正确。

注意（已知限制，见 docs/00-first-principle-bilingual.md）：
**请求语言尚未真正传到端点** —— 中间件与 FastAPI 依赖里设置的 contextvars 都未
在端点内可见（实测 X-Display-Language: en 仍返回中文）。因此线上目前一律中文。
修法见文档：改为在**异常处理器**里按 request 解析消息键。
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend import messages

RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(f"  {'✔' if ok else '✗'} {label}" + (f" — {detail}" if detail else ""))

CJK = __import__("re").compile(r"[\u4e00-\u9fff]")

check("目录非空", len(messages.MESSAGES) > 0, f"{len(messages.MESSAGES)} 条")
missing_en = [k for k, v in messages.MESSAGES.items() if not v.get("en")]
missing_zh = [k for k, v in messages.MESSAGES.items() if not v.get("zh")]
check("每条都有英文", not missing_en, str(missing_en))
check("每条都有中文", not missing_zh, str(missing_zh))
cjk_in_en = [k for k, v in messages.MESSAGES.items() if CJK.search(v.get("en", ""))]
check("英文不含中文字符", not cjk_in_en, str(cjk_in_en))

messages.set_language("zh"); zh = messages.msg("login_password_required")
messages.set_language("en"); en = messages.msg("login_password_required")
check("按语言取值", zh == "请输入登录密码。" and en == "Enter the login password.", f"{zh!r} / {en!r}")
check("未知键回落键名", messages.msg("no_such_key_xyz") == "no_such_key_xyz")
messages.set_language("en")
check("插值参数", messages.msg("too_many_attempts", seconds=7) == "Too many attempts. Try again in 7 seconds.",
      messages.msg("too_many_attempts", seconds=7))
messages.set_language("zh")
check("插值参数（中文）", "7" in messages.msg("too_many_attempts", seconds=7))
check("缺参数不抛异常（回落原文）", isinstance(messages.msg("too_many_attempts"), str))

passed = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
for ok, label in RESULTS:
    if not ok: print("  失败：", label)
sys.exit(0 if passed == len(RESULTS) else 1)
