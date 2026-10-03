"""来源校验（CSRF 防护）自检 —— 必须挡住跨站，但不能挡住经反向代理的访问。

    ~/personal-ontology/.venv/bin/python tests/test_origin_policy.py

背景：中间件原先硬编码只允许 http://localhost / http://127.0.0.1，
经 nginx/Caddy 反代到公网域名后，登录请求带 Origin=https://域名 被 403（"Origin not allowed"）。
"""
import os, sys, tempfile, pathlib
os.environ.setdefault("PERSONAL_ONTOLOGY_DATA", tempfile.mkdtemp(prefix="origin-"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend import api, config

RESULTS = []
def check(label, ok, detail=""):
    RESULTS.append((bool(ok), label)); print(f"  {'✔' if ok else '✗'} {label}" + (f" — {detail}" if detail else ""))

class Req:
    def __init__(self, headers): self.headers = headers

def allowed(origin, headers):
    return api._origin_allowed(origin, Req(headers))

check("本机回环来源允许", allowed("http://127.0.0.1:8765", {}))
check("localhost 来源允许", allowed("http://localhost:8765", {}))
check("反代同源允许（Origin 与 Host 同域）",
      allowed("https://ontology.example.com", {"host": "ontology.example.com"}))
check("反代同源允许（靠 X-Forwarded-Host，Host 被改写成回环）",
      allowed("https://ontology.example.com",
              {"host": "127.0.0.1:8765", "x-forwarded-host": "ontology.example.com"}))
check("跨站来源拒绝（Origin 与 Host 不同域）",
      not allowed("https://evil.example.com", {"host": "ontology.example.com"}))
check("跨站来源拒绝（Host 被伪造也无效）",
      not allowed("https://ontology.example.com", {"host": "evil.example.com"}))
check("无 Host 且非回环时拒绝（不误放行）",
      not allowed("https://ontology.example.com", {}))

config.ALLOWED_ORIGINS = ["https://explicit.example.com"]
check("显式白名单允许", allowed("https://explicit.example.com", {"host": "127.0.0.1:8765"}))
check("白名单不影响拒绝其它来源",
      not allowed("https://other.example.com", {"host": "127.0.0.1:8765"}))
config.ALLOWED_ORIGINS = []

check("不支持通配 *（不因配置而全局放开）",
      not allowed("https://anything.example.com", {"host": "127.0.0.1:8765"}))


# 静态守卫：管理器也必须走共享判定（只修后端是不够的——浏览器只跟管理器说话）。
manager_src = (pathlib.Path(__file__).resolve().parent.parent / "backend/manager.py").read_text(encoding="utf-8")
check("管理器使用共享判定（而非硬编码回环）",
      "origin_allowed(origin, request.headers, ALLOWED_ORIGINS)" in manager_src
      and 'origin.startswith(("http://localhost"' not in manager_src)
api_src = (pathlib.Path(__file__).resolve().parent.parent / "backend/api.py").read_text(encoding="utf-8")
check("后端也使用共享判定", "from .origin_policy import origin_allowed" in api_src)

passed = sum(1 for ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
for ok, label in RESULTS:
    if not ok: print("  失败：", label)
sys.exit(0 if passed == len(RESULTS) else 1)
